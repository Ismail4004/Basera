"""Grow profile data rules (test-case section A11)."""

from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from catalog.models import Region

from .models import GrowProfile

FAST = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
VALID = {"name": "Backyard", "space_type": "OUTDOOR", "sunlight": "FULL_SUN", "soil_type": "LOAM",
         "water_availability": "MEDIUM", "purpose": "SHADE_COOLING"}


@FAST
class ProfileIntegrityTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Punjab Plains")
        self.user = User.objects.create_user("c@example.com", "x", full_name="Cy Khan")
        self.profile = GrowProfile.objects.create(user=self.user, region=self.region, **VALID)

    def test_gp01_a_region_that_profiles_use_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.region.delete()
        self.assertTrue(Region.objects.filter(pk=self.region.pk).exists())

    def test_gp02_deleting_a_user_deletes_their_profiles(self):
        self.user.delete()
        self.assertEqual(GrowProfile.objects.count(), 0)

    def test_gp03_a_name_of_only_spaces_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("grow_profile_new"), {**VALID, "name": "    ", "region": self.region.pk})
        self.assertContains(response, "Please give this profile a name.")
        self.assertEqual(GrowProfile.objects.count(), 1)

    def test_gp04_a_name_over_100_characters_is_rejected(self):
        self.client.force_login(self.user)
        self.client.post(reverse("grow_profile_new"), {**VALID, "name": "x" * 101, "region": self.region.pk})
        self.assertEqual(GrowProfile.objects.count(), 1)

    def test_gp05_a_region_that_does_not_exist_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("grow_profile_new"), {**VALID, "region": 9999})
        self.assertContains(response, "Please choose a region.")
        self.assertEqual(GrowProfile.objects.count(), 1)

    def test_gp06_the_newest_profile_is_listed_first_and_each_user_can_have_several(self):
        newer = GrowProfile.objects.create(user=self.user, region=self.region, **{**VALID, "name": "Balcony"})
        self.client.force_login(self.user)
        page = self.client.get(reverse("grow_profiles"))
        self.assertEqual([p.pk for p in page.context["profiles"]], [newer.pk, self.profile.pk])

    def test_gp07_whitespace_around_a_name_is_trimmed(self):
        self.client.force_login(self.user)
        self.client.post(reverse("grow_profile_new"), {**VALID, "name": "  Roof  ", "region": self.region.pk})
        self.assertTrue(GrowProfile.objects.filter(name="Roof").exists())
