from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import LoginForm, SignUpForm


def _safe_next(request):
    """The ?next= page to return to after logging in, if it's on this site."""
    target = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                       require_https=request.is_secure()):
        return target
    return ""


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.user)
            return redirect(_safe_next(request) or "home")
    else:
        form = LoginForm(request)

    return render(request, "accounts/login.html", {"form": form, "next": _safe_next(request)})


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
            except IntegrityError:
                # Someone registered the same email between the check and the save.
                form.add_error("email", "An account with this email already exists.")
            else:
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                return redirect("home")
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You've been logged out.")
    return redirect("login")


@login_required
def home_view(request):
    # Placeholder until a teammate builds the real Home page.
    return render(request, "accounts/home.html")


class ForgotPasswordView(auth_views.PasswordResetView):
    """Emails a one-time reset link (printed in the terminal for now).

    Django only sends it if an active account with that email exists, but the
    page responds the same way either way, so it doesn't reveal who has an
    account.
    """

    template_name = "accounts/forgot_password.html"
    form_class = PasswordResetForm
    email_template_name = "accounts/emails/password_reset_email.txt"
    subject_template_name = "accounts/emails/password_reset_subject.txt"
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            "If there's an account with that email, we've sent a reset link. "
            "Check your inbox.",
        )
        return response


class ResetPasswordView(auth_views.PasswordResetConfirmView):
    """Page opened from the emailed link: choose a new password."""

    template_name = "accounts/reset_password.html"
    form_class = SetPasswordForm
    success_url = reverse_lazy("login")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Your password has been changed. Log in with your new password.")
        return response


def placeholder(request, page_name):
    """Simple stand-in page until the real one is built."""
    return render(request, "accounts/placeholder.html", {"page_name": page_name})
