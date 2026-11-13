from django import forms
from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError

from .models import User


class SignUpForm(forms.Form):
    """Sign-up page (Figma "Create account").

    Only Customer or Seller can be chosen here. Admin accounts are never
    self-selected: they are created with `manage.py createsuperuser`, or an
    existing admin changes a user's role in the admin site ("Manage User
    Accounts" in the proposal's use case diagram).
    """

    SIGNUP_ROLES = [
        (User.Role.CUSTOMER, "Customer"),
        (User.Role.SELLER, "Seller"),
    ]

    full_name = forms.CharField(
        max_length=150,
        error_messages={"required": "Please enter your name."},
    )
    email = forms.EmailField(
        max_length=254,
        error_messages={
            "required": "Please enter your email.",
            "invalid": "Please enter a valid email, like you@example.com.",
        },
    )
    password = forms.CharField(
        strip=False,
        error_messages={"required": "Please choose a password."},
    )
    role = forms.ChoiceField(
        choices=SIGNUP_ROLES,
        initial=User.Role.CUSTOMER,
        error_messages={
            "required": "Please choose an account type.",
            "invalid_choice": "Please choose Customer or Seller.",
        },
    )

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if not name:
            raise ValidationError("Please enter your name.")
        return name

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.", code="duplicate")
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            # Runs the project's validators (8+ characters, not too common,
            # not all numbers, not too similar to the name or email).
            probe = User(email=cleaned.get("email", ""), full_name=cleaned.get("full_name", ""))
            try:
                password_validation.validate_password(password, user=probe)
            except ValidationError as error:
                self.add_error("password", error)
        return cleaned

    def save(self):
        data = self.cleaned_data
        return User.objects.create_user(
            email=data["email"],
            password=data["password"],
            full_name=data["full_name"],
            role=data["role"],
        )


class LoginForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        error_messages={
            "required": "Please enter your email.",
            "invalid": "Please enter a valid email, like you@example.com.",
        },
    )
    password = forms.CharField(strip=False, error_messages={"required": "Please enter your password."})

    error_messages = {
        # Same message whether the email or the password is wrong, so the form
        # doesn't reveal which emails have accounts.
        "invalid_login": "That email and password don't match. Please try again.",
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email, password = cleaned.get("email"), cleaned.get("password")
        if email and password:
            # authenticate() also refuses deactivated accounts (is_active=False).
            self.user = authenticate(self.request, username=email, password=password)
            if self.user is None:
                raise ValidationError(self.error_messages["invalid_login"], code="invalid_login")
        return cleaned
