from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

User = get_user_model()

# The real PBKDF2 hasher takes seconds per hash; tests that are not about
# hashing use Django's fast test hasher (PasswordHashingTests uses the real one).
FAST_HASHERS = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


class PasswordHashingTests(TestCase):
    """Uses the project's real PASSWORD_HASHERS (Argon2 first)."""

    def test_old_pbkdf2_password_still_works_and_is_upgraded_to_argon2(self):
        from django.contrib.auth.hashers import PBKDF2PasswordHasher

        user = User.objects.create_user("old@example.com", None, full_name="Old Account")
        # Simulate an account created before the switch to Argon2.
        User.objects.filter(pk=user.pk).update(
            password=PBKDF2PasswordHasher().encode("old-Pass-123", PBKDF2PasswordHasher().salt())
        )
        self.assertEqual(authenticate(username="old@example.com", password="old-Pass-123"), user)
        user.refresh_from_db()
        self.assertTrue(user.password.startswith("argon2$"))

    def test_password_is_hashed_and_case_insensitive_login(self):
        user = User.objects.create_user("Ana@Example.com", "s3cret-Pass!", full_name="Ana Khan")
        user.refresh_from_db()
        self.assertNotEqual(user.password, "s3cret-Pass!")
        self.assertNotIn("s3cret-Pass!", user.password)
        self.assertTrue(user.password.startswith("argon2$"))
        self.assertTrue(user.check_password("s3cret-Pass!"))
        self.assertEqual(authenticate(username="  ANA@EXAMPLE.COM ", password="s3cret-Pass!"), user)


@FAST_HASHERS
class UserManagerTests(TestCase):
    def test_create_user_lowercases_and_strips_email(self):
        user = User.objects.create_user("  Ana.Khan@Example.COM ", "s3cret-Pass!", full_name="Ana Khan")
        self.assertEqual(user.email, "ana.khan@example.com")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_password_is_hashed(self):
        user = User.objects.create_user("ana@example.com", "s3cret-Pass!", full_name="Ana Khan")
        user.refresh_from_db()
        self.assertNotEqual(user.password, "s3cret-Pass!")
        self.assertNotIn("s3cret-Pass!", user.password)
        self.assertTrue(user.check_password("s3cret-Pass!"))
        self.assertFalse(user.check_password("wrong"))

    def test_authenticate_with_differently_cased_email(self):
        user = User.objects.create_user("Ana@Example.com", "s3cret-Pass!", full_name="Ana Khan")
        self.assertEqual(authenticate(username="  ANA@EXAMPLE.COM ", password="s3cret-Pass!"), user)
        self.assertIsNone(authenticate(username="ana@example.com", password="wrong"))

    def test_get_by_natural_key_normalises(self):
        user = User.objects.create_user("ana@example.com", "x", full_name="Ana Khan")
        self.assertEqual(User.objects.get_by_natural_key(" ANA@Example.COM "), user)

    def test_whitespace_only_email_rejected(self):
        for email in ("", "   ", None):
            with self.assertRaisesMessage(ValueError, "Users must have an email address."):
                User.objects.create_user(email, "s3cret-Pass!", full_name="Ana Khan")
        self.assertEqual(User.objects.count(), 0)

    def test_blank_full_name_rejected_by_manager(self):
        for name in ("", "   ", None):
            with self.assertRaisesMessage(ValueError, "Users must have a full name."):
                User.objects.create_user("ana@example.com", "s3cret-Pass!", full_name=name)
        with self.assertRaisesMessage(ValueError, "Users must have a full name."):
            User.objects.create_user("ana@example.com", "s3cret-Pass!")
        self.assertEqual(User.objects.count(), 0)

    def test_full_name_is_stripped(self):
        user = User.objects.create_user("ana@example.com", "x", full_name="  Ana Khan ")
        self.assertEqual(user.full_name, "Ana Khan")

    def test_create_superuser_is_admin(self):
        admin = User.objects.create_superuser("Admin@Basera.test", "adm1n-Pass!", full_name="Site Admin")
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(admin.is_staff)

    def test_create_superuser_rejects_non_admin_role(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser("a@basera.test", "x", full_name="A", role=User.Role.SELLER)
        with self.assertRaises(ValueError):
            User.objects.create_superuser("a@basera.test", "x", full_name="A", is_superuser=False)
        self.assertEqual(User.objects.count(), 0)


@FAST_HASHERS
class UserConstraintTests(TestCase):
    """Database-level constraints, bypassing Python-side normalisation."""

    def setUp(self):
        self.user = User.objects.create_user("ana@example.com", "s3cret-Pass!", full_name="Ana Khan")

    def test_duplicate_email_same_case(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("ana@example.com", "x", full_name="Dup")

    def test_duplicate_email_mixed_case_via_create_user(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("ANA@Example.Com", "x", full_name="Dup")

    def test_duplicate_email_differing_only_by_case_db_constraint(self):
        # bulk_create skips save(), so only the LOWER(email) unique index stops this.
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(email="ANA@EXAMPLE.COM", full_name="Dup", password="!")])
        self.assertEqual(User.objects.count(), 1)

    def test_empty_full_name_db_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(email="b@example.com", full_name="", password="!")])
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.user.pk).update(full_name="")

    def test_invalid_role_db_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.user.pk).update(role="GUEST")

    def test_superuser_must_be_admin_db_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.user.pk).update(is_superuser=True)  # role is CUSTOMER
        admin = User.objects.create_superuser("admin@basera.test", "x", full_name="Admin")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=admin.pk).update(role=User.Role.SELLER)
        # A non-superuser may have any valid role, including ADMIN.
        User.objects.filter(pk=self.user.pk).update(role=User.Role.ADMIN)
