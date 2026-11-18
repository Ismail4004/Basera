"""Tests for the catalogue (US-18), species details (US-12), invasive handling (US-10)
and the role-based landing placeholders."""

from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.tests import FAST_HASHERS

from .models import PlantSpecies, Region, SpeciesRegion

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
class CatalogueTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("s@basera.test", "x", full_name="Sam Seller", role=User.Role.SELLER)

    def test_guest_can_browse_and_sees_only_active_species(self):
        make_species(self.seller, "Neem")
        make_species(self.seller, "Hidden", is_active=False)
        response = self.client.get(reverse("catalogue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Neem")
        self.assertNotContains(response, "Hidden")

    def test_twelve_per_page_with_pagination(self):
        for i in range(15):
            make_species(self.seller, f"Plant {i:02d}")
        first = self.client.get(reverse("catalogue"))
        self.assertEqual(len(first.context["page"].object_list), 12)
        self.assertContains(first, "Showing 1–12 of 15")
        second = self.client.get(reverse("catalogue"), {"page": 2})
        self.assertEqual(len(second.context["page"].object_list), 3)

    def test_search_matches_common_or_scientific_name_case_insensitively(self):
        make_species(self.seller, "Neem", scientific_name="Azadirachta indica")
        make_species(self.seller, "Ber", scientific_name="Ziziphus mauritiana")
        by_common = self.client.get(reverse("catalogue"), {"q": "nEEm"})
        self.assertEqual([s.common_name for s in by_common.context["page"].object_list], ["Neem"])
        by_scientific = self.client.get(reverse("catalogue"), {"q": "ZIZIPHUS"})
        self.assertEqual([s.common_name for s in by_scientific.context["page"].object_list], ["Ber"])

    def test_search_with_no_match_says_so(self):
        make_species(self.seller, "Neem")
        response = self.client.get(reverse("catalogue"), {"q": "zzz"})
        self.assertContains(response, "No plants match")

    def test_search_keeps_term_across_pages(self):
        for i in range(14):
            make_species(self.seller, f"Pine {i:02d}")
        response = self.client.get(reverse("catalogue"), {"q": "pine"})
        self.assertContains(response, "q=pine&amp;page=2")

    def test_htmx_request_gets_only_the_results_partial(self):
        make_species(self.seller, "Neem")
        response = self.client.get(reverse("catalogue"), {"q": "neem"}, headers={"HX-Request": "true"})
        self.assertContains(response, "Neem")
        self.assertNotContains(response, "<html")

    def test_invasive_has_warning_and_no_buy_button(self):
        make_species(self.seller, "Lantana", is_invasive=True)
        response = self.client.get(reverse("catalogue"))
        self.assertContains(response, "Invasive — not sold")
        self.assertContains(response, "Not sold")
        self.assertNotContains(response, "Add to cart")

    def test_out_of_stock_is_listed_but_cannot_be_added(self):
        make_species(self.seller, "Amaltas", stock_qty=0)
        response = self.client.get(reverse("catalogue"))
        self.assertContains(response, "Amaltas")
        self.assertContains(response, "Out of stock")
        self.assertNotContains(response, "Add to cart")

    def test_guest_add_to_cart_goes_to_login_and_returns_to_species(self):
        species = make_species(self.seller, "Neem")
        response = self.client.get(reverse("catalogue"))
        self.assertContains(response, f"{reverse('login')}?next={reverse('species_detail', args=[species.pk])}")

    def test_seller_does_not_see_a_buy_button(self):
        make_species(self.seller, "Neem")
        self.client.force_login(self.seller)
        self.assertNotContains(self.client.get(reverse("catalogue")), "Add to cart")


@FAST_HASHERS
class SpeciesDetailTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("s@basera.test", "x", full_name="Sam Seller", role=User.Role.SELLER)
        self.punjab = Region.objects.create(name="Punjab Plains")
        self.species = make_species(self.seller, "Neem")
        SpeciesRegion.objects.create(species=self.species, region=self.punjab)

    def test_shows_all_the_details(self):
        response = self.client.get(reverse("species_detail", args=[self.species.pk]))
        for text in ("Neem", "Neem scientificus", "Rs 450", "In stock · 10 available", "A test plant.",
                     "Full sun", "Punjab Plains", "Sam Seller", "Feeds bees."):
            self.assertContains(response, text)

    def test_inactive_or_missing_species_give_404(self):
        hidden = make_species(self.seller, "Hidden", is_active=False)
        self.assertEqual(self.client.get(reverse("species_detail", args=[hidden.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("species_detail", args=[999999])).status_code, 404)

    def test_invasive_shows_banner_and_hides_add_to_cart(self):
        invasive = make_species(self.seller, "Lantana", is_invasive=True)
        SpeciesRegion.objects.create(species=invasive, region=self.punjab)
        response = self.client.get(reverse("species_detail", args=[invasive.pk]))
        self.assertContains(response, "Invasive species — not sold on Basera")
        self.assertContains(response, "Not available for purchase")
        # No buy button on the invasive plant itself (the alternatives below may have one).
        actions = response.content.decode().split('class="bt-detail__actions"')[1].split("</div>")[0]
        self.assertNotIn("Add to cart", actions)
        self.assertNotIn("Log in to add to cart", actions)
        # It suggests native alternatives from the same region.
        self.assertContains(response, "Native alternatives")
        self.assertContains(response, "Neem")

    def test_out_of_stock_hides_add_to_cart(self):
        self.species.stock_qty = 0
        self.species.save()
        response = self.client.get(reverse("species_detail", args=[self.species.pk]))
        self.assertContains(response, "Out of stock")
        actions = response.content.decode().split('class="bt-detail__actions"')[1].split("</div>")[0]
        self.assertNotIn("Add to cart", actions)

    def test_customer_sees_add_to_cart_and_guest_sees_login_prompt(self):
        url = reverse("species_detail", args=[self.species.pk])
        self.assertContains(self.client.get(url), "Log in to add to cart")
        customer = User.objects.create_user("c@basera.test", "x", full_name="Cy Customer")
        self.client.force_login(customer)
        self.assertContains(self.client.get(url), "Add to cart")

    def test_related_species_never_include_invasive_or_itself(self):
        other = make_species(self.seller, "Ber")
        bad = make_species(self.seller, "Mesquite", is_invasive=True)
        for s in (other, bad):
            SpeciesRegion.objects.create(species=s, region=self.punjab)
        related = self.client.get(reverse("species_detail", args=[self.species.pk])).context["related"]
        self.assertEqual([s.common_name for s in related], ["Ber"])


@FAST_HASHERS
class LandingPlaceholderTests(TestCase):
    def test_each_role_lands_on_its_own_placeholder_that_links_to_the_catalogue(self):
        cases = [
            (User.Role.CUSTOMER, "accounts/home_customer.html"),
            (User.Role.SELLER, "accounts/home_seller.html"),
            (User.Role.ADMIN, "accounts/home_admin.html"),
        ]
        for role, template in cases:
            with self.subTest(role=role):
                user = User.objects.create_user(f"{role.lower()}@basera.test", "x", full_name="Ana Khan", role=role)
                self.client.force_login(user)
                response = self.client.get(reverse("home"))
                self.assertTemplateUsed(response, template)
                self.assertContains(response, reverse("catalogue"))
                self.client.logout()

    def test_header_placeholder_pages_load(self):
        # "cart" is no longer a placeholder: it is a real page that needs a login,
        # covered by orders.test_cart_views.
        for name in ("match_results", "about", "seller_listings", "seller_orders",
                     "seller_earnings", "seller_guide", "admin_users", "admin_reports", "admin_settings"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)


@FAST_HASHERS
class LandingPageContentTests(TestCase):
    def setUp(self):
        call_command("seed_catalog", stdout=StringIO())

    def test_customer_home_features_five_native_plants_and_no_invasive_ones(self):
        customer = User.objects.create_user("c@basera.test", "x", full_name="Ana Khan")
        self.client.force_login(customer)
        response = self.client.get(reverse("home"))
        self.assertEqual(len(response.context["featured"]), 5)
        self.assertFalse(any(s.is_invasive for s in response.context["featured"]))
        for text in ("Grow closer", "How Basera works", "A little more local."):
            self.assertContains(response, text)

    def test_seller_home_shows_only_their_own_numbers(self):
        seller = User.objects.get(email="seller@basera.test")
        self.client.force_login(seller)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Good morning,")
        self.assertEqual(response.context["active_count"], PlantSpecies.objects.filter(seller=seller, is_active=True).count())
        self.assertContains(response, "No orders yet")
        self.assertContains(response, "Amaltas")  # out of stock, so it is in the stock check

    def test_admin_home_shows_platform_numbers(self):
        self.client.force_login(User.objects.get(email="admin@basera.test"))
        response = self.client.get(reverse("home"))
        self.assertContains(response, "A growing ecosystem.")
        self.assertEqual(response.context["listing_count"], PlantSpecies.objects.filter(is_active=True).count())
        self.assertEqual(response.context["region_total"], 5)
        self.assertContains(response, "Punjab Plains")


@FAST_HASHERS
class SeedCatalogueTests(TestCase):
    def test_seed_command_creates_35_species_and_is_repeatable(self):
        call_command("seed_catalog", stdout=StringIO())
        call_command("seed_catalog", stdout=StringIO())
        self.assertEqual(PlantSpecies.objects.count(), 35)
        self.assertEqual(Region.objects.count(), 5)
        self.assertEqual(PlantSpecies.objects.filter(is_invasive=True).count(), 4)
        self.assertTrue(all(s.regions.exists() for s in PlantSpecies.objects.all()))
        self.assertEqual(User.objects.filter(email__endswith="@basera.test").count(), 3)
