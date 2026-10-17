from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from hotspots.tests import make_hotspot

from .models import Review


class ReviewIntegrityTests(TestCase):
    def test_rating_bounds_are_enforced_by_database(self):
        hotspot = make_hotspot()
        user = get_user_model().objects.create_user(username="alex")
        for rating in [0, 6]:
            with self.subTest(rating=rating), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Review.objects.create(hotspot=hotspot, author=user, rating=rating)


class DemoSeedTests(TestCase):
    @override_settings(DEMO_MODE=False)
    def test_seed_is_rejected_without_demo_mode(self):
        with self.assertRaisesMessage(CommandError, "DEMO_MODE=1"):
            call_command("seed_demo_reviews", stdout=StringIO())
        self.assertFalse(Review.objects.exists())
        self.assertFalse(get_user_model().objects.exists())

    @override_settings(DEMO_MODE=True)
    def test_seed_requires_official_hotspot(self):
        with self.assertRaisesMessage(CommandError, "Run import_hotspots first"):
            call_command("seed_demo_reviews", stdout=StringIO())
        self.assertFalse(get_user_model().objects.exists())

    @override_settings(DEMO_MODE=True)
    def test_seed_is_idempotent_and_explicitly_fictional(self):
        make_hotspot()
        for _ in range(2):
            call_command("seed_demo_reviews", stdout=StringIO())
        self.assertEqual(Review.objects.count(), 3)
        self.assertEqual(Review.objects.filter(is_demo=True).count(), 3)
        self.assertEqual(Review.objects.exclude(body="").count(), 2)
        self.assertEqual(get_user_model().objects.count(), 3)
        self.assertTrue(all(not user.has_usable_password() and not user.is_active for user in get_user_model().objects.all()))
