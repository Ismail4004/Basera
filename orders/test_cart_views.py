"""Tests for the cart (US-19): add, change the quantity, remove.

The views live in orders.views; the cart page is /cart/.
"""

import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from accounts.tests import FAST_HASHERS
from catalog.models import PlantSpecies

from .models import CartItem

User = get_user_model()


def make_species(seller, name, **overrides):
    data = dict(
        seller=seller, common_name=name, scientific_name=f"{name} scientificus",
        description="A test plant.", light_need="Full sun", water_need="Low",
        suitable_soils="Loam", setting=PlantSpecies.Setting.OUTDOOR,
        ecological_role="Feeds bees.", price=Decimal("450.00"), stock_qty=10,
    )
    data.update(overrides)
    return PlantSpecies.objects.create(**data)


@FAST_HASHERS
class CartTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            "seller@basera.test", "x", full_name="Sam Seller", role=User.Role.SELLER
        )
        self.customer = User.objects.create_user("ana@example.com", "x", full_name="Ana Khan")
        self.species = make_species(self.seller, "Neem")
        self.client.force_login(self.customer)

    def messages(self, response):
        return [m.message for m in get_messages(response.wsgi_request)]

    # --- adding ---------------------------------------------------------

    def test_add_creates_a_line_with_one_plant(self):
        response = self.client.post(reverse("cart_add", args=[self.species.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        item = CartItem.objects.get(user=self.customer, species=self.species)
        self.assertEqual(item.quantity, 1)
        self.assertIn("Neem is in your cart.", self.messages(response))

    def test_adding_again_raises_the_quantity_instead_of_a_second_line(self):
        self.client.post(reverse("cart_add", args=[self.species.pk]))
        self.client.post(reverse("cart_add", args=[self.species.pk]))
        items = CartItem.objects.filter(user=self.customer, species=self.species)
        self.assertEqual(items.count(), 1)
        self.assertEqual(items.get().quantity, 2)

    def test_quantity_is_capped_by_stock(self):
        self.species.stock_qty = 2
        self.species.save(update_fields=["stock_qty"])
        response = self.client.post(
            reverse("cart_add", args=[self.species.pk]), {"quantity": 5}, follow=True
        )
        self.assertEqual(CartItem.objects.get(user=self.customer).quantity, 2)
        self.assertTrue(any("that's all that's left in stock" in m for m in self.messages(response)))

    def test_adding_the_last_one_again_reports_the_limit(self):
        self.species.stock_qty = 1
        self.species.save(update_fields=["stock_qty"])
        self.client.post(reverse("cart_add", args=[self.species.pk]))
        response = self.client.post(reverse("cart_add", args=[self.species.pk]), follow=True)
        self.assertEqual(CartItem.objects.get(user=self.customer).quantity, 1)
        self.assertTrue(any("already in your cart" in m for m in self.messages(response)))

    def test_stock_dropping_below_the_cart_never_lowers_the_line(self):
        item = CartItem.objects.create(user=self.customer, species=self.species, quantity=5)
        self.species.stock_qty = 2
        self.species.save(update_fields=["stock_qty"])
        response = self.client.post(reverse("cart_add", args=[self.species.pk]), follow=True)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 5)
        self.assertTrue(any("are left in stock" in m for m in self.messages(response)))

    def test_invasive_plant_never_enters_the_cart(self):
        invasive = make_species(self.seller, "Lantana", is_invasive=True)
        response = self.client.post(reverse("cart_add", args=[invasive.pk]), follow=True)
        self.assertFalse(CartItem.objects.filter(species=invasive).exists())
        self.assertIn("doesn't sell it", self.messages(response)[0])

    def test_out_of_stock_plant_never_enters_the_cart(self):
        sold_out = make_species(self.seller, "Arjun", stock_qty=0)
        response = self.client.post(reverse("cart_add", args=[sold_out.pk]), follow=True)
        self.assertFalse(CartItem.objects.filter(species=sold_out).exists())
        self.assertIn("out of stock", self.messages(response)[0])

    def test_hidden_listing_cannot_be_added(self):
        hidden = make_species(self.seller, "Hidden", is_active=False)
        response = self.client.post(reverse("cart_add", args=[hidden.pk]))
        self.assertEqual(response.status_code, 404)

    def test_guest_is_sent_to_log_in(self):
        self.client.logout()
        response = self.client.post(reverse("cart_add", args=[self.species.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertFalse(CartItem.objects.exists())

    def test_seller_cannot_shop(self):
        self.client.force_login(self.seller)
        response = self.client.post(reverse("cart_add", args=[self.species.pk]), follow=True)
        self.assertFalse(CartItem.objects.exists())
        self.assertIn("Only customer accounts", self.messages(response)[0])

    def test_next_returns_to_the_page_the_button_was_on(self):
        response = self.client.post(
            reverse("cart_add", args=[self.species.pk]), {"next": reverse("catalogue")}
        )
        self.assertEqual(response["Location"], reverse("catalogue"))

    def test_next_cannot_point_at_another_site(self):
        response = self.client.post(
            reverse("cart_add", args=[self.species.pk]), {"next": "https://evil.example/"}
        )
        self.assertEqual(response["Location"], reverse("species_detail", args=[self.species.pk]))

    # --- changing the quantity ------------------------------------------

    def test_stepper_moves_the_quantity_up_and_down(self):
        item = CartItem.objects.create(user=self.customer, species=self.species, quantity=2)
        self.client.post(reverse("cart_update", args=[self.species.pk]), {"delta": 1})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 3)
        self.client.post(reverse("cart_update", args=[self.species.pk]), {"delta": -1})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    def test_quantity_never_drops_below_one(self):
        item = CartItem.objects.create(user=self.customer, species=self.species, quantity=1)
        self.client.post(reverse("cart_update", args=[self.species.pk]), {"delta": -1})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)

    def test_quantity_never_exceeds_stock(self):
        self.species.stock_qty = 3
        self.species.save(update_fields=["stock_qty"])
        item = CartItem.objects.create(user=self.customer, species=self.species, quantity=3)
        response = self.client.post(
            reverse("cart_update", args=[self.species.pk]), {"delta": 1}, follow=True
        )
        item.refresh_from_db()
        self.assertEqual(item.quantity, 3)
        self.assertIn("only 3", self.messages(response)[0])

    def test_update_accepts_an_explicit_quantity(self):
        item = CartItem.objects.create(user=self.customer, species=self.species, quantity=1)
        self.client.post(reverse("cart_update", args=[self.species.pk]), {"quantity": 4})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 4)

    # --- removing -------------------------------------------------------

    def test_remove_deletes_the_line(self):
        CartItem.objects.create(user=self.customer, species=self.species, quantity=2)
        response = self.client.post(reverse("cart_remove", args=[self.species.pk]), follow=True)
        self.assertFalse(CartItem.objects.exists())
        self.assertIn("removed from your cart", self.messages(response)[0])

    def test_removing_something_that_is_not_there_is_harmless(self):
        response = self.client.post(reverse("cart_remove", args=[self.species.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("wasn't in your cart", self.messages(response)[0])

    # --- the page -------------------------------------------------------

    def test_cart_page_lists_each_line_with_its_total(self):
        CartItem.objects.create(user=self.customer, species=self.species, quantity=2)
        response = self.client.get(reverse("cart"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Neem")
        self.assertContains(response, "Rs 900")  # 2 x 450
        self.assertContains(response, "Rs 450 each")

    def test_cart_page_flags_a_line_that_sold_out(self):
        CartItem.objects.create(user=self.customer, species=self.species, quantity=2)
        self.species.stock_qty = 0
        self.species.save(update_fields=["stock_qty"])
        response = self.client.get(reverse("cart"))
        self.assertContains(response, "No longer available")

    def test_empty_cart_page_says_so(self):
        response = self.client.get(reverse("cart"))
        self.assertContains(response, "Your cart is empty.")

    def test_header_badge_shows_how_many_plants_are_in_the_cart(self):
        CartItem.objects.create(user=self.customer, species=self.species, quantity=3)
        response = self.client.get(reverse("catalogue"))
        self.assertContains(response, '<span class="bt-badge">3</span>', html=True)

    def test_cart_page_needs_a_login(self):
        self.client.logout()
        response = self.client.get(reverse("cart"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    # --- the same changes, in place (HTMX) ------------------------------

    def test_htmx_add_answers_with_a_fragment_and_no_redirect(self):
        response = self.client.post(
            reverse("cart_add", args=[self.species.pk]), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CartItem.objects.get(user=self.customer).quantity, 1)
        # the header link is swapped out of band; the message rides in a trigger
        self.assertContains(response, 'hx-swap-oob="true"')
        self.assertNotIn("Location", response)
        self.assertIn("Neem is in your cart.", json.loads(response["HX-Trigger"])["cart:notice"]["message"])

    def test_htmx_update_swaps_the_cart_body_in_place(self):
        CartItem.objects.create(user=self.customer, species=self.species, quantity=1)
        response = self.client.post(
            reverse("cart_update", args=[self.species.pk]), {"delta": 1}, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cart-body"')
        self.assertContains(response, "Rs 900")  # 2 x 450, rendered by the fragment
        self.assertEqual(CartItem.objects.get(user=self.customer).quantity, 2)

    def test_htmx_stepper_success_is_quiet_but_limits_are_not(self):
        CartItem.objects.create(user=self.customer, species=self.species, quantity=1)
        quiet = self.client.post(
            reverse("cart_update", args=[self.species.pk]), {"delta": 1}, HTTP_HX_REQUEST="true"
        )
        self.assertNotIn("HX-Trigger", quiet)

        self.species.stock_qty = 2
        self.species.save(update_fields=["stock_qty"])
        loud = self.client.post(
            reverse("cart_update", args=[self.species.pk]), {"delta": 1}, HTTP_HX_REQUEST="true"
        )
        self.assertIn("only 2", json.loads(loud["HX-Trigger"])["cart:notice"]["message"])

    def test_htmx_remove_falls_back_to_the_empty_state(self):
        CartItem.objects.create(user=self.customer, species=self.species, quantity=1)
        response = self.client.post(
            reverse("cart_remove", args=[self.species.pk]), HTTP_HX_REQUEST="true"
        )
        self.assertContains(response, "Your cart is empty.")
        self.assertContains(response, 'id="cart-body"')

    def test_htmx_request_from_a_guest_asks_the_browser_to_navigate(self):
        self.client.logout()
        response = self.client.post(
            reverse("cart_add", args=[self.species.pk]), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 204)
        self.assertIn("/?next=", response["HX-Redirect"])

    # --- method guards --------------------------------------------------

    def test_cart_changes_only_accept_post(self):
        for name in ("cart_add", "cart_update", "cart_remove"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name, args=[self.species.pk]))
                self.assertEqual(response.status_code, 405)
