"""Shared queries so every public page agrees on what a visitor may see."""

from django.db.models import Q

from .models import PlantSpecies


def visible_species():
    """Species a visitor may see: active listings only (inactive ones never appear)."""
    return PlantSpecies.objects.filter(is_active=True)


def search_species(queryset, term):
    """Case-insensitive match on the common or the scientific name."""
    term = (term or "").strip()
    if not term:
        return queryset
    return queryset.filter(Q(common_name__icontains=term) | Q(scientific_name__icontains=term))
