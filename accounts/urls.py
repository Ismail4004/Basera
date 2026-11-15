from django.urls import path

from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("signup/", views.signup_view, name="signup"),
    path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset/<uidb64>/<token>/", views.ResetPasswordView.as_view(), name="password_reset_confirm"),
    path("home/", views.home_view, name="home"),
    path("privacy/", views.placeholder, {"page_name": "Privacy"}, name="privacy"),
    path("terms/", views.placeholder, {"page_name": "Terms"}, name="terms"),
    path("help/", views.placeholder, {"page_name": "Help"}, name="help"),
    # Header links to pages that later stories build; replace these when they exist.
    path("profiles/", views.coming_soon, {"page_name": "My Grow Profiles"}, name="grow_profiles"),
    path("matches/", views.coming_soon, {"page_name": "Match Results"}, name="match_results"),
    path("about/", views.coming_soon, {"page_name": "About"}, name="about"),
    path("cart/", views.coming_soon, {"page_name": "Cart"}, name="cart"),
    path("seller/listings/", views.coming_soon, {"page_name": "My Listings"}, name="seller_listings"),
]
