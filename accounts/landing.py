"""Numbers and lists shown on the three landing pages (customer, seller, admin).

Everything is read through the ORM. Where the design shows something the database
cannot give yet (store ratings, seller applications, support requests), the page
shows the nearest real figure instead; see the comments below.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone

from catalog.models import PlantSpecies, Region
from catalog.queries import visible_species
from orders.models import Order, OrderItem

from .models import User

LOW_STOCK_AT = 5  # "low stock" means 1 to 5 left
COUNTED = ~Q(order__status=Order.Status.CANCELLED)
LINE_TOTAL = ExpressionWrapper(F("unit_price") * F("quantity"), output_field=DecimalField(max_digits=12, decimal_places=2))


def _month_start(now):
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def pkr(amount):
    """'PKR 24,850' from a number (None counts as 0)."""
    return f"PKR {int(amount or 0):,}"


def customer_context():
    """Five featured plants: native, in stock, cheapest-first among the newest."""
    featured = visible_species().filter(is_invasive=False, stock_qty__gt=0).order_by("-created_at")[:5]
    return {"featured": featured}


def seller_context(user):
    now = timezone.now()
    mine = PlantSpecies.objects.filter(seller=user)
    active = mine.filter(is_active=True)
    lines = OrderItem.objects.filter(species__seller=user)

    revenue = (
        lines.filter(COUNTED, order__placed_at__gte=_month_start(now)).aggregate(t=Sum(LINE_TOTAL))["t"] or Decimal(0)
    )
    to_fulfil = Order.objects.filter(
        items__species__seller=user, status__in=[Order.Status.PENDING, Order.Status.CONFIRMED]
    ).distinct()

    recent = []
    orders = (
        Order.objects.filter(items__species__seller=user)
        .distinct()
        .select_related("user")
        .prefetch_related("items__species")[:4]
    )
    for order in orders:
        mine_items = [i for i in order.items.all() if i.species.seller_id == user.pk]
        recent.append({
            "ref": f"#BS{order.pk}",
            "customer": order.delivery_name or order.user.full_name,
            "plants": ", ".join(f"{i.species.common_name} × {i.quantity}" for i in mine_items),
            "total": pkr(sum(i.unit_price * i.quantity for i in mine_items)),
            "status": order.get_status_display(),
            "tone": {"PENDING": "warn", "CONFIRMED": "warn", "SHIPPED": "ok", "DELIVERED": "ok"}.get(order.status, "muted"),
        })

    low = active.filter(stock_qty__lte=LOW_STOCK_AT).order_by("stock_qty", "common_name")[:3]
    counts = active.aggregate(
        outdoor=Count("pk", filter=Q(setting=PlantSpecies.Setting.OUTDOOR)),
        indoor=Count("pk", filter=Q(setting=PlantSpecies.Setting.INDOOR)),
        both=Count("pk", filter=Q(setting=PlantSpecies.Setting.BOTH)),
        low=Count("pk", filter=Q(stock_qty__gt=0, stock_qty__lte=LOW_STOCK_AT)),
        out=Count("pk", filter=Q(stock_qty=0)),
    )
    total = active.count()
    stats = [
        {"label": "Outdoor", "n": counts["outdoor"]},
        {"label": "Indoor", "n": counts["indoor"]},
        {"label": "Both", "n": counts["both"]},
        {"label": "Low stock", "n": counts["low"]},
        {"label": "Out of stock", "n": counts["out"]},
    ]
    for s in stats:
        s["pct"] = round(100 * s["n"] / total) if total else 0

    return {
        "month_label": now.strftime("%B %Y"),
        "revenue": pkr(revenue),
        "to_fulfil": to_fulfil.count(),
        "active_count": total,
        "region_count": Region.objects.filter(species_regions__species__in=active).distinct().count(),
        # There is no ratings model yet, so the fourth tile shows customers served.
        "customers_served": Order.objects.filter(items__species__seller=user).values("user").distinct().count(),
        "recent_orders": recent,
        "low_stock": low,
        "plant_stats": stats,
    }


def admin_context():
    now = timezone.now()
    start = _month_start(now)
    month_orders = Order.objects.filter(placed_at__gte=start).exclude(status=Order.Status.CANCELLED)
    sales = month_orders.aggregate(t=Sum("total_amount"))["t"] or Decimal(0)

    # Order value in four slices of the month (days 1-7, 8-14, 15-21, 22-end).
    slices = [(1, 7), (8, 14), (15, 21), (22, 31)]
    weeks, peak = [], Decimal(1)
    for first, last in slices:
        total = sum(o.total_amount for o in month_orders if first <= timezone.localtime(o.placed_at).day <= last)
        weeks.append({"label": f"{first:02d}–{last:02d} {now.strftime('%b')}" if last < 31 else f"{first}–end {now.strftime('%b')}",
                      "total": total, "text": pkr(total)})
        peak = max(peak, total)
    for w in weeks:
        w["pct"] = max(int(100 * w["total"] / peak), 3) if w["total"] else 3

    sellers = User.objects.filter(role=User.Role.SELLER)
    region_rows = list(
        Region.objects.annotate(n=Count("species_regions", filter=Q(species_regions__species__is_active=True)))
        .order_by("-n", "name")
    )
    top = max([r.n for r in region_rows] + [1])
    for r in region_rows:
        r.pct = round(100 * r.n / top)

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "month_label": now.strftime("%B %Y"),
        "sales": pkr(sales),
        "orders_placed": month_orders.count(),
        "active_growers": sellers.filter(is_active=True).count(),
        "waiting_growers": sellers.filter(is_active=False).count(),
        "homes": User.objects.filter(role=User.Role.CUSTOMER, is_active=True).count(),
        "new_homes": User.objects.filter(role=User.Role.CUSTOMER, date_joined__gte=start).count(),
        "weeks": weeks,
        # No application workflow or support inbox exists yet, so these are the
        # real figures closest to the design's three "attention" tiles.
        "attention": [
            {"n": sellers.filter(is_active=False).count(), "label": "Sellers awaiting approval", "link": "Review growers"},
            {"n": PlantSpecies.objects.filter(is_invasive=True, is_active=True).count(), "label": "Invasive listings to check", "link": "Review catalogue"},
            {"n": PlantSpecies.objects.filter(is_active=False).count(), "label": "Hidden plant listings", "link": "Open listings"},
        ],
        "new_growers": sellers.annotate(plants=Count("listings")).order_by("-date_joined")[:3],
        "regions": region_rows,
        "listing_count": PlantSpecies.objects.filter(is_active=True).count(),
        "region_total": len(region_rows),
        "new_plants_today": PlantSpecies.objects.filter(created_at__gte=today).count(),
        "delivered": Order.objects.filter(status=Order.Status.DELIVERED).count(),
        "new_homes_today": User.objects.filter(role=User.Role.CUSTOMER, date_joined__gte=today).count(),
    }
