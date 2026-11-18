from django.urls import path

from . import views

urlpatterns = [
    path("matches/", views.match_latest, name="match_results"),
    path("match/<int:pk>/", views.match_profile, name="match_profile"),
]
