"""Real MySQL interleavings for simultaneous followed-hotspot updates."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event, Lock
from unittest.mock import patch

from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from accounts.tests import make_user
from availability.models import AvailabilityReport
from hotspots.tests import make_hotspot
from reviews.models import Review

from . import services
from .models import AvailabilityAlertState, Notification
from .tests import follow


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentNotificationTests(TransactionTestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.follower = make_user("follower")
        self.first_author = make_user("first")
        self.second_author = make_user("second")
        follow(self.follower, self.hotspot)

    def overlap(self, paused_method, first_action, second_action):
        """Let a second request run while the first is about to write.

        Each worker uses its own database connection. A correct implementation may
        block the second request on a row lock; both must finish after release.
        """
        paused, release = Event(), Event()
        guard = Lock()
        first_call = True
        original = getattr(services, paused_method)

        def delay_first(*args, **kwargs):
            nonlocal first_call
            with guard:
                should_pause = first_call
                first_call = False
            if should_pause:
                paused.set()
                if not release.wait(10):
                    raise AssertionError("The first request was not released")
            return original(*args, **kwargs)

        def worker(action):
            try:
                return action()
            finally:
                connections.close_all()

        with patch.object(services, paused_method, side_effect=delay_first):
            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(worker, first_action)
                try:
                    self.assertTrue(paused.wait(5), "First request did not reach pause")
                    second = executor.submit(worker, second_action)
                    try:
                        second.result(timeout=0.5)
                    except TimeoutError:
                        pass  # A serialized request waits for the first to commit.
                finally:
                    release.set()
                first.result(timeout=5)
                second.result(timeout=5)

    def test_simultaneous_reviews_share_one_unread_summary(self):
        first = Review.objects.create(
            hotspot=self.hotspot, author=self.first_author, rating=4
        )
        second = Review.objects.create(
            hotspot=self.hotspot, author=self.second_author, rating=5
        )
        self.overlap(
            "_create",
            lambda: services.review_published(first),
            lambda: services.review_published(second),
        )
        summaries = Notification.objects.filter(
            recipient=self.follower, kind=Notification.Kind.FOLLOWED_REVIEW
        )
        self.assertEqual(summaries.count(), 1)
        self.assertEqual(summaries.get().count, 2)

    def test_simultaneous_reports_send_one_outage_alert(self):
        AvailabilityAlertState.objects.create(hotspot=self.hotspot)
        for author in (self.first_author, self.second_author, make_user("third")):
            AvailabilityReport.objects.create(
                hotspot=self.hotspot, reporter=author, status="unavailable"
            )
        first, second = list(AvailabilityReport.objects.order_by("pk")[:2])
        self.overlap(
            "_alert_condition",
            lambda: services.availability_reported(first),
            lambda: services.availability_reported(second),
        )
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.follower, kind=Notification.Kind.AVAILABILITY_ALERT
            ).count(),
            1,
        )
