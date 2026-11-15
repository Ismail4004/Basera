"""Seed the catalogue (EN-02): regions, demo accounts and the 35 starter species.

Safe to run more than once: anything that already exists is left alone.

    python manage.py seed_catalog
"""

import secrets
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import PlantSpecies, Region, SpeciesRegion
from catalog.seed_data import REGIONS, SPECIES

User = get_user_model()
SEED_IMAGES = settings.BASE_DIR / "catalog" / "seed_images"

DEMO_ACCOUNTS = [
    ("admin@basera.test", "Demo Admin", User.Role.ADMIN),
    ("seller@basera.test", "Demo Nursery", User.Role.SELLER),
    ("customer@basera.test", "Demo Customer", User.Role.CUSTOMER),
]


class Command(BaseCommand):
    help = "Create the regions, demo accounts and 35 starter species (skips what already exists)."

    @transaction.atomic
    def handle(self, *args, **options):
        regions = self._regions()
        seller = self._demo_accounts()
        created = 0
        for (image, common, scientific, region_codes, light, water, soil, setting,
             invasive, price, stock, role, description) in SPECIES:
            species, was_created = PlantSpecies.objects.get_or_create(
                common_name=common,
                scientific_name=scientific,
                defaults=dict(
                    seller=seller, description=description, light_need=light,
                    water_need=water, suitable_soils=soil, setting=setting,
                    ecological_role=role, is_invasive=invasive,
                    price=Decimal(price), stock_qty=stock,
                ),
            )
            if was_created:
                created += 1
            for code in region_codes.split():
                SpeciesRegion.objects.get_or_create(species=species, region=regions[code])
            photo = SEED_IMAGES / f"{image}.jpg"
            if not species.image and photo.exists():
                with photo.open("rb") as fh:
                    species.image.save(f"{image}.jpg", File(fh), save=True)
        self.stdout.write(self.style.SUCCESS(
            f"Catalogue ready: {PlantSpecies.objects.count()} species ({created} new), "
            f"{Region.objects.count()} regions."
        ))

    def _regions(self):
        regions = {}
        for code, (name, description, climate) in REGIONS.items():
            regions[code], _ = Region.objects.get_or_create(
                name=name, defaults={"description": description, "climate_zone": climate}
            )
        return regions

    def _demo_accounts(self):
        seller = None
        for email, full_name, role in DEMO_ACCOUNTS:
            user = User.objects.filter(email=email).first()
            if user is None:
                password = secrets.token_urlsafe(10)
                if role == User.Role.ADMIN:
                    user = User.objects.create_superuser(email, password, full_name=full_name)
                else:
                    user = User.objects.create_user(email, password, full_name=full_name, role=role)
                self.stdout.write(f"Created {email} with password: {password}")
            if role == User.Role.SELLER:
                seller = user
        return seller
