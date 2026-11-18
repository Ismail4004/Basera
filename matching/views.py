"""US-08: the ranked shortlist for one grow profile."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.ui import page_band
from growprofiles.models import GrowProfile
from growprofiles.views import customer_required, describe

from . import services

SHORTLIST = 5  # the page opens on the top five; "Show all" lists the rest


@customer_required
def match_latest(request):
    """The "Match Results" header link: the newest profile's matches, or the list."""
    profile = GrowProfile.objects.filter(user=request.user).first()
    if profile is None:
        messages.info(request, "Create a grow profile first, then Basera can match plants to it.")
        return redirect("grow_profiles")
    return redirect("match_profile", pk=profile.pk)


@customer_required
def match_profile(request, pk):
    # Filtering by user makes someone else's profile a 404 (never a hint it exists).
    profile = get_object_or_404(GrowProfile.objects.select_related("region"), pk=pk, user=request.user)
    matches = services.rank(profile)
    show_all = request.GET.get("all") == "1"
    has_fit = any(m.score >= services.LOW_FIT for m in matches)
    context = {
        "profile": profile,
        "summary": describe(profile),
        "total": len(matches),
        "matches": matches if show_all else matches[:SHORTLIST],
        "show_all": show_all,
        "has_fit": has_fit,
        # US-10: when nothing fits well, say which answer to relax and where else plants grow.
        "hints": [] if has_fit else services.relaxing_hints(matches),
        "other_regions": [] if has_fit else services.other_regions(profile),
        "viewer": "customer",
        **page_band(request, "Your matches", f"Native plants ranked for your {profile.name} profile.",
                    ("My grow profiles", reverse("grow_profiles")), (profile.name, None), ("Matches", None)),
    }
    return render(request, "matching/match_results.html", context)
