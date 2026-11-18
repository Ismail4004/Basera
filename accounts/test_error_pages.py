"""The branded error pages (Figma "404 error" and "403 error")."""

from django.core.exceptions import PermissionDenied
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.views import defaults
from django.views.csrf import csrf_failure

from accounts.models import User

FAST = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


@FAST
class ErrorPageTests(TestCase):
    def test_ep01_a_missing_page_shows_the_branded_404_with_two_ways_out(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        for text in ("Page not found", "404", "Back to home", "Browse catalogue"):
            self.assertContains(response, text, status_code=404)
        self.assertContains(response, reverse("catalogue"), status_code=404)
        self.assertTemplateUsed(response, "404.html")

    def test_ep02_the_404_page_keeps_the_site_header_and_footer(self):
        response = self.client.get("/no-such-page/")
        self.assertContains(response, 'class="bt-header', status_code=404)
        self.assertContains(response, "Terms of Service", status_code=404)

    def test_ep03_the_404_page_works_when_logged_in(self):
        user = User.objects.create_user("c@example.com", "x", full_name="Cy Khan")
        self.client.force_login(user)
        self.assertContains(self.client.get("/no-such-page/"), "Page not found", status_code=404)

    def test_ep04_access_denied_shows_the_branded_403(self):
        request = RequestFactory().get("/somewhere/")
        request.user = User.objects.create_user("a@example.com", "x", full_name="Ada Lee")
        from django.contrib.messages.storage.fallback import FallbackStorage
        request.session = {}
        request._messages = FallbackStorage(request)
        response = defaults.permission_denied(request, PermissionDenied())
        self.assertEqual(response.status_code, 403)
        self.assertIn("Access denied", response.content.decode())
        self.assertIn("Log in", response.content.decode())

    def test_ep05_a_form_without_a_valid_token_shows_a_friendly_403(self):
        from django.test import Client
        strict = Client(enforce_csrf_checks=True)
        response = strict.post("/", {"email": "x@example.com", "password": "y"})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Please try again", status_code=403)
        self.assertTemplateUsed(response, "403_csrf.html")

    def test_ep06_the_500_page_is_plain_html_that_needs_no_context(self):
        html = render_to_string("500.html")
        self.assertIn("Something went wrong", html)
        self.assertNotIn("{%", html)
