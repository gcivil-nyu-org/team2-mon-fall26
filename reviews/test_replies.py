"""Replies to reviews and helpful / not-helpful votes, with E05 moderation and E07 notices."""

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.tests import make_administrator, make_established_user, make_user
from hotspots.tests import make_hotspot
from moderation import services as moderation
from moderation.models import ContentFlag, ModerationRecord, Reason
from moderation.registry import REVIEW, REVIEW_REPLY, get_type
from notifications.models import Notification, NotificationPreference

from .models import Review, ReviewReply, ReviewVote
from .services import public_replies, rating_summary

Kind = Notification.Kind
CLEAN = "Thanks, the outlets by the north entrance worked for me too."


def notices(user, kind=Kind.REVIEW_REPLY):
    return Notification.objects.filter(recipient=user, kind=kind)


class VoteTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.author = make_user("author")
        self.voter = make_user("voter")
        self.review = Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=4, body="Fast and quiet."
        )
        self.url = reverse("reviews:vote", args=[self.review.pk])
        self.client.force_login(self.voter)

    def vote(self, direction):
        return self.client.post(self.url, {"direction": direction})

    def test_downvote_switch_and_remove(self):
        self.vote("down")
        self.assertEqual(ReviewVote.objects.get().value, ReviewVote.DOWN)
        self.vote("up")
        self.assertEqual(ReviewVote.objects.get().value, ReviewVote.UP)
        self.vote("up")
        self.assertFalse(ReviewVote.objects.exists())

    def test_missing_direction_is_an_upvote(self):
        self.client.post(self.url)
        self.assertEqual(ReviewVote.objects.get().value, ReviewVote.UP)

    def test_counts_shown_and_average_unchanged(self):
        self.vote("down")
        ReviewVote.objects.create(review=self.review, user=make_user("fan"))
        page = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(page, "Remove not-helpful vote, </span>1")
        self.assertContains(page, "Helpful, </span>1")
        self.assertEqual(rating_summary(Review.objects.all())["average"], 4.0)

    def test_author_cannot_downvote_own_review(self):
        self.client.force_login(self.author)
        self.vote("down")
        self.assertFalse(ReviewVote.objects.exists())

    def test_rating_only_and_held_reviews_take_no_votes(self):
        rating_only = Review.objects.create(
            hotspot=self.hotspot, author=make_user("quiet"), rating=2
        )
        held = Review.objects.create(
            hotspot=make_hotspot(2000),
            author=self.author,
            rating=1,
            body="Held text.",
            is_held=True,
        )
        for review in (rating_only, held):
            response = self.client.post(
                reverse("reviews:vote", args=[review.pk]), {"direction": "down"}
            )
            self.assertEqual(response.status_code, 404)

    def test_visitor_sees_counts_but_no_buttons(self):
        self.client.logout()
        page = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(page, "0 helpful")
        self.assertNotContains(page, 'name="direction"')


class ReplyTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.author = make_user("author")
        self.replier = make_user("replier")
        self.review = Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=4, body="Fast and quiet."
        )
        self.url = reverse("reviews:reply", args=[self.review.pk])

    def reply(self, body=CLEAN, user=None):
        self.client.force_login(user or self.replier)
        return self.client.post(self.url, {"body": body})

    def test_visitor_is_sent_to_log_in_and_get_is_rejected(self):
        response = self.client.post(self.url, {"body": CLEAN})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        login_form = self.client.get(response.url)
        self.assertEqual(
            login_form.context["next"],
            f"{self.hotspot.get_absolute_url()}#review-{self.review.pk}",
        )
        self.client.force_login(self.replier)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertFalse(ReviewReply.objects.exists())

    def test_reply_is_public_and_notifies_review_author(self):
        response = self.reply()
        reply = ReviewReply.objects.get()
        self.assertRedirects(
            response,
            f"{self.hotspot.get_absolute_url()}#reply-{reply.pk}",
            fetch_redirect_response=False,
        )
        self.client.logout()
        page = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(page, CLEAN)
        self.assertContains(page, f'id="reply-{reply.pk}"')
        notice = notices(self.author).get()
        self.assertIn("replier replied to your review of", notice.text)
        self.client.force_login(self.author)
        response = self.client.get(reverse("notifications:open", args=[notice.pk]))
        self.assertTrue(response["Location"].endswith(f"#reply-{reply.pk}"))

    def test_visitor_sees_log_in_to_reply_except_on_demo_reviews(self):
        with self.settings(DEMO_MODE=True):
            demo = Review.objects.create(
                hotspot=self.hotspot,
                author=make_user("demo_ana"),
                rating=5,
                body="Demo text.",
                is_demo=True,
            )
            page = self.client.get(self.hotspot.get_absolute_url())
        login = reverse("accounts:login")
        self.assertContains(page, f"%23review-{self.review.pk}")
        self.assertNotContains(page, f"%23review-{demo.pk}")
        self.assertContains(page, login)

    def test_own_reply_and_preference_off_send_no_notice(self):
        self.reply(user=self.author)
        NotificationPreference.objects.create(user=self.author, review_replies=False)
        self.reply("A second, different reply about the same review.")
        self.assertEqual(ReviewReply.objects.count(), 2)
        self.assertFalse(notices(self.author).exists())

    def test_empty_and_blocked_replies_are_rejected(self):
        self.reply("   ")
        self.reply("Call me at 212-555-0123 for the password")
        self.reply("See https://example.com/deal")
        self.assertFalse(ReviewReply.objects.exists())

    def test_cannot_reply_to_rating_only_held_or_retired_reviews(self):
        rating_only = Review.objects.create(
            hotspot=self.hotspot, author=make_user("quiet"), rating=2
        )
        held_hotspot = make_hotspot(2000)
        held = Review.objects.create(
            hotspot=held_hotspot,
            author=self.author,
            rating=1,
            body="Hmm.",
            is_held=True,
        )
        retired_hotspot = make_hotspot(3000)
        retired = Review.objects.create(
            hotspot=retired_hotspot, author=self.author, rating=3, body="Fine."
        )
        retired_hotspot.is_active = False
        retired_hotspot.save()
        self.client.force_login(self.replier)
        for review in (rating_only, held, retired):
            response = self.client.post(
                reverse("reviews:reply", args=[review.pk]), {"body": CLEAN}
            )
            self.assertEqual(response.status_code, 404)
        self.assertFalse(ReviewReply.objects.exists())

    def test_suspicious_reply_is_held_and_visible_only_to_its_author(self):
        self.reply("THIS HOTSPOT IS THE WORST I HAVE EVER USED IN MY LIFE")
        reply = ReviewReply.objects.get()
        self.assertTrue(reply.is_held)
        self.assertFalse(public_replies().exists())
        self.assertFalse(notices(self.author).exists())
        self.assertTrue(notices(self.replier, Kind.REVIEW_HELD).exists())
        self.assertIn(
            "reply to author's review",
            notices(self.replier, Kind.REVIEW_HELD).get().text,
        )
        own = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(own, "Awaiting moderator approval")
        self.client.force_login(self.author)
        self.assertNotContains(
            self.client.get(self.hotspot.get_absolute_url()), "WORST"
        )
        # Approval publishes it and only then tells the review author.
        moderation.approve(REVIEW_REPLY, reply, make_administrator())
        reply.refresh_from_db()
        self.assertFalse(reply.is_held)
        self.assertEqual(notices(self.author).count(), 1)

    def test_author_can_delete_own_reply_only(self):
        self.reply()
        reply = ReviewReply.objects.get()
        delete_url = reverse("reviews:delete_reply", args=[reply.pk])
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(delete_url).status_code, 404)
        self.client.force_login(self.replier)
        self.assertContains(self.client.get(delete_url), "Delete your reply?")
        self.client.post(delete_url)
        self.assertFalse(ReviewReply.objects.exists())

    def test_deleting_a_review_removes_its_replies(self):
        self.reply()
        self.client.force_login(self.author)
        response = self.client.post(reverse("reviews:delete", args=[self.review.pk]))
        self.assertRedirects(response, f"{self.hotspot.get_absolute_url()}#reviews")
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())
        self.assertFalse(ReviewReply.objects.exists())

    def test_author_sees_deletion_effect_before_confirming(self):
        self.reply()
        ReviewReply.objects.create(
            review=self.review, author=self.replier, body="Pending", is_held=True
        )
        self.client.force_login(self.author)
        page = self.client.get(reverse("reviews:delete", args=[self.review.pk]))
        self.assertContains(page, "Deleting this review also deletes its replies.")
        self.assertContains(page, "1 visible reply")
        self.assertNotContains(page, "2 visible replies")
        self.assertContains(
            page, f'href="{self.hotspot.get_absolute_url()}#reviews">Keep my review</a>'
        )
        self.client.get(self.hotspot.get_absolute_url())
        self.assertEqual(self.review.replies.count(), 2)

    def test_reply_notice_returns_to_inbox_if_parent_becomes_rating_only(self):
        self.reply()
        notice = notices(self.author).get()
        self.review.body = ""
        self.review.save(update_fields=["body"])
        self.client.force_login(self.author)
        response = self.client.get(reverse("notifications:open", args=[notice.pk]))
        self.assertRedirects(response, reverse("notifications:inbox"))


class ReplyModerationTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.author = make_user("author")
        self.replier = make_user("replier")
        self.admin = make_administrator()
        self.review = Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=4, body="Fast and quiet."
        )
        self.reply = ReviewReply.objects.create(
            review=self.review, author=self.replier, body=CLEAN
        )

    def flag(self, user):
        return ContentFlag.objects.create(
            content_type=ContentType.objects.get_for_model(ReviewReply),
            object_id=self.reply.pk,
            flagged_by=user,
            reason=Reason.OFFENSIVE,
        )

    def test_reply_is_a_registered_flaggable_type(self):
        self.assertIs(get_type("reply"), REVIEW_REPLY)
        info = REVIEW_REPLY.describe(self.reply)
        self.assertTrue(info["is_public"])
        self.assertIn("#reply-", info["url"])
        self.assertIn("Reply to author's review", info["reference"])

    def test_contributor_flags_a_reply_from_the_profile(self):
        flagger = make_user("flagger")
        self.client.force_login(flagger)
        page = self.client.get(self.hotspot.get_absolute_url())
        flag_url = reverse("moderation:flag", args=["reply", self.reply.pk])
        self.assertContains(page, flag_url)
        response = self.client.post(flag_url, {"reason": Reason.SPAM})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContentFlag.objects.filter(flagged_by=flagger).count(), 1)
        self.assertContains(
            self.client.get(self.hotspot.get_absolute_url()), "Flagged for review"
        )

    def test_replier_cannot_flag_own_reply(self):
        self.client.force_login(self.replier)
        self.client.post(
            reverse("moderation:flag", args=["reply", self.reply.pk]),
            {"reason": Reason.SPAM},
        )
        self.assertFalse(ContentFlag.objects.exists())

    @override_settings(MODERATION_AUTO_HIDE_FLAGS=3)
    def test_only_established_reporters_count_toward_hiding_a_reply(self):
        self.flag(make_user("new-reporter"))
        self.flag(make_established_user("first"))
        self.flag(make_established_user("second"))
        self.assertFalse(
            moderation.auto_hide_if_widely_flagged(REVIEW_REPLY, self.reply)
        )
        self.flag(make_established_user("third"))
        self.assertTrue(
            moderation.auto_hide_if_widely_flagged(REVIEW_REPLY, self.reply)
        )
        self.reply.refresh_from_db()
        self.assertTrue(self.reply.is_held)
        self.assertTrue(notices(self.replier, Kind.REVIEW_HIDDEN).exists())

    def test_admin_removal_logs_and_notifies(self):
        flagger = make_user("flagger")
        self.flag(flagger)
        self.client.force_login(self.admin)
        queue = self.client.get(reverse("moderation:queue") + "?tab=flagged")
        self.assertContains(queue, "Review reply")
        response = self.client.post(
            reverse("moderation:remove", args=["reply", self.reply.pk]),
            {"reason": Reason.SPAM},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ReviewReply.objects.exists())
        record = ModerationRecord.objects.get()
        self.assertEqual(record.action, ModerationRecord.Action.REMOVED)
        removed = notices(self.replier, Kind.REVIEW_REMOVED).get()
        self.assertIn("reply to author's review", removed.text)
        resolved = notices(flagger, Kind.FLAG_RESOLVED).get()
        self.assertIn("the reply you flagged", resolved.text)
        # The review is still there, so the notices open it.
        self.client.force_login(self.replier)
        response = self.client.get(reverse("notifications:open", args=[removed.pk]))
        self.assertIn(self.hotspot.get_absolute_url(), response["Location"])

    def test_review_removal_warns_about_replies(self):
        self.client.force_login(self.admin)
        page = self.client.get(
            reverse("moderation:remove", args=["review", self.review.pk])
        )
        self.assertContains(page, "This also removes 1 reply.")
        self.assertEqual(
            REVIEW.removal_effect(self.review), "This also removes 1 reply."
        )

    def test_author_deleting_reply_withdraws_flags(self):
        flag = self.flag(make_user("flagger"))
        self.reply.delete()
        flag.refresh_from_db()
        self.assertEqual(flag.status, ContentFlag.Status.WITHDRAWN)
