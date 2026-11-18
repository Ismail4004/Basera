"""US-06: create a grow profile, and see your saved profiles listed."""

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from catalog.models import Region

from .models import GrowProfile

FAST_HASHERS = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])

VALID = {
    "name": "Backyard",
    "space_type": "OUTDOOR",
    "sunlight": "FULL_SUN",
    "soil_type": "LOAM",
    "water_availability": "MEDIUM",
    "purpose": "SHADE_COOLING",
}


@FAST_HASHERS
class CreateGrowProfileTests(TestCase):
    url = "/profiles/new/"

    def setUp(self):
        self.region = Region.objects.create(name="Punjab Plains")
        self.user = User.objects.create_user("ana@example.com", "x", full_name="Ana Khan")
        self.client.force_login(self.user)

    def post(self, **changes):
        data = {**VALID, "region": self.region.pk, **changes}
        return self.client.post(self.url, data)

    def test_valid_profile_is_saved_under_the_logged_in_customer_and_listed(self):
        response = self.post()
        self.assertRedirects(response, reverse("grow_profiles"))
        profile = GrowProfile.objects.get()
        self.assertEqual((profile.user, profile.region, profile.name), (self.user, self.region, "Backyard"))
        self.assertEqual(profile.sunlight, "FULL_SUN")
        page = self.client.get(reverse("grow_profiles"))
        self.assertContains(page, "Backyard")
        self.assertContains(page, "Punjab Plains")

    def test_every_missing_field_shows_its_own_error_and_saves_nothing(self):
        response = self.client.post(self.url, {})
        for text in ("Please give this profile a name.", "Please choose a region.",
                     "Please choose indoor or outdoor.", "Please choose your soil.",
                     "Please choose how much water you can provide.",
                     "Please choose what you want the plants to do."):
            self.assertContains(response, text)
        self.assertContains(response, "Please fix the highlighted fields and try again.")
        self.assertEqual(GrowProfile.objects.count(), 0)

    def test_a_failed_save_keeps_what_the_user_typed(self):
        response = self.post(sunlight="")
        self.assertContains(response, 'value="Backyard"')
        self.assertContains(response, 'value="LOAM" checked')

    def test_values_outside_the_fixed_choices_are_rejected(self):
        self.post(sunlight="MOONLIGHT")
        self.assertEqual(GrowProfile.objects.count(), 0)

    def test_region_choices_come_from_the_region_table(self):
        Region.objects.create(name="Potohar Plateau")
        page = self.client.get(self.url)
        self.assertContains(page, "Punjab Plains")
        self.assertContains(page, "Potohar Plateau")

    def test_the_user_cannot_be_chosen_through_the_form(self):
        other = User.objects.create_user("bo@example.com", "x", full_name="Bo")
        self.post(user=other.pk)
        self.assertEqual(GrowProfile.objects.get().user, self.user)


@FAST_HASHERS
class ProfileListTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Punjab Plains")
        self.ana = User.objects.create_user("ana@example.com", "x", full_name="Ana Khan")
        self.bo = User.objects.create_user("bo@example.com", "x", full_name="Bo Ali")

    def make(self, user, name):
        return GrowProfile.objects.create(user=user, region=self.region, name=name, space_type="OUTDOOR",
                                          sunlight="FULL_SUN", soil_type="LOAM", water_availability="LOW",
                                          purpose="FOOD")

    def test_empty_list_invites_the_customer_to_create_one(self):
        self.client.force_login(self.ana)
        page = self.client.get(reverse("grow_profiles"))
        self.assertContains(page, "You haven’t created a grow profile yet")
        self.assertContains(page, reverse("grow_profile_new"))

    def test_a_customer_only_sees_their_own_profiles(self):
        self.make(self.ana, "Ana's balcony")
        self.make(self.bo, "Bo's roof")
        self.client.force_login(self.ana)
        page = self.client.get(reverse("grow_profiles"))
        self.assertContains(page, "Ana&#x27;s balcony")
        self.assertNotContains(page, "Bo&#x27;s roof")

    def test_logged_out_visitors_are_sent_to_log_in(self):
        for url in ("/profiles/", "/profiles/new/"):
            self.assertRedirects(self.client.get(url), f"/?next={url}")

    def test_sellers_cannot_use_grow_profiles(self):
        seller = User.objects.create_user("s@example.com", "x", full_name="Sam", role=User.Role.SELLER)
        self.client.force_login(seller)
        self.assertRedirects(self.client.get("/profiles/"), reverse("home"))
