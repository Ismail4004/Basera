"""Security and access-control cases (test-case sections A7 and A8).

These check that pages are protected for the right roles, that forms refuse a
request without the CSRF token, and that what a visitor types is never run as
HTML or as part of a database query.
"""

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from catalog.models import PlantSpecies, Region, SpeciesRegion
from growprofiles.models import GrowProfile

FAST = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
SCRIPT = "<script>alert(1)</script>"


@FAST
class SecurityBase(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Punjab Plains")
        self.customer = User.objects.create_user("c@example.com", "x", full_name="Cy Khan")
        self.seller = User.objects.create_user("s@example.com", "x", full_name="Sam", role=User.Role.SELLER)
        self.admin = User.objects.create_superuser("a@example.com", "x", full_name="Ada")
        self.species = PlantSpecies.objects.create(
            seller=self.seller, common_name="Neem", scientific_name="Azadirachta indica", light_need="Full sun",
            water_need="Low", suitable_soils="Loam", setting="OUTDOOR", price=450, stock_qty=5,
            ecological_role="Shade.")
        SpeciesRegion.objects.create(species=self.species, region=self.region)
        self.profile = GrowProfile.objects.create(
            user=self.customer, region=self.region, name="Backyard", space_type="OUTDOOR", sunlight="FULL_SUN",
            soil_type="LOAM", water_availability="LOW", purpose="SHADE_COOLING")


class AccessControlTests(SecurityBase):
    """SEC-01 to SEC-05: who may open which page."""

    def test_sec01_logged_out_visitors_are_sent_to_log_in_from_every_private_page(self):
        for url in ("/home/", "/profiles/", "/profiles/new/", "/matches/", f"/match/{self.profile.pk}/", "/cart/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith("/?next="), response["Location"])

    def test_sec02_public_pages_open_without_logging_in(self):
        for url in ("/", "/signup/", "/forgot-password/", "/catalogue/", f"/species/{self.species.pk}/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_sec03_sellers_and_admins_cannot_use_customer_only_pages(self):
        for user in (self.seller, self.admin):
            self.client.force_login(user)
            for url in ("/profiles/", "/profiles/new/", f"/match/{self.profile.pk}/", "/matches/"):
                with self.subTest(user=user.role, url=url):
                    self.assertRedirects(self.client.get(url), reverse("home"))

    def test_sec04_the_admin_site_is_for_admins_only(self):
        for user in (self.customer, self.seller):
            self.client.force_login(user)
            response = self.client.get("/admin/")
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin/login/", response["Location"])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_sec05_a_customer_cannot_open_another_customers_profile(self):
        other = User.objects.create_user("o@example.com", "x", full_name="Olu")
        self.client.force_login(other)
        self.assertEqual(self.client.get(f"/match/{self.profile.pk}/").status_code, 404)
        self.assertNotContains(self.client.get("/profiles/"), "Backyard")

    def test_sec06_unknown_pages_give_a_404(self):
        self.assertEqual(self.client.get("/no-such-page/").status_code, 404)


class CsrfTests(SecurityBase):
    """SEC-07 to SEC-09: a form post without the CSRF token is refused."""

    def setUp(self):
        super().setUp()
        self.strict = Client(enforce_csrf_checks=True)
        self.strict.force_login(self.customer)

    def test_sec07_log_out_needs_the_token(self):
        self.assertEqual(self.strict.post("/logout/").status_code, 403)

    def test_sec08_add_to_cart_needs_the_token(self):
        self.assertEqual(self.strict.post(f"/cart/add/{self.species.pk}/").status_code, 403)
        from orders.models import CartItem
        self.assertEqual(CartItem.objects.count(), 0)

    def test_sec09_creating_a_profile_needs_the_token(self):
        self.assertEqual(self.strict.post("/profiles/new/", {"name": "x"}).status_code, 403)
        self.assertEqual(GrowProfile.objects.count(), 1)  # only the one from setUp


class InjectionTests(SecurityBase):
    """SEC-10 to SEC-13: typed text is shown as text and never run."""

    def test_sec10_a_script_in_a_plant_name_is_escaped_in_the_catalogue(self):
        PlantSpecies.objects.filter(pk=self.species.pk).update(common_name=SCRIPT)
        page = self.client.get("/catalogue/")
        self.assertNotContains(page, SCRIPT)
        self.assertContains(page, "&lt;script&gt;")

    def test_sec11_a_script_in_a_profile_name_is_escaped_on_every_page_that_shows_it(self):
        GrowProfile.objects.filter(pk=self.profile.pk).update(name=SCRIPT)
        self.client.force_login(self.customer)
        for url in ("/profiles/", f"/match/{self.profile.pk}/"):
            with self.subTest(url=url):
                page = self.client.get(url)
                self.assertNotContains(page, SCRIPT)
                self.assertContains(page, "&lt;script&gt;")

    def test_sec12_a_script_in_the_search_box_is_escaped(self):
        page = self.client.get("/catalogue/", {"q": SCRIPT})
        self.assertNotContains(page, SCRIPT)

    def test_sec13_sql_looking_searches_are_treated_as_plain_text(self):
        for term in ("' OR 1=1 --", "'; DROP TABLE catalog_plantspecies; --", "%", "_"):
            with self.subTest(term=term):
                page = self.client.get("/catalogue/", {"q": term})
                self.assertEqual(page.status_code, 200)
                self.assertEqual(page.context["page"].paginator.count, 0)
        self.assertEqual(PlantSpecies.objects.count(), 1)  # the table is still there


class OpenRedirectAndSessionTests(SecurityBase):
    def test_sec14_log_out_ends_the_session(self):
        self.client.force_login(self.customer)
        self.client.post("/logout/")
        self.assertEqual(self.client.get("/home/").status_code, 302)

    def test_sec15_the_reset_email_has_a_link_but_never_the_password_or_its_hash(self):
        from django.core import mail
        user = User.objects.create_user("p@example.com", "Zq7-distinct-passphrase", full_name="Pat Lee")
        self.client.post("/forgot-password/", {"email": user.email})
        body = mail.outbox[0].body
        self.assertIn("/reset/", body)
        self.assertNotIn("Zq7-distinct-passphrase", body)
        self.assertNotIn(user.password, body)
        self.assertNotEqual(user.password, "Zq7-distinct-passphrase")
