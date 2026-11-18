from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from catalog.models import PlantSpecies

from .models import CartItem, Order, OrderItem

User = get_user_model()

# The real PBKDF2 hasher takes seconds per hash; tests that are not about
# hashing use Django's fast test hasher (PasswordHashingTests uses the real one).
FAST_HASHERS = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


@FAST_HASHERS
class OrdersConstraintTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user("ana@example.com", "x", full_name="Ana Khan")
        seller = User.objects.create_user(
            "seller@basera.test", "x", full_name="Sam Seller", role=User.Role.SELLER
        )
        self.species = PlantSpecies.objects.create(
            seller=seller, common_name="Neem", scientific_name="Azadirachta indica",
            light_need="Full sun", water_need="Low", suitable_soils="Loam",
            setting=PlantSpecies.Setting.OUTDOOR, price=Decimal("250.00"), stock_qty=5,
        )
        self.order = Order.objects.create(
            user=self.customer, delivery_name="Ana Khan", delivery_address="1 Street",
            city="Lahore", phone="0300", total_amount=Decimal("500.00"),
        )

    def test_order_defaults(self):
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertEqual(self.order.payment_method, Order.PaymentMethod.COD)
        self.assertIsNone(self.order.grow_profile)

    def test_cart_quantity_at_least_one(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CartItem.objects.create(user=self.customer, species=self.species, quantity=0)

    def test_cart_user_species_unique(self):
        CartItem.objects.create(user=self.customer, species=self.species, quantity=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CartItem.objects.create(user=self.customer, species=self.species, quantity=2)

    def test_order_item_quantity_at_least_one(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(
                order=self.order, species=self.species, quantity=0, unit_price=Decimal("1.00")
            )

    def test_order_item_unit_price_not_negative(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(
                order=self.order, species=self.species, quantity=1, unit_price=Decimal("-1.00")
            )

    def test_order_item_order_species_unique(self):
        OrderItem.objects.create(order=self.order, species=self.species, quantity=1, unit_price=Decimal("250.00"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(
                order=self.order, species=self.species, quantity=2, unit_price=Decimal("250.00")
            )

    def test_order_total_not_negative(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.filter(pk=self.order.pk).update(total_amount=Decimal("-0.01"))
