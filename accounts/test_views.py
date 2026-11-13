"""Tests for the sign-up, log in, log out, home and password reset pages."""

import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .tests import FAST_HASHERS

User = get_user_model()
GOOD_PASSWORD = "moss-garden-42"


@FAST_HASHERS
class SignUpViewTests(TestCase):
    url = reverse("signup")

    def post(self, **overrides):
        data = {"full_name": "Ana Khan", "email": "Ana@Example.com",
                "password": GOOD_PASSWORD, "role": "CUSTOMER"}
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_page_has_role_choice_with_customer_selected(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('value="CUSTOMER" checked', html)
        self.assertIn('value="SELLER"', html)
        self.assertNotIn('value="ADMIN"', html)

    def test_creates_customer_logs_in_and_goes_home(self):
        response = self.post()
        self.assertRedirects(response, reverse("home"))
        user = User.objects.get()
        self.assertEqual(user.email, "ana@example.com")
        self.assertEqual(user.full_name, "Ana Khan")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertTrue(user.check_password(GOOD_PASSWORD))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_creates_seller(self):
        self.post(role="SELLER")
        self.assertEqual(User.objects.get().role, User.Role.SELLER)

    def test_cannot_sign_up_as_admin(self):
        response = self.post(role="ADMIN")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())
        self.assertContains(response, "Please choose Customer or Seller.")

    def test_duplicate_email_any_case_is_rejected(self):
        User.objects.create_user("ana@example.com", GOOD_PASSWORD, full_name="Ana")
        response = self.post(email="  ANA@example.COM ")
        self.assertContains(response, "An account with this email already exists.")
        self.assertContains(response, "Log in instead")
        self.assertEqual(User.objects.count(), 1)

    def test_weak_password_is_rejected_with_reason(self):
        response = self.post(password="short")
        self.assertContains(response, "at least 8 characters")
        self.assertFalse(User.objects.exists())

    def test_password_similar_to_name_is_rejected(self):
        response = self.post(full_name="Gardenia Moss", password="gardeniamoss")
        self.assertContains(response, "too similar")
        self.assertFalse(User.objects.exists())

    def test_blank_fields_show_errors_and_keep_values(self):
        response = self.post(full_name="   ", password="")
        self.assertContains(response, "Please enter your name.")
        self.assertContains(response, "Please choose a password.")
        self.assertContains(response, 'value="Ana@Example.com"')
        self.assertFalse(User.objects.exists())

    def test_password_never_echoed_back(self):
        response = self.post(email="not-an-email")
        self.assertNotContains(response, GOOD_PASSWORD)


@FAST_HASHERS
class LoginLogoutViewTests(TestCase):
    url = reverse("login")

    def setUp(self):
        self.user = User.objects.create_user("ana@example.com", GOOD_PASSWORD, full_name="Ana Khan")

    def test_login_with_any_email_case_goes_home(self):
        response = self.client.post(self.url, {"email": " ANA@example.com", "password": GOOD_PASSWORD})
        self.assertRedirects(response, reverse("home"))
        home = self.client.get(reverse("home"))
        self.assertContains(home, "Hi, Ana.")
        self.assertContains(home, "Customer")

    def test_wrong_password_shows_one_generic_error(self):
        response = self.client.post(self.url, {"email": "ana@example.com", "password": "nope-nope"})
        self.assertContains(response, "That email and password don&#x27;t match.")
        self.assertContains(response, 'value="ana@example.com"')
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_email_gets_the_same_error(self):
        response = self.client.post(self.url, {"email": "who@example.com", "password": GOOD_PASSWORD})
        self.assertContains(response, "That email and password don&#x27;t match.")

    def test_deactivated_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(self.url, {"email": "ana@example.com", "password": GOOD_PASSWORD})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(response.status_code, 200)

    def test_home_requires_login_and_returns_after(self):
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, f"{self.url}?next=/home/")
        response = self.client.post(self.url, {"email": "ana@example.com", "password": GOOD_PASSWORD, "next": "/home/"})
        self.assertRedirects(response, "/home/")

    def test_next_to_another_site_is_ignored(self):
        response = self.client.post(self.url, {"email": "ana@example.com", "password": GOOD_PASSWORD,
                                               "next": "https://evil.example.com/"})
        self.assertRedirects(response, reverse("home"))

    def test_logout_needs_post_and_shows_message(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        response = self.client.post(reverse("logout"), follow=True)
        self.assertRedirects(response, self.url)
        self.assertContains(response, "You&#x27;ve been logged out.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logged_in_user_skips_login_and_signup(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(self.url), reverse("home"))
        self.assertRedirects(self.client.get(reverse("signup")), reverse("home"))


@FAST_HASHERS
class PasswordResetViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana@example.com", GOOD_PASSWORD, full_name="Ana Khan")

    def request_link(self, email):
        return self.client.post(reverse("forgot_password"), {"email": email}, follow=True)

    def test_known_email_gets_link_and_can_reset(self):
        response = self.request_link("ANA@example.com")
        self.assertRedirects(response, reverse("login"))
        self.assertContains(response, "we&#x27;ve sent a reset link")
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["ana@example.com"])
        self.assertEqual(message.subject, "Reset your Basera password")

        link = re.search(r"http://testserver(/reset/\S+/)", message.body).group(1)
        page = self.client.get(link, follow=True)
        self.assertContains(page, "Set a new password")
        set_url = page.redirect_chain[-1][0]

        mismatch = self.client.post(set_url, {"new_password1": "fern-valley-77", "new_password2": "other-77-x"})
        self.assertContains(mismatch, "didn’t match")

        done = self.client.post(set_url, {"new_password1": "fern-valley-77", "new_password2": "fern-valley-77"}, follow=True)
        self.assertRedirects(done, reverse("login"))
        self.assertContains(done, "Your password has been changed.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("fern-valley-77"))

        # The link only works once.
        again = self.client.get(link, follow=True)
        self.assertContains(again, "Link expired")

    def test_unknown_email_looks_the_same_but_sends_nothing(self):
        response = self.request_link("nobody@example.com")
        self.assertRedirects(response, reverse("login"))
        self.assertContains(response, "we&#x27;ve sent a reset link")
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_email_shows_error(self):
        response = self.client.post(reverse("forgot_password"), {"email": "not-an-email"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "basera-error")

    def test_bad_link_shows_expired(self):
        response = self.client.get("/reset/Mg/bad-token/", follow=True)
        self.assertContains(response, "Link expired")
