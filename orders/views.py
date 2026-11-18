"""The cart (US-19): add a plant, change how many, take it out again.

One CartItem row per species — the model enforces UNIQUE(user, species) — so
adding a plant that is already in the cart raises its quantity instead of
creating a second line. Stock is the ceiling everywhere: a line never holds
more plants than the listing has, and invasive or out-of-stock listings never
enter the cart at all.

Every change is a POST. Without JavaScript it stores a Django message and
redirects back; the HTMX version answers with a fragment that swaps the cart
body in place, and reports what happened through an HX-Trigger event that the
page turns into a toast, so nothing reloads either way.
"""

import json
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.ui import page_band
from catalog.queries import visible_species

from .models import CartItem


def _is_htmx(request):
    """True for the in-place requests the cart buttons send."""
    return request.headers.get("HX-Request") == "true"


def _notify(request, level, text):
    """Queue one line of feedback for whichever way this request is answered."""
    if _is_htmx(request):
        notices = getattr(request, "_cart_notices", [])
        notices.append({"message": text, "level": level})
        request._cart_notices = notices
    else:
        getattr(messages, level)(request, text)


def _back(request, fallback):
    """Return to the page the form came from, if it is on this site."""
    target = request.POST.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback


def _refuse_non_customers(request):
    """Only customers shop here: sellers and admins own or run the shop."""
    if request.user.is_customer:
        return None
    _notify(request, "error", "Only customer accounts can shop on Basera.")
    if _is_htmx(request):
        return _finish(request, None, fragment="orders/_cart_toast.html")
    return redirect("home")


def requires_customer(view):
    """login_required + customer-only, in a shape HTMX understands.

    A plain redirect would make HTMX swap the login page into the cart, so an
    expired session answers with HX-Redirect instead and the browser navigates.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if _is_htmx(request):
                response = HttpResponse(status=204)
                response["HX-Redirect"] = f"{reverse('login')}?next={request.get_full_path()}"
                return response
            return redirect_to_login(request.get_full_path())
        refused = _refuse_non_customers(request)
        if refused is not None:
            return refused
        return view(request, *args, **kwargs)

    return wrapper


def _cart_lines(user):
    """The cart as the templates want it: one dict per line, plus the totals."""
    items = (
        CartItem.objects.filter(user=user)
        .select_related("species", "species__seller")
        .order_by("added_at")
    )
    lines, subtotal = [], Decimal("0.00")
    for item in items:
        species = item.species
        line_total = species.price * item.quantity
        subtotal += line_total
        lines.append(
            {
                "species": species,
                "quantity": item.quantity,
                "line_total": line_total,
                # A listing can sell out or be withdrawn while it sits in a cart.
                "unavailable": species.stock_qty < 1 or species.is_invasive or not species.is_active,
                "at_limit": item.quantity >= species.stock_qty,
            }
        )
    return lines, subtotal, sum(line["quantity"] for line in lines)


def _finish(request, back, *, fragment="orders/_cart_response.html"):
    """Answer the request: a fragment in place for HTMX, a redirect otherwise."""
    if not _is_htmx(request):
        return redirect(back)

    if fragment == "orders/_cart_response.html":
        lines, subtotal, plant_count = _cart_lines(request.user)
        context = {"lines": lines, "subtotal": subtotal, "plant_count": plant_count}
    else:
        context = {}
    response = render(request, fragment, context)

    notices = getattr(request, "_cart_notices", None)
    if notices:
        # htmx turns this into an event the page listens for (see botanical.js).
        response["HX-Trigger"] = json.dumps({"cart:notice": notices[0]})
    return response


def _requested_quantity(request):
    """The quantity posted with an Add-to-cart form, 1 when missing or odd."""
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        return 1
    return max(1, quantity)


@requires_customer
def cart_view(request):
    """The cart page: every line, what it costs, and what is left in stock."""
    lines, subtotal, plant_count = _cart_lines(request.user)
    context = {
        "lines": lines,
        "subtotal": subtotal,
        "plant_count": plant_count,
        **page_band(
            request,
            "Your cart",
            "Plants waiting for your patch.",
            ("Catalogue", reverse("catalogue")),
            ("Cart", None),
        ),
    }
    return render(request, "orders/cart.html", context)


@requires_customer
@require_POST
def add_to_cart(request, pk):
    """Add one plant (or raise its quantity) and go back where we came from."""
    species = get_object_or_404(visible_species(), pk=pk)
    back = _back(request, reverse("species_detail", args=[species.pk]))

    if species.is_invasive:
        _notify(request, "error", f"{species.common_name} is invasive, so Basera doesn't sell it.")
        return _finish(request, back, fragment="orders/_cart_toast.html")
    if species.stock_qty < 1:
        _notify(request, "error", f"{species.common_name} is out of stock right now.")
        return _finish(request, back, fragment="orders/_cart_toast.html")

    quantity = _requested_quantity(request)

    with transaction.atomic():
        clamped = quantity > species.stock_qty
        item, created = CartItem.objects.get_or_create(
            user=request.user,
            species=species,
            defaults={"quantity": min(quantity, species.stock_qty)},
        )
        if created:
            if clamped:
                _notify(
                    request,
                    "success",
                    f"{species.common_name}: {species.stock_qty} in your cart — that's all that's left in stock.",
                )
            else:
                _notify(request, "success", f"{species.common_name} is in your cart.")
        else:
            previous = item.quantity
            wanted = min(previous + quantity, species.stock_qty)
            if wanted <= previous:
                # Either the cart already holds every plant in stock, or the
                # listing was reduced after it went in: never quietly lower it.
                if previous > species.stock_qty:
                    _notify(
                        request,
                        "info",
                        f"Only {species.stock_qty} of the {species.common_name} are left in stock.",
                    )
                else:
                    _notify(
                        request,
                        "info",
                        f"All {species.stock_qty} of the {species.common_name} in stock are already in your cart.",
                    )
                return _finish(request, back, fragment="orders/_cart_toast.html")
            item.quantity = wanted
            item.save(update_fields=["quantity"])
            if previous + quantity > species.stock_qty:
                _notify(
                    request,
                    "success",
                    f"{species.common_name}: {wanted} in your cart — that's all that's left in stock.",
                )
            else:
                _notify(request, "success", f"{species.common_name}: {wanted} in your cart.")

    return _finish(request, back, fragment="orders/_cart_toast.html")


@requires_customer
@require_POST
def update_cart(request, pk):
    """Set a line's quantity, or move it by ±1 from the cart page stepper."""
    species = get_object_or_404(visible_species(), pk=pk)
    item = get_object_or_404(CartItem, user=request.user, species=species)
    back = _back(request, reverse("cart"))

    if species.stock_qty < 1:
        _notify(request, "error", f"{species.common_name} is out of stock, so it can't be increased.")
        return _finish(request, back)

    if "quantity" in request.POST:
        try:
            target = int(request.POST["quantity"])
        except (TypeError, ValueError):
            _notify(request, "error", "That quantity doesn't look right. Try again.")
            return _finish(request, back)
    else:
        try:
            delta = int(request.POST.get("delta", 0))
        except (TypeError, ValueError):
            delta = 0
        target = item.quantity + delta

    target = max(1, min(target, species.stock_qty))

    if target == item.quantity:
        if target == species.stock_qty:
            _notify(request, "info", f"There are only {species.stock_qty} of the {species.common_name} in stock.")
        return _finish(request, back)

    item.quantity = target
    item.save(update_fields=["quantity"])
    # The stepper already shows the new number, so only speak up elsewhere.
    if not _is_htmx(request):
        _notify(request, "success", f"{species.common_name}: {target} in your cart.")
    return _finish(request, back)


@requires_customer
@require_POST
def remove_from_cart(request, pk):
    """Take a plant out of the cart."""
    item = CartItem.objects.filter(user=request.user, species_id=pk).select_related("species").first()
    back = _back(request, reverse("cart"))

    if item is None:
        _notify(request, "info", "That plant wasn't in your cart.")
        return _finish(request, back)

    name = item.species.common_name
    item.delete()
    _notify(request, "success", f"{name} removed from your cart.")
    return _finish(request, back)
