"""Seed the catalogue (EN-02): regions, demo accounts and the 35 starter species.

Safe to run more than once: anything that already exists is left alone, and a
photo file that has gone missing (for example on a host that wipes its disk when
it restarts) is put back.

    python manage.py seed_catalog

With SEED_DEMO_ACCOUNTS=False (production) no demo admin or customer is created
and no shared password is printed. The plants still need an owner, so a seller
account with NO usable password is created: nobody can log in as it. To get a real
admin, set ADMIN_EMAIL and ADMIN_PASSWORD (and optionally ADMIN_NAME) before running.
"""

import os
import secrets
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
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
            # Also repairs a photo whose file has disappeared from the disk.
            missing = not species.image or not species.image.storage.exists(species.image.name)
            if missing and photo.exists():
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
        if not settings.SEED_DEMO_ACCOUNTS:
            self._real_admin()
            return self._nursery_owner()
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

    def _nursery_owner(self):
        """The seller that owns the starter plants in production (cannot be logged into)."""
        email = DEMO_ACCOUNTS[1][0]
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                email, None, full_name=os.environ.get("NURSERY_NAME") or "Basera Nursery", role=User.Role.SELLER
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])
            self.stdout.write(f"Created the nursery account {email} (no password: it cannot be logged into).")
        return user

    def _real_admin(self):
        """Create the site's admin from ADMIN_EMAIL / ADMIN_PASSWORD, if given and not there yet."""
        email = (os.environ.get("ADMIN_EMAIL") or "").strip()
        password = os.environ.get("ADMIN_PASSWORD") or ""
        if not email or not password:
            return
        if User.objects.filter(email__iexact=email).exists():
            return
        try:
            password_validation.validate_password(password)
        except ValidationError as error:
            raise CommandError("ADMIN_PASSWORD is not strong enough: " + " ".join(error.messages))
        User.objects.create_superuser(email, password, full_name=os.environ.get("ADMIN_NAME") or "Basera Admin")
        self.stdout.write(f"Created the admin account {email}.")
