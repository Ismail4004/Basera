from django.contrib import admin

from .models import PlantSpecies, Region, SpeciesRegion


class SpeciesRegionInline(admin.TabularInline):
    model = SpeciesRegion
    extra = 1


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "climate_zone")
    search_fields = ("name", "climate_zone")


@admin.register(PlantSpecies)
class PlantSpeciesAdmin(admin.ModelAdmin):
    list_display = ("common_name", "scientific_name", "seller", "setting", "price", "stock_qty", "is_invasive", "is_active")
    list_filter = ("setting", "is_invasive", "is_active", "regions")
    search_fields = ("common_name", "scientific_name")
    list_select_related = ("seller",)
    autocomplete_fields = ("seller",)
    inlines = [SpeciesRegionInline]


@admin.register(SpeciesRegion)
class SpeciesRegionAdmin(admin.ModelAdmin):
    list_display = ("species", "region")
    list_filter = ("region",)
    list_select_related = ("species", "region")
