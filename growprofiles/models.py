"""
Grow profiles: the ERD's GrowProfile entity (docs/database/erd_transcription.md).
"""

from django.conf import settings
from django.db import models


class GrowProfile(models.Model):
    # CASCADE: a grow profile belongs to exactly one user and is private to them.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="grow_profiles",
    )
    # PROTECT: reference data; a region in use by profiles cannot be deleted.
    region = models.ForeignKey(
        "catalog.Region",
        on_delete=models.PROTECT,
        related_name="grow_profiles",
    )
    name = models.CharField(max_length=100)
    space_type = models.CharField(max_length=50)
    sunlight = models.CharField(max_length=50)
    soil_type = models.CharField(max_length=50)
    water_availability = models.CharField(max_length=50)
    purpose = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name} ({self.user})"
