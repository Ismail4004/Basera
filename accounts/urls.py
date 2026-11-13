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
]
