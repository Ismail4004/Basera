from django.contrib import admin

from .models import CartItem, Order, OrderItem


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("user", "species", "quantity", "added_at")
    search_fields = ("user__email", "species__common_name")
    list_select_related = ("user", "species")
    autocomplete_fields = ("user", "species")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ("species",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "payment_method", "total_amount", "city", "placed_at")
    list_filter = ("status", "payment_method")
    search_fields = ("user__email", "delivery_name", "city", "phone")
    list_select_related = ("user",)
    autocomplete_fields = ("user", "grow_profile")
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "species", "quantity", "unit_price")
    list_select_related = ("order", "species")
    autocomplete_fields = ("order", "species")
