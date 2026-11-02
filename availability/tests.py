from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from hotspots.tests import make_hotspot
from reviews.models import Review
from reviews.services import rating_summary

from .models import AvailabilityReport
from .services import (
    MIN_REPORTS,
    REPORT_WINDOW_DAYS,
    availability_by_hotspot,
    hotspot_availability,
)

WORKING = AvailabilityReport.Status.WORKING
UNAVAILABLE = AvailabilityReport.Status.UNAVAILABLE


def make_users(count):
    return [
        get_user_model().objects.create_user(username=f"reporter{i}")
        for i in range(count)
    ]


def report(hotspot, user, status, days_ago=0):
    return AvailabilityReport.objects.create(
        hotspot=hotspot,
        reporter=user,
        status=status,
        created_at=timezone.now() - timedelta(days=days_ago),
    )


@override_settings(DEMO_MODE=False)
class SubmitReportTests(TestCase):
    """US22 / #32: report Working or Unavailable."""

    def setUp(self):
        self.hotspot = make_hotspot()
        self.url = reverse("availability:report", args=[self.hotspot.pk])
        self.user = make_users(1)[0]

    def test_visitor_is_sent_to_log_in_and_nothing_is_saved(self):
        response = self.client.post(self.url, {"status": "working"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertFalse(AvailabilityReport.objects.exists())

    def test_contributor_report_is_saved_with_source_and_timestamp(self):
        self.client.force_login(self.user)
        before = timezone.now()
        response = self.client.post(self.url, {"status": "unavailable"})
        self.assertRedirects(
            response,
            f"{self.hotspot.get_absolute_url()}#availability",
            fetch_redirect_response=False,
        )
        saved = AvailabilityReport.objects.get()
        self.assertEqual(
            (saved.hotspot, saved.reporter, saved.status),
            (self.hotspot, self.user, UNAVAILABLE),
        )
        self.assertGreaterEqual(saved.created_at, before)

    def test_only_working_or_unavailable_are_accepted(self):
        self.client.force_login(self.user)
        for value in ["", "maybe", "WORKING"]:
            with self.subTest(value=value):
                self.client.post(self.url, {"status": value})
        self.assertFalse(AvailabilityReport.objects.exists())

    def test_reports_must_be_posted_and_need_an_active_hotspot(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.hotspot.is_active = False
        self.hotspot.save()
        self.assertEqual(
            self.client.post(self.url, {"status": "working"}).status_code, 404
        )
        self.assertFalse(AvailabilityReport.objects.exists())

    def test_reports_are_kept_separate_from_ratings(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {"status": "working"})
        self.assertFalse(Review.objects.exists())
        self.assertEqual(rating_summary(Review.objects.all())["count"], 0)
        Review.objects.create(hotspot=self.hotspot, author=self.user, rating=2)
        self.assertEqual(AvailabilityReport.objects.count(), 1)
        self.assertEqual(rating_summary(Review.objects.all())["average"], 2.0)


@override_settings(DEMO_MODE=False)
class ReliabilityRulesTests(TestCase):
    """US23 / #33: the reliability score and report recency."""

    def setUp(self):
        self.hotspot = make_hotspot()
        self.users = make_users(5)

    def test_no_score_until_enough_different_people_report(self):
        report(self.hotspot, self.users[0], WORKING)
        report(self.hotspot, self.users[1], WORKING)
        summary = hotspot_availability(self.hotspot)
        self.assertEqual(
            (MIN_REPORTS, summary["report_count"], summary["score"]), (3, 2, None)
        )
        self.assertFalse(summary["has_enough"])

    def test_score_is_share_of_working_reports(self):
        report(self.hotspot, self.users[0], WORKING)
        report(self.hotspot, self.users[1], WORKING)
        report(self.hotspot, self.users[2], UNAVAILABLE)
        self.assertEqual(hotspot_availability(self.hotspot)["score"], 67)

    def test_one_person_cannot_count_more_than_once(self):
        for _ in range(3):
            report(self.hotspot, self.users[0], WORKING)
        self.assertEqual(hotspot_availability(self.hotspot)["report_count"], 1)

    def test_a_newer_report_replaces_the_same_persons_older_one(self):
        report(self.hotspot, self.users[0], WORKING, days_ago=5)
        report(self.hotspot, self.users[0], UNAVAILABLE, days_ago=1)
        summary = hotspot_availability(self.hotspot)
        self.assertEqual(
            (summary["working_count"], summary["unavailable_count"]), (0, 1)
        )

    def test_reports_expire_after_the_window(self):
        report(self.hotspot, self.users[0], WORKING, days_ago=REPORT_WINDOW_DAYS + 1)
        report(self.hotspot, self.users[1], WORKING, days_ago=REPORT_WINDOW_DAYS - 1)
        self.assertEqual(hotspot_availability(self.hotspot)["report_count"], 1)

    def test_reports_do_not_leak_between_hotspots(self):
        other = make_hotspot(53, name="Clinton Hill Library", borough="Brooklyn")
        report(other, self.users[0], WORKING)
        self.assertEqual(hotspot_availability(self.hotspot)["report_count"], 0)
        self.assertEqual(
            availability_by_hotspot([self.hotspot.pk, other.pk])[other.pk][
                "report_count"
            ],
            1,
        )

    def test_profile_shows_score_time_source_and_the_community_note(self):
        for user, status in zip(self.users[:3], [WORKING, WORKING, UNAVAILABLE]):
            report(self.hotspot, user, status)
        page = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(page, "67%")
        self.assertContains(page, "reporter0")
        self.assertContains(
            page, "community observations, not a guarantee of live connectivity"
        )
        self.assertContains(page, "Log in to report")

    def test_profile_without_enough_reports_says_so(self):
        page = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(page, "Not enough reports yet")
        self.assertNotContains(page, "% of recent reports")

    def test_signed_in_contributor_sees_report_buttons_and_their_latest_report(self):
        self.client.force_login(self.users[0])
        report(self.hotspot, self.users[0], UNAVAILABLE)
        page = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(page, 'value="working"')
        self.assertContains(page, "Your latest report: <strong>Unavailable</strong>")


@override_settings(DEMO_MODE=False)
class SortTests(TestCase):
    """US24 / #34: sort results by rating or reliability."""

    def setUp(self):
        self.a = make_hotspot(1, name="A Library", borough="Manhattan")
        self.b = make_hotspot(2, name="B Park", borough="Manhattan")
        self.c = make_hotspot(3, name="C Kiosk", borough="Manhattan")
        self.d = make_hotspot(4, name="D Plaza", borough="Brooklyn")
        self.users = make_users(3)

    def names(self, **params):
        data = self.client.get(reverse("hotspots:data"), params).json()
        return [item["name"] for item in data["hotspots"]]

    def test_default_order_is_unchanged(self):
        self.assertEqual(self.names(), ["D Plaza", "A Library", "B Park", "C Kiosk"])

    def test_sort_by_rating_puts_best_first_and_unrated_last(self):
        for user in self.users:
            Review.objects.create(hotspot=self.c, author=user, rating=5)
        Review.objects.create(hotspot=self.a, author=self.users[0], rating=3)
        self.assertEqual(
            self.names(sort="rating"), ["C Kiosk", "A Library", "D Plaza", "B Park"]
        )

    def test_sort_by_reliability_puts_most_reliable_first_and_thin_data_last(self):
        for user, status in zip(self.users, [WORKING, WORKING, WORKING]):
            report(self.b, user, status)
        for user, status in zip(self.users, [WORKING, UNAVAILABLE, UNAVAILABLE]):
            report(self.a, user, status)
        report(self.c, self.users[0], WORKING)  # one report is not enough for a score
        self.assertEqual(
            self.names(sort="reliability"),
            ["B Park", "A Library", "D Plaza", "C Kiosk"],
        )

    def test_sorting_works_together_with_filters(self):
        for user in self.users:
            report(self.a, user, UNAVAILABLE)
            report(self.b, user, WORKING)
            report(self.d, user, WORKING)
        self.assertEqual(
            self.names(sort="reliability", borough="Manhattan"),
            ["B Park", "A Library", "C Kiosk"],
        )

    def test_unknown_sort_is_ignored(self):
        self.assertEqual(self.names(sort="bogus"), self.names())

    def test_map_page_offers_sorting_without_counting_it_as_a_filter(self):
        page = self.client.get(reverse("hotspots:map"), {"sort": "reliability"})
        self.assertContains(page, 'id="filter-sort"')
        self.assertContains(page, '<option value="reliability" selected>')
        self.assertFalse(page.context["is_filtered"])
        self.assertEqual(page.context["filter_chips"], [])
