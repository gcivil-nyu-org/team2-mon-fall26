from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from hotspots.tests import make_hotspot

from .models import Review
from .services import rating_summary


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


@override_settings(DEMO_MODE=False)
class AverageRatingTests(TestCase):
    """US12 / #22: the sprint plan's deterministic average-rating sequence."""

    def setUp(self):
        self.hotspot = make_hotspot()
        self.other = make_hotspot(53, name="Clinton Hill Library", borough="Brooklyn")
        self.users = [get_user_model().objects.create_user(username=f"user{i}") for i in range(3)]

    def summary(self):
        return rating_summary(Review.objects.filter(hotspot=self.hotspot))

    def test_average_updates_after_additions_edits_and_deletions(self):
        first = Review.objects.create(hotspot=self.hotspot, author=self.users[0], rating=1, body="Slow")
        Review.objects.create(hotspot=self.hotspot, author=self.users[1], rating=3)
        Review.objects.create(hotspot=self.other, author=self.users[0], rating=5)
        self.assertEqual((self.summary()["average"], self.summary()["count"]), (2.0, 2))

        five = Review.objects.create(hotspot=self.hotspot, author=self.users[2], rating=5)
        self.assertEqual((self.summary()["average"], self.summary()["count"]), (3.0, 3))

        first.rating = 4
        first.save()
        self.assertEqual((self.summary()["average"], self.summary()["count"]), (4.0, 3))

        five.delete()
        self.assertEqual((self.summary()["average"], self.summary()["count"]), (3.5, 2))

        response = self.client.get(self.hotspot.get_absolute_url())
        self.assertEqual(response.context["rating_summary"]["average"], 3.5)
        record = next(
            item for item in self.client.get("/api/hotspots/").json()["hotspots"]
            if item["id"] == self.hotspot.pk
        )
        self.assertEqual((record["average_rating"], record["rating_count"]), (3.5, 2))

    def test_unrated_hotspot_shows_no_ratings_yet_instead_of_zero(self):
        summary = self.summary()
        self.assertIsNone(summary["average"])
        self.assertEqual(summary["count"], 0)
        response = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(response, "No ratings yet")
        record = self.client.get("/api/hotspots/").json()["hotspots"][0]
        self.assertIsNone(record["average_rating"])

    def test_average_is_rounded_to_one_decimal(self):
        for user, rating in zip(self.users, [5, 4, 4]):
            Review.objects.create(hotspot=self.hotspot, author=user, rating=rating)
        self.assertEqual(self.summary()["average"], 4.3)
