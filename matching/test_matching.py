"""US-08: scoring and the ranked shortlist."""

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from catalog.models import PlantSpecies, Region, SpeciesRegion
from growprofiles.models import GrowProfile

from . import services, vocabulary

FAST_HASHERS = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


class Base(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Punjab Plains")
        self.other_region = Region.objects.create(name="Northern Highlands")
        self.seller = User.objects.create_user("s@example.com", "x", full_name="Sam", role=User.Role.SELLER)
        self.customer = User.objects.create_user("c@example.com", "x", full_name="Cy Khan")
        self.profile = GrowProfile.objects.create(
            user=self.customer, region=self.region, name="Backyard", space_type="OUTDOOR", sunlight="FULL_SUN",
            soil_type="LOAM", water_availability="MEDIUM", purpose="SHADE_COOLING")

    def species(self, name, regions=None, **kw):
        fields = dict(seller=self.seller, common_name=name, scientific_name=f"{name} sp.", light_need="Full sun",
                      water_need="Medium", suitable_soils="Loam", setting="OUTDOOR", price=100, stock_qty=5,
                      ecological_role="Gives dense shade.")
        fields.update(kw)
        s = PlantSpecies.objects.create(**fields)
        for region in regions if regions is not None else [self.region]:
            SpeciesRegion.objects.create(species=s, region=region)
        return s


class VocabularyTests(TestCase):
    def test_text_is_read_into_codes(self):
        self.assertEqual(vocabulary.sun_level("Full sun"), 2)
        self.assertEqual(vocabulary.sun_level("Partial shade"), 1)
        self.assertEqual(vocabulary.sun_level("Shade"), 0)
        self.assertIsNone(vocabulary.sun_level("???"))
        self.assertEqual((vocabulary.water_level("Low"), vocabulary.water_level("High")), (0, 2))
        self.assertEqual(vocabulary.soil_codes("Loam, Sandy"), {"LOAM", "SANDY"})


class ScoreTests(Base):
    def points(self, species):
        return {c.key: c.points for c in services.score_species(self.profile, species)}

    def test_a_perfect_species_scores_100(self):
        s = self.species("Neem")
        self.assertEqual(round(sum(self.points(s).values())), 100)

    def test_sunlight_is_30_points_and_loses_half_per_step(self):
        self.assertEqual(self.points(self.species("A", light_need="Full sun"))["sunlight"], 30)
        self.assertEqual(self.points(self.species("B", light_need="Partial shade"))["sunlight"], 15)
        self.assertEqual(self.points(self.species("C", light_need="Shade"))["sunlight"], 0)

    def test_water_is_20_points_with_the_same_formula(self):
        self.assertEqual(self.points(self.species("A", water_need="Medium"))["water"], 20)
        self.assertEqual(self.points(self.species("B", water_need="Low"))["water"], 10)
        self.assertEqual(self.points(self.species("C", water_need="High"))["water"], 10)
        self.profile.water_availability = "LOW"
        self.assertEqual(self.points(self.species("D", water_need="High"))["water"], 0)

    def test_soil_exact_is_25_loam_is_adaptable_for_half_otherwise_0(self):
        self.profile.soil_type = "SANDY"
        self.assertEqual(self.points(self.species("A", suitable_soils="Sandy"))["soil"], 25)
        self.assertEqual(self.points(self.species("B", suitable_soils="Loam"))["soil"], 12.5)
        self.assertEqual(self.points(self.species("C", suitable_soils="Clay"))["soil"], 0)

    def test_indoor_outdoor_is_15_and_both_always_fits(self):
        self.assertEqual(self.points(self.species("A", setting="OUTDOOR"))["setting"], 15)
        self.assertEqual(self.points(self.species("B", setting="BOTH"))["setting"], 15)
        self.assertEqual(self.points(self.species("C", setting="INDOOR"))["setting"], 0)

    def test_purpose_is_10_points_when_the_plant_serves_it(self):
        self.assertEqual(self.points(self.species("A", ecological_role="Gives dense shade."))["purpose"], 10)
        self.assertEqual(self.points(self.species("B", ecological_role="Feeds bees.", description=""))["purpose"], 0)


class RankTests(Base):
    def test_only_native_active_non_invasive_species_are_candidates(self):
        keep = self.species("Keep")
        self.species("Elsewhere", regions=[self.other_region])
        self.species("Invasive", is_invasive=True)
        self.species("Hidden", is_active=False)
        self.assertEqual([m.species for m in services.rank(self.profile)], [keep])

    def test_sorted_by_score_then_name_and_out_of_stock_is_kept(self):
        self.species("Zed")
        self.species("Alder")
        weak = self.species("Weak", light_need="Shade", water_need="High", suitable_soils="Clay", setting="INDOOR",
                            ecological_role="Feeds bees.")
        sold_out = self.species("Gone", stock_qty=0)
        ranked = services.rank(self.profile)
        self.assertEqual([m.species.common_name for m in ranked], ["Alder", "Gone", "Zed", "Weak"])
        self.assertFalse(ranked[1].in_stock)
        self.assertEqual(ranked[-1].species, weak)
        self.assertLess(ranked[-1].score, 40)
        self.assertEqual((ranked[0].tier, ranked[-1].tier), ("great", "low"))
        self.assertEqual(sold_out.stock_qty, 0)

    def test_a_species_in_two_regions_appears_once(self):
        self.species("Both", regions=[self.region, self.other_region])
        self.assertEqual(len(services.rank(self.profile)), 1)


@FAST_HASHERS
class MatchPageTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.customer)

    def url(self, profile=None):
        return reverse("match_profile", args=[(profile or self.profile).pk])

    def test_lists_ranked_cards_with_score_price_stock_and_details_link(self):
        a = self.species("Neem", price=450, stock_qty=24)
        self.species("Gone", stock_qty=0)
        page = self.client.get(self.url())
        self.assertContains(page, "2 native plants match your space")
        self.assertContains(page, "100%")
        self.assertContains(page, "Rs 450")
        self.assertContains(page, "In stock · 24 available")
        self.assertContains(page, reverse("species_detail", args=[a.pk]))
        self.assertContains(page, "Out of stock")
        self.assertContains(page, reverse("cart_add", args=[a.pk]))

    def test_out_of_stock_plants_have_no_add_to_cart(self):
        gone = self.species("Gone", stock_qty=0)
        self.assertNotContains(self.client.get(self.url()), reverse("cart_add", args=[gone.pk]))

    def test_opens_on_the_top_five_and_show_all_lists_the_rest(self):
        for i in range(8):
            self.species(f"Plant {i}")
        self.assertContains(self.client.get(self.url()), "Showing the top 5 of 8 matches")
        self.assertEqual(len(self.client.get(self.url()).context["matches"]), 5)
        self.assertEqual(len(self.client.get(self.url() + "?all=1").context["matches"]), 8)

    def test_someone_elses_profile_is_a_404(self):
        other = User.objects.create_user("o@example.com", "x", full_name="Olu")
        theirs = GrowProfile.objects.create(user=other, region=self.region, name="Theirs", space_type="INDOOR",
                                            sunlight="SHADE", soil_type="CLAY", water_availability="LOW",
                                            purpose="FOOD")
        self.assertEqual(self.client.get(self.url(theirs)).status_code, 404)

    def test_the_header_link_goes_to_the_newest_profile_or_the_list(self):
        self.assertRedirects(self.client.get(reverse("match_results")), self.url())
        GrowProfile.objects.all().delete()
        self.assertRedirects(self.client.get(reverse("match_results")), reverse("grow_profiles"))

    def test_the_list_page_links_to_find_plants(self):
        self.assertContains(self.client.get(reverse("grow_profiles")), self.url())

    def test_logged_out_visitors_are_sent_to_log_in(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url()).status_code, 302)
