from django.contrib import admin

from .models import GrowProfile


@admin.register(GrowProfile)
class GrowProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "region", "space_type", "sunlight", "soil_type", "updated_at")
    list_filter = ("region",)
    search_fields = ("name", "user__email")
    list_select_related = ("user", "region")
    autocomplete_fields = ("user",)
