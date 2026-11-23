"""The Settings page: notification categories and the light/dark theme."""

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from hotspots.models import HotspotFollow
from hotspots.tests import make_hotspot
from moderation import services as moderation
from moderation.models import ContentFlag, Reason
from moderation.registry import REVIEW
from notifications import services as notify
from notifications.models import Notification, NotificationPreference
from reviews.models import Review

from .models import UserSettings, theme_for
from .tests import make_administrator, make_user

Kind = Notification.Kind
ALL_ON = {
    "followed_reviews": "on",
    "followed_availability": "on",
    "followed_availability_alerts": "on",
    "followed_discussions": "on",
    "review_replies": "on",
    "flag_outcomes": "on",
}


class SettingsPageTests(TestCase):
    def setUp(self):
        self.user = make_user("sam")
        self.url = reverse("accounts:settings")

    def test_visitor_is_sent_to_log_in(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_page_lists_every_category_and_theme(self):
        self.client.force_login(self.user)
        page = self.client.get(self.url)
        for text in (
            "New ratings and reviews on hotspots I follow",
            "New availability reports on hotspots I follow",
            "Alerts when a hotspot I follow may be down",
            "New discussions about hotspots I follow",
            "Replies to my reviews",
            "Outcomes of content I flagged",
            "Match my device",
            "Dark",
            "Always sent",
        ):
            self.assertContains(page, text)
        self.assertContains(page, 'data-theme="system"')

    def test_saving_switches_off_one_category_and_sets_dark_mode(self):
        self.client.force_login(self.user)
        data = {**ALL_ON, "theme": "dark"}
        del data["followed_reviews"]
        response = self.client.post(self.url, data)
        self.assertRedirects(response, self.url)
        preference = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(preference.followed_reviews)
        self.assertTrue(preference.followed_discussions)
        self.assertEqual(theme_for(self.user), UserSettings.Theme.DARK)
        # The theme is applied to every page for this user.
        self.assertContains(
            self.client.get(reverse("hotspots:map")), 'data-theme="dark"'
        )

    def test_invalid_theme_saves_nothing(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {**ALL_ON, "theme": "neon"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserSettings.objects.exists())
        self.assertFalse(NotificationPreference.objects.exists())

    def test_header_toggle_sets_theme_and_returns_to_page(self):
        self.client.force_login(self.user)
        hotspot = make_hotspot()
        response = self.client.post(
            reverse("accounts:set_theme"),
            {"theme": "dark", "next": hotspot.get_absolute_url()},
        )
        self.assertRedirects(
            response, hotspot.get_absolute_url(), fetch_redirect_response=False
        )
        self.assertEqual(UserSettings.objects.get(user=self.user).theme, "dark")
        self.client.post(reverse("accounts:set_theme"), {"theme": "light"})
        self.assertEqual(UserSettings.objects.get(user=self.user).theme, "light")
        response = self.client.post(
            reverse("accounts:set_theme"),
            {"theme": "light", "next": "https://evil.example/"},
        )
        self.assertEqual(response["Location"], self.url)

    def test_header_toggle_requires_post_and_sign_in(self):
        self.assertEqual(
            self.client.post(
                reverse("accounts:set_theme"), {"theme": "dark"}
            ).status_code,
            302,
        )
        self.assertFalse(UserSettings.objects.exists())
        self.client.force_login(self.user)
        self.assertEqual(
            self.client.get(reverse("accounts:set_theme")).status_code, 405
        )

    def test_visitors_follow_their_device(self):
        page = self.client.get(reverse("hotspots:map"))
        self.assertContains(page, 'data-theme="system"')
        self.assertNotContains(page, "data-theme-toggle")


class NotificationCategoryTests(TestCase):
    """Switching a category off stops exactly that kind of notification."""

    def setUp(self):
        self.hotspot = make_hotspot()
        self.follower = make_user("follower")
        HotspotFollow.objects.create(user=self.follower, hotspot=self.hotspot)
        self.client.force_login(self.follower)

    def save(self, **off):
        data = {**ALL_ON, "theme": "system"}
        for name in off:
            data.pop(name)
        self.client.post(reverse("accounts:settings"), data)

    def test_followed_reviews_off_stops_review_summaries_only(self):
        self.save(followed_reviews=False)
        review = Review.objects.create(
            hotspot=self.hotspot, author=make_user("writer"), rating=5, body="Great."
        )
        notify.review_published(review)
        notify.hotspot_retired(self.hotspot)
        kinds = set(
            Notification.objects.filter(recipient=self.follower).values_list(
                "kind", flat=True
            )
        )
        self.assertEqual(kinds, {Kind.FOLLOWED_RETIRED})

    def test_flag_outcomes_off_stops_flag_notices(self):
        self.save(flag_outcomes=False)
        review = Review.objects.create(
            hotspot=self.hotspot, author=make_user("writer"), rating=1, body="Spam."
        )
        ContentFlag.objects.create(
            content_type=ContentType.objects.get_for_model(Review),
            object_id=review.pk,
            flagged_by=self.follower,
            reason=Reason.SPAM,
        )
        moderation.remove_content(REVIEW, review, make_administrator(), Reason.SPAM)
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.follower, kind=Kind.FLAG_RESOLVED
            ).exists()
        )
        self.assertTrue(Notification.objects.filter(kind=Kind.REVIEW_REMOVED).exists())
