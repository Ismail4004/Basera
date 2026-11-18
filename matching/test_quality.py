"""Matching quality cases (test-case section A14): score limits, speed and the cart link."""

import itertools
import time
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from catalog.models import PlantSpecies, Region, SpeciesRegion
from growprofiles import choices
from growprofiles.models import GrowProfile

from . import services

FAST = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


@FAST
class MatchingQualityTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user("c@example.com", "x", full_name="Cy Khan")

    def profile(self, region, **answers):
        data = dict(space_type="OUTDOOR", sunlight="FULL_SUN", soil_type="LOAM", water_availability="MEDIUM",
                    purpose="SHADE_COOLING")
        data.update(answers)
        return GrowProfile.objects.create(user=self.customer, region=region, name="t", **data)

    def test_mq01_every_possible_profile_gets_scores_between_0_and_100_in_order(self):
        with override_settings(MEDIA_ROOT="/tmp/basera-test-media"):
            call_command("seed_catalog", stdout=StringIO())
        region = Region.objects.get(name="Punjab Plains")
        invasive = set(PlantSpecies.objects.filter(is_invasive=True).values_list("pk", flat=True))
        answers = itertools.product(
            [c for c, *_ in choices.SPACE_TYPES], [c for c, *_ in choices.SUNLIGHT], [c for c, *_ in choices.SOILS],
            [c for c, *_ in choices.WATER], [c for c, *_ in choices.PURPOSES])
        checked = 0
        for space, sun, soil, water, purpose in answers:
            p = self.profile(region, space_type=space, sunlight=sun, soil_type=soil, water_availability=water,
                             purpose=purpose)
            ranked = services.rank(p)
            scores = [m.score for m in ranked]
            self.assertTrue(all(0 <= s <= 100 for s in scores))
            self.assertEqual(scores, sorted(scores, reverse=True))
            self.assertFalse({m.species.pk for m in ranked} & invasive)
            checked += 1
        self.assertEqual(checked, 2 * 3 * 4 * 3 * 6)  # all 432 combinations

    def test_mq02_five_hundred_species_are_ranked_in_under_two_seconds_with_one_query(self):
        seller = User.objects.create_user("s@example.com", "x", full_name="Sam", role=User.Role.SELLER)
        region = Region.objects.create(name="Punjab Plains")
        PlantSpecies.objects.bulk_create([
            PlantSpecies(seller=seller, common_name=f"Plant {i:03d}", scientific_name=f"Plantus {i}",
                         light_need=("Full sun", "Partial shade", "Shade")[i % 3], water_need=("Low", "Medium", "High")[i % 3],
                         suitable_soils=("Loam", "Sandy", "Clay", "Rocky")[i % 4], setting=("OUTDOOR", "INDOOR", "BOTH")[i % 3],
                         ecological_role="Gives shade." if i % 2 else "Feeds bees.", price=100 + i, stock_qty=i % 7)
            for i in range(500)])
        SpeciesRegion.objects.bulk_create([SpeciesRegion(species=s, region=region) for s in PlantSpecies.objects.all()])
        profile = self.profile(region)
        with self.assertNumQueries(1):
            start = time.perf_counter()
            ranked = services.rank(profile)
            elapsed = time.perf_counter() - start
        self.assertEqual(len(ranked), 500)
        self.assertLess(elapsed, 2.0, f"took {elapsed:.2f}s")

    def test_mq03_the_match_page_itself_stays_fast_with_five_hundred_species(self):
        seller = User.objects.create_user("s@example.com", "x", full_name="Sam", role=User.Role.SELLER)
        region = Region.objects.create(name="Punjab Plains")
        PlantSpecies.objects.bulk_create([
            PlantSpecies(seller=seller, common_name=f"Plant {i:03d}", scientific_name=f"Plantus {i}", light_need="Full sun",
                         water_need="Medium", suitable_soils="Loam", setting="OUTDOOR", ecological_role="Gives shade.",
                         price=100, stock_qty=3) for i in range(500)])
        SpeciesRegion.objects.bulk_create([SpeciesRegion(species=s, region=region) for s in PlantSpecies.objects.all()])
        profile = self.profile(region)
        self.client.force_login(self.customer)
        start = time.perf_counter()
        response = self.client.get(reverse("match_profile", args=[profile.pk]) + "?all=1")
        elapsed = time.perf_counter() - start
        self.assertEqual(response.status_code, 200)
        self.assertLess(elapsed, 2.0, f"took {elapsed:.2f}s")

    def test_mq04_add_to_cart_from_the_match_page_returns_to_the_match_page(self):
        seller = User.objects.create_user("s@example.com", "x", full_name="Sam", role=User.Role.SELLER)
        region = Region.objects.create(name="Punjab Plains")
        species = PlantSpecies.objects.create(seller=seller, common_name="Neem", scientific_name="A i",
                                              light_need="Full sun", water_need="Medium", suitable_soils="Loam",
                                              setting="OUTDOOR", price=450, stock_qty=5, ecological_role="Shade.")
        SpeciesRegion.objects.create(species=species, region=region)
        profile = self.profile(region)
        self.client.force_login(self.customer)
        match_url = reverse("match_profile", args=[profile.pk])
        response = self.client.post(reverse("cart_add", args=[species.pk]), {"next": match_url})
        self.assertRedirects(response, match_url)
        from orders.models import CartItem
        self.assertEqual(CartItem.objects.get().species, species)
