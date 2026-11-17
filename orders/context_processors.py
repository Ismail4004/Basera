"""Template context shared by every page."""

from django.db.models import Sum

from .models import CartItem


def cart(request):
    """Number of plants in the signed-in customer's cart (0 for everyone else).

    The header badge used to be a hard-coded 0; it now follows the cart rows so
    it stays right once the Add-to-cart story lands.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not getattr(user, "is_customer", False):
        return {"cart_count": 0}
    total = CartItem.objects.filter(user=user).aggregate(n=Sum("quantity"))["n"]
    return {"cart_count": total or 0}
