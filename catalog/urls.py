from django.urls import path

from . import views

urlpatterns = [
    path("catalogue/", views.catalogue, name="catalogue"),
    path("species/<int:pk>/", views.species_detail, name="species_detail"),
]
