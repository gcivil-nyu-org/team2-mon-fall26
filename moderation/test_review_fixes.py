"""PR #60 review fixes: moderation decisions vs. concurrent author edits, and
confirmation before bulk removal (US20 / #30).

The interleaving tests run a moderation action at the exact point the review
reported: after the edit view has read the review, but before it saves.
"""

from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.tests import make_administrator, make_user
from hotspots.tests import make_hotspot
from reviews import views as review_views
from reviews.models import Review, ReviewVote

from . import services
from .models import ContentFlag, ModerationRecord, Reason
from .registry import REVIEW

CLEAN = "Strong signal by the fountain, easy to connect, good for video calls."


def run_after_lookup(action):
    """Patch the edit view so ``action`` runs between its lookup and its save."""
    original = review_views._own_review_or_404

    def lookup_then_act(request, pk):
        review = original(request, pk)
        action(Review.objects.get(pk=review.pk))
        return review

    return mock.patch.object(review_views, "_own_review_or_404", lookup_then_act)


@override_settings(DEMO_MODE=False, MODERATION_AUTO_HIDE_FLAGS=3)
class ConcurrentAuthorEditTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.author = make_user("author")
        self.admin = make_administrator()
        self.review = Review.objects.create(
            hotspot=self.hotspot,
            author=self.author,
            rating=2,
            body="Original text here.",
        )
        self.edit_url = reverse("reviews:edit", args=[self.review.pk])
        self.client.force_login(self.author)

    def edit(self, body=CLEAN, rating=4):
        return self.client.post(
            self.edit_url, {"rating": rating, "body": body}, follow=True
        )

    def test_community_hold_during_edit_is_preserved(self):
        def three_flags(review):
            for name in ["one", "two", "three"]:
                ContentFlag.objects.create(
                    content_type=services.content_type_for(REVIEW),
                    object_id=review.pk,
                    flagged_by=make_user(name),
                    reason=Reason.OFFENSIVE,
                )
            self.assertTrue(services.auto_hide_if_widely_flagged(REVIEW, review))

        with run_after_lookup(three_flags):
            response = self.edit()
        self.review.refresh_from_db()
        self.assertTrue(
            self.review.is_held,
            "a clean edit must not republish a community-held review",
        )
        self.assertEqual((self.review.rating, self.review.body), (4, CLEAN))
        self.assertContains(response, "waiting for a moderator")
        self.client.logout()
        self.assertNotContains(self.client.get(self.hotspot.get_absolute_url()), CLEAN)

    def test_automated_hold_during_edit_is_preserved(self):
        with run_after_lookup(
            lambda review: services.hold(
                REVIEW, review, [(Reason.SPAM, "Held elsewhere")]
            )
        ):
            self.edit()
        self.review.refresh_from_db()
        self.assertTrue(self.review.is_held)

    def test_moderator_removal_during_edit_is_not_undone(self):
        ReviewVote.objects.create(review=self.review, user=make_user("voter"))
        with run_after_lookup(
            lambda review: services.remove_content(
                REVIEW, review, self.admin, Reason.SPAM
            )
        ):
            response = self.edit()
        self.assertFalse(
            Review.objects.filter(pk=self.review.pk).exists(),
            "the removed review must not be recreated",
        )
        self.assertFalse(Review.objects.filter(author=self.author).exists())
        self.assertContains(response, "no longer available")
        self.assertEqual(
            ModerationRecord.objects.get().content_text, "Original text here."
        )

    def test_edit_without_interference_still_saves_and_keeps_publication(self):
        response = self.edit()
        self.review.refresh_from_db()
        self.assertEqual(
            (self.review.rating, self.review.body, self.review.is_held),
            (4, CLEAN, False),
        )
        self.assertContains(response, "Your changes have been saved")

    def test_edit_never_writes_moderation_state(self):
        with mock.patch.object(
            Review, "save", autospec=True, side_effect=Review.save
        ) as save:
            self.edit()
        self.assertEqual(
            save.call_args.kwargs["update_fields"], ["rating", "body", "updated_at"]
        )

    def test_removing_an_already_deleted_review_changes_nothing(self):
        stale = Review.objects.get(pk=self.review.pk)
        Review.objects.filter(pk=stale.pk).delete()
        self.assertIsNone(
            services.remove_content(REVIEW, stale, self.admin, Reason.SPAM)
        )
        self.assertFalse(ModerationRecord.objects.exists())


@override_settings(DEMO_MODE=False)
class ApproveStaleVersionTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.author = make_user("author")
        self.review = Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=3, body="promo code inside"
        )
        services.hold(
            REVIEW, self.review, [(Reason.SPAM, "Promotional wording: promo code")]
        )
        self.seen_version = REVIEW.describe(Review.objects.get(pk=self.review.pk))[
            "version"
        ]
        self.client.force_login(make_administrator())
        self.approve_url = reverse(
            "moderation:approve", args=["review", self.review.pk]
        )

    def author_edits(self):
        Review.objects.filter(pk=self.review.pk).update(
            body="Something the moderator never saw",
            updated_at=self.review.updated_at + timedelta(seconds=5),
        )

    def test_approval_of_text_edited_after_viewing_is_refused(self):
        self.author_edits()
        response = self.client.post(
            self.approve_url, {"version": self.seen_version}, follow=True
        )
        self.assertContains(response, "Not published")
        self.assertTrue(Review.objects.get(pk=self.review.pk).is_held)
        self.assertFalse(ModerationRecord.objects.exists())

    def test_bulk_approval_skips_edited_items(self):
        self.author_edits()
        response = self.client.post(
            reverse("moderation:bulk"),
            {
                "action": "approve",
                "items": [f"review:{self.review.pk}|{self.seen_version}"],
            },
            follow=True,
        )
        self.assertContains(response, "Approved and published 0 items")
        self.assertContains(response, "1 item not published")
        self.assertTrue(Review.objects.get(pk=self.review.pk).is_held)

    def test_unchanged_text_is_approved(self):
        self.client.post(self.approve_url, {"version": self.seen_version})
        self.assertFalse(Review.objects.get(pk=self.review.pk).is_held)


@override_settings(DEMO_MODE=False)
class BulkRemovalConfirmationTests(TestCase):
    """US20 requires confirmation; the bulk button must not delete on its own."""

    def setUp(self):
        self.reviews = []
        for index in range(3):
            review = Review.objects.create(
                hotspot=make_hotspot(index + 1, name=f"Site {index}"),
                author=make_user(f"bot{index}"),
                rating=1,
                body=f"promo code number {index}",
            )
            ReviewVote.objects.create(review=review, user=make_user(f"voter{index}"))
            services.hold(
                REVIEW, review, [(Reason.SPAM, "Promotional wording: promo code")]
            )
            self.reviews.append(review)
        self.items = [
            f"review:{review.pk}|{REVIEW.describe(review)['version']}"
            for review in self.reviews
        ]
        self.bulk = reverse("moderation:bulk")
        self.client.force_login(make_administrator())

    def test_first_step_only_shows_a_confirmation(self):
        response = self.client.post(
            self.bulk,
            {
                "action": "remove",
                "reason": Reason.SPAM,
                "tab": "held",
                "items": self.items,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "moderation/confirm_bulk_remove.html")
        self.assertContains(response, "Remove 3 selected items?")
        self.assertContains(response, "Nothing has been removed yet.")
        for index in range(3):
            self.assertContains(response, f"promo code number {index}")
        self.assertContains(response, 'href="/manage/moderation/?tab=held"')  # Cancel
        self.assertEqual(Review.objects.count(), 3)
        self.assertEqual(ReviewVote.objects.count(), 3)
        self.assertFalse(ModerationRecord.objects.exists())

    def test_cancelling_keeps_every_record(self):
        self.client.post(
            self.bulk, {"action": "remove", "reason": Reason.SPAM, "items": self.items}
        )
        self.client.get(reverse("moderation:queue"))
        self.assertEqual(Review.objects.filter(is_held=True).count(), 3)

    def test_confirmed_submission_removes_and_logs_each(self):
        response = self.client.post(
            self.bulk,
            {
                "action": "remove",
                "confirm": "yes",
                "reason": Reason.SPAM,
                "note": "Spam wave",
                "tab": "held",
                "items": self.items[:2],
            },
            follow=True,
        )
        self.assertRedirects(response, f"{reverse('moderation:queue')}?tab=held")
        self.assertContains(response, "Removed 2 items")
        self.assertEqual(
            list(Review.objects.values_list("pk", flat=True)), [self.reviews[2].pk]
        )
        self.assertEqual(ModerationRecord.objects.filter(note="Spam wave").count(), 2)

    def test_queue_button_is_labelled_as_a_step(self):
        response = self.client.get(reverse("moderation:queue"))
        self.assertContains(response, "Remove selected…")
        self.assertNotContains(response, 'name="confirm"')
