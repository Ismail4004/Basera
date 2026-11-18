from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from accounts.ui import page_band

from .queries import search_species, visible_species

PAGE_SIZE = 12  # US-18: 12 species per page


def _viewer(user):
    """Who is looking: decides which buy button a species card shows."""
    if not user.is_authenticated:
        return "guest"
    return "customer" if user.is_customer else "other"


def catalogue(request):
    """US-18: browse and search the catalogue (works with or without HTMX)."""
    term = request.GET.get("q", "").strip()
    results = search_species(visible_species(), term).prefetch_related("regions")
    page = Paginator(results, PAGE_SIZE).get_page(request.GET.get("page"))
    context = {
        "page": page,
        "term": term,
        "viewer": _viewer(request.user),
        "total_visible": visible_species().count(),
        **page_band(request, "Catalogue", "Browse native plants for every kind of space.", ("Catalogue", None)),
    }
    # HTMX asks for just the results block; a normal visit gets the full page.
    template = "catalog/_results.html" if request.headers.get("HX-Request") else "catalog/catalogue.html"
    return render(request, template, context)


def species_detail(request, pk):
    """US-12 and US-10: one species. Inactive or missing species give a 404."""
    species = get_object_or_404(visible_species().select_related("seller"), pk=pk)
    regions = list(species.regions.all())
    # "You may also like" (or, for an invasive plant, "Native alternatives"):
    # other native, non-invasive species from the same regions.
    related = (
        visible_species()
        .filter(is_invasive=False, regions__in=regions)
        .exclude(pk=species.pk)
        .distinct()
        .order_by("common_name")[:4]
    )
    context = {
        "species": species,
        "regions": regions,
        "related": related,
        "viewer": _viewer(request.user),
        "in_stock": species.stock_qty > 0,
        "purchasable": (not species.is_invasive) and species.stock_qty > 0,
        **page_band(
            request,
            "Plant details",
            "Listed for awareness only. Not sold on Basera."
            if species.is_invasive else "Everything you need to know before you grow it.",
            ("Catalogue", reverse("catalogue")),
            (species.common_name, None),
        ),
    }
    return render(request, "catalog/species_detail.html", context)
