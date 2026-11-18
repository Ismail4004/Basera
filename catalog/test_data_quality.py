"""Seed data and catalogue paging cases (test-case sections A9 and A10)."""

import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from catalog.models import PlantSpecies, Region

FAST = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


class SeedDataTests(TestCase):
    """DQ-01 to DQ-08: what `manage.py seed_catalog` creates."""

    @classmethod
    def setUpTestData(cls):
        cls.media = tempfile.TemporaryDirectory()
        with override_settings(MEDIA_ROOT=cls.media.name):
            call_command("seed_catalog", stdout=StringIO())
            cls.species = list(PlantSpecies.objects.all())

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.media.cleanup()

    def test_dq01_creates_35_species_in_5_regions_with_4_invasive(self):
        self.assertEqual(len(self.species), 35)
        self.assertEqual(Region.objects.count(), 5)
        self.assertEqual(sum(s.is_invasive for s in self.species), 4)

    def test_dq02_every_species_has_at_least_one_native_region(self):
        self.assertTrue(all(s.regions.exists() for s in self.species))

    def test_dq03_every_species_has_a_photo_file(self):
        import os
        for s in self.species:
            self.assertTrue(s.image, s.common_name)
            self.assertTrue(os.path.exists(os.path.join(self.media.name, s.image.name)), s.common_name)

    def test_dq04_every_species_has_complete_botanical_details(self):
        for s in self.species:
            for field in ("light_need", "water_need", "suitable_soils", "ecological_role", "description"):
                self.assertTrue(getattr(s, field).strip(), f"{s.common_name}: {field}")
            self.assertIn(s.setting, ("INDOOR", "OUTDOOR", "BOTH"))
            self.assertGreater(s.price, 0)

    def test_dq05_names_are_unique(self):
        self.assertEqual(len({s.scientific_name for s in self.species}), 35)
        self.assertEqual(len({s.common_name for s in self.species}), 35)

    def test_dq06_demo_accounts_have_the_right_roles_and_usable_passwords(self):
        expected = {"admin@basera.test": User.Role.ADMIN, "seller@basera.test": User.Role.SELLER,
                    "customer@basera.test": User.Role.CUSTOMER}
        for email, role in expected.items():
            user = User.objects.get(email=email)
            self.assertEqual(user.role, role)
            self.assertTrue(user.has_usable_password())
        self.assertTrue(User.objects.get(email="admin@basera.test").is_superuser)

    def test_dq07_all_seeded_species_belong_to_the_demo_seller(self):
        seller = User.objects.get(email="seller@basera.test")
        self.assertTrue(all(s.seller_id == seller.pk for s in self.species))

    def test_dq08_running_it_again_changes_nothing(self):
        with override_settings(MEDIA_ROOT=self.media.name):
            before = (PlantSpecies.objects.count(), User.objects.count(), Region.objects.count())
            call_command("seed_catalog", stdout=StringIO())
        self.assertEqual(before, (PlantSpecies.objects.count(), User.objects.count(), Region.objects.count()))


@FAST
class CataloguePagingTests(TestCase):
    """DQ-09 to DQ-12: odd page numbers and empty searches."""

    def setUp(self):
        seller = User.objects.create_user("s@example.com", "x", full_name="Sam", role=User.Role.SELLER)
        PlantSpecies.objects.bulk_create([
            PlantSpecies(seller=seller, common_name=f"Plant {i:02d}", scientific_name=f"Plantus {i:02d}",
                         light_need="Full sun", water_need="Low", suitable_soils="Loam", setting="OUTDOOR",
                         price=100, stock_qty=1) for i in range(30)])

    def test_dq09_a_page_number_past_the_end_shows_the_last_page(self):
        page = self.client.get(reverse("catalogue"), {"page": 999})
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context["page"].number, 3)
        self.assertEqual(len(page.context["page"]), 6)  # 30 species, 12 per page

    def test_dq10_a_page_number_that_is_not_a_number_shows_the_first_page(self):
        self.assertEqual(self.client.get(reverse("catalogue"), {"page": "abc"}).context["page"].number, 1)

    def test_dq11_an_empty_or_blank_search_lists_everything(self):
        for term in ("", "   "):
            page = self.client.get(reverse("catalogue"), {"q": term})
            self.assertEqual(page.context["page"].paginator.count, 30)

    def test_dq12_search_ignores_extra_spaces_around_the_term(self):
        page = self.client.get(reverse("catalogue"), {"q": "  plant 07  "})
        self.assertEqual(page.context["page"].paginator.count, 1)
