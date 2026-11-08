"""E07 US27 (#37): notifications for followed hotspots and moderation decisions."""

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from accounts.tests import make_administrator, make_user
from availability.models import AvailabilityReport
from forum.models import ForumPost
from hotspots.models import HotspotFollow
from hotspots.tests import make_hotspot
from moderation import services as moderation
from moderation.models import ContentFlag, Reason
from moderation.registry import REVIEW
from reviews.models import Review

from . import services
from .models import Notification, NotificationPreference

Kind = Notification.Kind


def follow(user, hotspot):
    return HotspotFollow.objects.create(user=user, hotspot=hotspot)


def flag(review, user, reason=Reason.SPAM):
    return ContentFlag.objects.create(
        content_type=ContentType.objects.get_for_model(Review),
        object_id=review.pk,
        flagged_by=user,
        reason=reason,
    )


def inbox(user):
    return Notification.objects.filter(recipient=user)


class FollowedHotspotTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.follower = make_user("follower")
        self.other = make_user("other")
        self.author = make_user("author")
        follow(self.follower, self.hotspot)

    def post_review(self, user, rating="4", body="Fast and reliable connection."):
        self.client.force_login(user)
        return self.client.post(
            reverse("reviews:create", args=[self.hotspot.pk]),
            {"rating": rating, "body": body},
        )

    def test_new_review_notifies_followers_only(self):
        self.post_review(self.author)
        review = Review.objects.get(author=self.author)
        notification = inbox(self.follower).get()
        self.assertEqual(notification.kind, Kind.FOLLOWED_REVIEW)
        self.assertEqual(notification.object_id, review.pk)
        self.assertEqual(
            notification.text, "author rated Bryant Park 4/5 and wrote a review."
        )
        self.assertFalse(inbox(self.other).exists())
        self.assertFalse(inbox(self.author).exists())

    def test_rating_only_review_notifies_and_opens_reviews_section(self):
        self.post_review(self.author, body="")
        notification = inbox(self.follower).get()
        self.assertEqual(notification.text, "author rated Bryant Park 4/5.")
        self.client.force_login(self.follower)
        response = self.client.get(
            reverse("notifications:open", args=[notification.pk])
        )
        self.assertRedirects(
            response,
            f"{self.hotspot.get_absolute_url()}#reviews",
            fetch_redirect_response=False,
        )

    def test_followers_do_not_hear_about_their_own_review(self):
        self.post_review(self.follower)
        self.assertFalse(inbox(self.follower).exists())

    def test_editing_a_review_does_not_notify(self):
        self.post_review(self.author)
        inbox(self.follower).delete()
        review = Review.objects.get(author=self.author)
        self.client.post(
            reverse("reviews:edit", args=[review.pk]),
            {"rating": "2", "body": "Slower this week than before."},
        )
        self.assertFalse(inbox(self.follower).exists())

    def test_held_review_notifies_followers_only_after_approval(self):
        self.post_review(self.author, body="Use promo code SAVE10 for a discount")
        review = Review.objects.get(author=self.author)
        self.assertTrue(review.is_held)
        self.assertFalse(inbox(self.follower).exists())
        moderation.approve(REVIEW, review, make_administrator())
        self.assertEqual(inbox(self.follower).get().kind, Kind.FOLLOWED_REVIEW)

    def test_review_announced_once_after_being_hidden_and_approved(self):
        self.post_review(self.author)
        review = Review.objects.get(author=self.author)
        moderation.hold(REVIEW, review, [(Reason.SPAM, "test")])
        moderation.approve(REVIEW, review, make_administrator())
        self.assertEqual(
            inbox(self.follower).filter(kind=Kind.FOLLOWED_REVIEW).count(), 1
        )

    def test_preference_can_switch_off_review_updates(self):
        NotificationPreference.objects.create(
            user=self.follower, followed_reviews=False
        )
        self.post_review(self.author)
        self.assertFalse(inbox(self.follower).exists())

    def test_demo_reviews_do_not_notify(self):
        review = Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=5, is_demo=True
        )
        self.assertEqual(services.review_published(review), 0)

    def report(self, user, status):
        self.client.force_login(user)
        self.client.post(
            reverse("availability:report", args=[self.hotspot.pk]), {"status": status}
        )

    def test_availability_reports_are_batched_while_unread(self):
        self.report(self.author, "working")
        self.report(self.other, "unavailable")
        notification = inbox(self.follower).get()
        self.assertEqual(notification.kind, Kind.FOLLOWED_AVAILABILITY)
        self.assertEqual(notification.count, 2)
        self.assertEqual(
            notification.text,
            "2 new availability reports on Bryant Park. Latest: unavailable.",
        )

    def test_availability_report_after_reading_starts_a_new_notification(self):
        self.report(self.author, "working")
        first = inbox(self.follower).get()
        self.assertEqual(first.text, "author reported Bryant Park as working.")
        services.mark_read(inbox(self.follower))
        self.report(self.other, "working")
        self.assertEqual(inbox(self.follower).count(), 2)
        first.refresh_from_db()
        self.assertEqual(first.count, 1)

    def test_availability_reporter_and_opted_out_followers_are_skipped(self):
        NotificationPreference.objects.create(
            user=self.follower, followed_availability=False
        )
        follow(self.author, self.hotspot)
        self.report(self.author, "working")
        self.assertEqual(Notification.objects.count(), 0)

    def test_discussion_about_followed_hotspot_notifies(self):
        self.client.force_login(self.author)
        self.client.post(
            reverse("forum:create"),
            {
                "topic_type": "question",
                "title": "Is it busy at lunch?",
                "body": "Wondering about speeds around noon.",
                "hotspot": self.hotspot.pk,
            },
        )
        post = ForumPost.objects.get()
        notification = inbox(self.follower).get()
        self.assertEqual(notification.kind, Kind.FOLLOWED_DISCUSSION)
        self.assertIn("Is it busy at lunch?", notification.text)
        self.client.force_login(self.follower)
        response = self.client.get(
            reverse("notifications:open", args=[notification.pk])
        )
        self.assertRedirects(
            response, post.get_absolute_url(), fetch_redirect_response=False
        )

    def test_discussion_without_hotspot_does_not_notify(self):
        post = ForumPost.objects.create(
            author=self.author, topic_type="discussion", title="General", body="Hi"
        )
        self.assertEqual(services.discussion_started(post), 0)

    def test_retiring_a_hotspot_notifies_followers_once(self):
        NotificationPreference.objects.create(
            user=self.follower,
            followed_reviews=False,
            followed_availability=False,
            followed_discussions=False,
        )
        self.client.force_login(make_administrator())
        url = reverse("hotspots:manage_retire", args=[self.hotspot.pk])
        self.client.post(url, {"confirm": "yes"})
        self.client.post(url, {"confirm": "yes"})
        notification = inbox(self.follower).get()
        self.assertEqual(notification.kind, Kind.FOLLOWED_RETIRED)
        self.client.force_login(self.follower)
        response = self.client.get(
            reverse("notifications:open", args=[notification.pk])
        )
        self.assertRedirects(
            response, reverse("hotspots:followed"), fetch_redirect_response=False
        )

    def test_no_activity_notifications_for_retired_hotspots(self):
        review = Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=3
        )
        self.hotspot.is_active = False
        self.hotspot.save()
        review.refresh_from_db()
        self.assertEqual(services.review_published(review), 0)
        report = AvailabilityReport.objects.create(
            hotspot=self.hotspot, reporter=self.author, status="working"
        )
        self.assertEqual(services.availability_reported(report), 0)


class ModerationNotificationTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.author = make_user("author")
        self.flagger = make_user("flagger")
        self.admin = make_administrator()
        self.review = Review.objects.create(
            hotspot=self.hotspot,
            author=self.author,
            rating=2,
            body="Signal drops every few minutes.",
        )

    def test_automated_hold_notifies_author_once(self):
        self.client.force_login(self.author)
        self.client.post(
            reverse("reviews:edit", args=[self.review.pk]),
            {"rating": "2", "body": "Use promo code SAVE10 for a discount"},
        )
        self.client.post(
            reverse("reviews:edit", args=[self.review.pk]),
            {"rating": "1", "body": "Use promo code SAVE20 for a discount"},
        )
        notification = inbox(self.author).get()
        self.assertEqual(notification.kind, Kind.REVIEW_HELD)
        response = self.client.get(
            reverse("notifications:open", args=[notification.pk])
        )
        self.assertRedirects(
            response,
            f"{self.hotspot.get_absolute_url()}#contribute",
            fetch_redirect_response=False,
        )

    def test_community_auto_hide_notifies_author(self):
        for name in ("a", "b", "c"):
            user = make_user(name)
            flag(self.review, user)
            moderation.auto_hide_if_widely_flagged(REVIEW, self.review)
        self.assertEqual(
            list(inbox(self.author).values_list("kind", flat=True)),
            [Kind.REVIEW_HIDDEN],
        )

    def test_removal_notifies_author_with_reason_and_flaggers(self):
        flag(self.review, self.flagger)
        self.client.force_login(self.admin)
        self.client.post(
            reverse("moderation:remove", args=["review", self.review.pk]),
            {"reason": Reason.OFFENSIVE, "note": "Private note for admins"},
        )
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())
        removed = inbox(self.author).get()
        self.assertEqual(removed.kind, Kind.REVIEW_REMOVED)
        self.assertIn("Harassment, hate or offensive language", removed.text)
        self.assertNotIn("Private note", removed.text)
        self.assertNotIn("flagger", removed.text)
        resolved = inbox(self.flagger).get()
        self.assertEqual(resolved.kind, Kind.FLAG_RESOLVED)
        self.assertIn("removed it", resolved.text)
        self.client.force_login(self.flagger)
        response = self.client.get(reverse("notifications:open", args=[resolved.pk]))
        self.assertRedirects(
            response,
            f"{self.hotspot.get_absolute_url()}#reviews",
            fetch_redirect_response=False,
        )

    def test_dismissal_notifies_flaggers_but_not_author(self):
        flag(self.review, self.flagger)
        moderation.dismiss_flags(REVIEW, self.review, self.admin)
        self.assertFalse(inbox(self.author).exists())
        resolved = inbox(self.flagger).get()
        self.assertIn("decided to keep it", resolved.text)
        self.client.force_login(self.flagger)
        response = self.client.get(reverse("notifications:open", args=[resolved.pk]))
        self.assertRedirects(
            response,
            f"{self.hotspot.get_absolute_url()}#review-{self.review.pk}",
            fetch_redirect_response=False,
        )

    def test_approval_notifies_author_and_flaggers(self):
        flag(self.review, self.flagger)
        moderation.hold(REVIEW, self.review, [(Reason.SPAM, "test")])
        inbox(self.author).delete()
        moderation.approve(REVIEW, self.review, self.admin)
        self.assertEqual(inbox(self.author).get().kind, Kind.REVIEW_APPROVED)
        self.assertEqual(inbox(self.flagger).get().kind, Kind.FLAG_RESOLVED)

    def test_moderation_notices_ignore_preferences(self):
        NotificationPreference.objects.create(
            user=self.author,
            followed_reviews=False,
            followed_availability=False,
            followed_discussions=False,
        )
        moderation.remove_content(REVIEW, self.review, self.admin, Reason.SPAM)
        self.assertEqual(inbox(self.author).get().kind, Kind.REVIEW_REMOVED)


class InboxViewTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.user = make_user("reader")
        self.author = make_user("author")
        follow(self.user, self.hotspot)
        self.review = Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=5, body="Great."
        )
        services.review_published(self.review)
        self.notification = inbox(self.user).get()

    def test_visitors_are_sent_to_log_in(self):
        response = self.client.get(reverse("notifications:inbox"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_inbox_lists_notifications_and_header_shows_unread_count(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:inbox"))
        self.assertContains(response, "author rated Bryant Park 5/5 and wrote a review")
        self.assertContains(response, 'class="nav-badge"')
        self.assertContains(response, '1<span class="visually-hidden"> unread')
        self.assertContains(response, "Mark all as read")

    def test_opening_marks_read_and_goes_to_review(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("notifications:open", args=[self.notification.pk])
        )
        self.assertRedirects(
            response,
            f"{self.hotspot.get_absolute_url()}#review-{self.review.pk}",
            fetch_redirect_response=False,
        )
        self.notification.refresh_from_db()
        self.assertFalse(self.notification.is_unread)
        response = self.client.get(reverse("notifications:inbox"))
        self.assertNotContains(response, 'class="nav-badge"')

    def test_opening_deleted_content_returns_to_inbox(self):
        self.review.delete()
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("notifications:open", args=[self.notification.pk]), follow=True
        )
        self.assertRedirects(response, reverse("notifications:inbox"))
        self.assertContains(response, "no longer available")

    def test_opening_review_that_became_held_returns_to_inbox(self):
        moderation.hold(REVIEW, self.review, [(Reason.SPAM, "test")])
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("notifications:open", args=[self.notification.pk])
        )
        self.assertRedirects(
            response, reverse("notifications:inbox"), fetch_redirect_response=False
        )

    def test_users_cannot_open_other_users_notifications(self):
        self.client.force_login(self.author)
        response = self.client.get(
            reverse("notifications:open", args=[self.notification.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_unread)

    def test_unread_filter_and_mark_all_read(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:inbox") + "?show=unread")
        self.assertContains(response, "author rated Bryant Park")
        self.assertEqual(
            self.client.get(reverse("notifications:mark_all_read")).status_code, 405
        )
        self.client.post(reverse("notifications:mark_all_read"))
        self.assertFalse(inbox(self.user).filter(read_at__isnull=True).exists())
        response = self.client.get(reverse("notifications:inbox") + "?show=unread")
        self.assertContains(response, "all caught up")

    def test_empty_inbox(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse("notifications:inbox"))
        self.assertContains(response, "No notifications yet")
        self.assertNotContains(response, "Mark all as read")

    def test_preferences_default_on_and_save(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:preferences"))
        self.assertContains(response, "checked", count=3)
        self.assertFalse(NotificationPreference.objects.exists())
        self.client.post(
            reverse("notifications:preferences"), {"followed_discussions": "on"}
        )
        preference = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(preference.followed_reviews)
        self.assertFalse(preference.followed_availability)
        self.assertTrue(preference.followed_discussions)

    def test_inbox_paginates(self):
        for index in range(25):
            services.hotspot_retired(self.hotspot)
        self.client.force_login(self.user)
        response = self.client.get(reverse("notifications:inbox") + "?page=2")
        self.assertContains(response, "Page 2 of 2")


class TextAndTargetTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.user = make_user("reader")

    def make(self, kind, **fields):
        return Notification.objects.create(
            recipient=self.user,
            kind=kind,
            hotspot=self.hotspot,
            hotspot_name=self.hotspot.display_name,
            actor_name="sam",
            **fields,
        )

    def test_every_kind_has_readable_text(self):
        for kind in Kind:
            notification = self.make(kind, detail="Spam or advertising")
            self.assertIn("Bryant Park", notification.text)
            self.assertTrue(str(notification))
        self.assertEqual(
            Notification(kind="unknown").text, "unknown"
        )  # Unknown kinds fall back to their raw value.

    def test_targets_for_hotspot_level_notices(self):
        base = self.hotspot.get_absolute_url()
        availability = self.make(Kind.FOLLOWED_AVAILABILITY, detail="Working")
        removed = self.make(Kind.REVIEW_REMOVED, detail="Spam or advertising")
        self.assertEqual(services.target_url(availability), f"{base}#availability")
        self.assertEqual(services.target_url(removed), f"{base}#contribute")
        self.hotspot.is_active = False
        self.hotspot.save()
        availability.refresh_from_db()
        self.assertIsNone(services.target_url(availability))

    def test_deleted_discussion_has_no_target(self):
        notification = self.make(Kind.FOLLOWED_DISCUSSION, object_id=999)
        self.assertIsNone(services.target_url(notification))

    def test_unread_count_for_visitors_is_zero(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(services.unread_count(AnonymousUser()), 0)
