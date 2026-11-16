"""Small helpers for the shared page shell (accounts/site_base.html)."""

from django.urls import reverse


def page_band(request, title, subtitle="", *trail):
    """Context for the illustrated header band: breadcrumb trail, title, subtitle.

    `trail` is a series of (label, url) pairs after "Home"; the last one is
    shown as the current page (pass url=None for it).
    """
    home = reverse("home") if request.user.is_authenticated else reverse("login")
    return {
        "band_title": title,
        "band_sub": subtitle,
        "crumbs": [("Home", home), *trail],
    }
