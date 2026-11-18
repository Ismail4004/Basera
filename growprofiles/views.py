"""Grow profiles (US-06): describe a growing space, and list the ones you saved.

Profiles are private. Every query here is filtered to request.user, so another
customer's profile can't be seen or used (it answers 404, not 403, so its
existence isn't revealed).
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.ui import page_band

from matching.services import CRITERION_LABELS, WEIGHTS

from . import choices
from .forms import GrowProfileForm
from .models import GrowProfile


def customer_required(view):
    """Log in first; sellers and admins have no grow profiles, so send them home."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_customer:
            messages.error(request, "Grow profiles are for customer accounts.")
            return redirect("home")
        return view(request, *args, **kwargs)

    return wrapper


def describe(profile):
    """The profile's answers as readable labels, for the list and results pages."""
    return {
        "region": profile.region.name,
        "space": choices.label_for(choices.SPACE_TYPES, profile.space_type),
        "sunlight": choices.label_for(choices.SUNLIGHT, profile.sunlight),
        "soil": choices.label_for(choices.SOILS, profile.soil_type),
        "water": choices.label_for(choices.WATER, profile.water_availability) + " water",
        "purpose": choices.label_for(choices.PURPOSES, profile.purpose),
    }


@customer_required
def profile_list(request):
    profiles = list(GrowProfile.objects.filter(user=request.user).select_related("region"))
    for profile in profiles:
        profile.summary = describe(profile)
    context = {
        "profiles": profiles,
        **page_band(request, "My grow profiles", "Your saved spaces and the plants that match them.",
                    ("My grow profiles", None)),
    }
    return render(request, "growprofiles/profile_list.html", context)


@customer_required
def profile_create(request):
    if request.method == "POST":
        form = GrowProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.success(request, f"Saved “{profile.name}”. Your grow profile is ready.")
            return redirect("grow_profiles")
    else:
        form = GrowProfileForm()
    # The bars are drawn against 33 (the longest bar in the design is Sunlight's 30 points).
    weights = [{"label": CRITERION_LABELS[k], "points": w, "bar": round(w / 33 * 100)} for k, w in WEIGHTS.items()]
    context = {
        "form": form,
        "weights": weights,
        **page_band(request, "Create a grow profile", "Answer a few quick questions about your space.",
                    ("My grow profiles", reverse("grow_profiles")), ("New", None)),
    }
    return render(request, "growprofiles/profile_form.html", context)
