"""E05 acceptance tests: US21 (#31) flag, US19 (#29) inspect, US20 (#30) remove."""
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.tests import make_administrator, make_user
from hotspots.tests import make_hotspot
from reviews.models import Review, ReviewVote

from . import services
from .models import ContentFlag, ModerationRecord, Reason
from .registry import REVIEW, get_type


def flag_url(review):
    return reverse("moderation:flag", args=["review", review.pk])


def remove_url(review):
    return reverse("moderation:remove", args=["review", review.pk])


def make_flag(review, user, reason=Reason.SPAM, note=""):
    return ContentFlag.objects.create(
        content_type=ContentType.objects.get_for_model(Review),
        object_id=review.pk,
        flagged_by=user,
        reason=reason,
        note=note,
    )


@override_settings(DEMO_MODE=False)
class ModerationTestCase(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.author = make_user("author")
        self.reporter = make_user("reporter")
        self.admin = make_administrator("moderator")
        self.review = Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=1, body="Buy cheap watches at spam.example"
        )


class FlagContentTests(ModerationTestCase):
    """US21 / #31."""

    def test_visitor_is_sent_to_log_in_and_cannot_flag(self):
        response = self.client.get(flag_url(self.review))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={flag_url(self.review)}", fetch_redirect_response=False)
        response = self.client.post(flag_url(self.review), {"reason": Reason.SPAM})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ContentFlag.objects.exists())

    def test_contributor_can_flag_a_review(self):
        self.client.force_login(self.reporter)
        response = self.client.get(flag_url(self.review))
        self.assertContains(response, "Flag this hotspot review")
        self.assertContains(response, "Buy cheap watches")
        response = self.client.post(flag_url(self.review), {"reason": Reason.SPAM, "note": "Advertising"}, follow=True)
        self.assertRedirects(response, f"{self.hotspot.get_absolute_url()}#review-{self.review.pk}")
        self.assertContains(response, "Thanks for flagging this")
        flag = ContentFlag.objects.get()
        self.assertEqual((flag.content_object, flag.flagged_by, flag.reason, flag.note, flag.status),
                         (self.review, self.reporter, Reason.SPAM, "Advertising", ContentFlag.Status.OPEN))

    def test_user_can_flag_an_item_only_once(self):
        self.client.force_login(self.reporter)
        self.client.post(flag_url(self.review), {"reason": Reason.SPAM})
        response = self.client.post(flag_url(self.review), {"reason": Reason.OFFENSIVE}, follow=True)
        self.assertContains(response, "You already flagged this")
        self.assertEqual(ContentFlag.objects.count(), 1)
        # Still only once after an administrator dismisses the first flag.
        services.dismiss_flags(REVIEW, self.review, self.admin)
        self.client.post(flag_url(self.review), {"reason": Reason.OFFENSIVE})
        self.assertEqual(ContentFlag.objects.count(), 1)

    def test_database_enforces_one_flag_per_user_per_item(self):
        make_flag(self.review, self.reporter)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_flag(self.review, self.reporter, Reason.OFFENSIVE)

    def test_different_users_can_flag_the_same_item(self):
        make_flag(self.review, self.reporter)
        self.client.force_login(make_user("second"))
        self.client.post(flag_url(self.review), {"reason": Reason.MISLEADING})
        self.assertEqual(ContentFlag.objects.filter(object_id=self.review.pk).count(), 2)

    def test_author_cannot_flag_their_own_review(self):
        self.client.force_login(self.author)
        response = self.client.post(flag_url(self.review), {"reason": Reason.SPAM}, follow=True)
        self.assertContains(response, "You can&#x27;t flag your own content.")
        self.assertFalse(ContentFlag.objects.exists())

    def test_reason_is_required_and_other_needs_details(self):
        self.client.force_login(self.reporter)
        response = self.client.post(flag_url(self.review), {})
        self.assertContains(response, "Choose a reason for flagging.")
        response = self.client.post(flag_url(self.review), {"reason": Reason.OTHER, "note": "  "})
        self.assertContains(response, "Describe the problem")
        response = self.client.post(flag_url(self.review), {"reason": "not-a-reason"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContentFlag.objects.exists())

    def test_only_visible_written_reviews_can_be_flagged(self):
        self.client.force_login(self.reporter)
        rating_only = Review.objects.create(hotspot=self.hotspot, author=self.reporter, rating=4)
        demo = Review.objects.create(hotspot=self.hotspot, author=make_user("demo"), rating=3, body="Demo", is_demo=True)
        retired = make_hotspot(2, name="Old Site")
        on_retired = Review.objects.create(hotspot=retired, author=self.author, rating=2, body="Old")
        retired.is_active = False
        retired.save()
        for review in [rating_only, demo, on_retired]:
            with self.subTest(review=review.pk):
                self.assertEqual(self.client.get(flag_url(review)).status_code, 404)
        self.assertEqual(self.client.get(reverse("moderation:flag", args=["forum-post", 1])).status_code, 404)

    def test_profile_shows_flag_link_to_contributors_only(self):
        response = self.client.get(self.hotspot.get_absolute_url())
        self.assertNotContains(response, flag_url(self.review))
        self.client.force_login(self.author)
        self.assertNotContains(self.client.get(self.hotspot.get_absolute_url()), flag_url(self.review))
        self.client.force_login(self.reporter)
        response = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(response, flag_url(self.review))
        make_flag(self.review, self.reporter)
        response = self.client.get(self.hotspot.get_absolute_url())
        self.assertNotContains(response, flag_url(self.review))
        self.assertContains(response, "Flagged for review")

    def test_flag_requires_post_to_create(self):
        self.client.force_login(self.reporter)
        self.client.get(flag_url(self.review), {"reason": Reason.SPAM})
        self.assertFalse(ContentFlag.objects.exists())


class ModerationViewTests(ModerationTestCase):
    """US19 / #29."""

    queue = reverse("moderation:queue")

    def test_visitors_are_sent_to_log_in_and_contributors_are_refused(self):
        self.assertEqual(self.client.get(self.queue).status_code, 302)
        self.client.force_login(self.reporter)
        self.assertEqual(self.client.get(self.queue).status_code, 403)
        self.assertEqual(self.client.get(remove_url(self.review)).status_code, 403)
        self.assertEqual(self.client.post(remove_url(self.review), {"reason": Reason.SPAM}).status_code, 403)
        self.assertEqual(self.client.post(reverse("moderation:dismiss", args=["review", self.review.pk])).status_code, 403)
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())

    def test_flagged_items_show_type_reference_and_reasons(self):
        make_flag(self.review, self.reporter, Reason.SPAM, "Advertising watches")
        make_flag(self.review, make_user("second"), Reason.SPAM)
        make_flag(self.review, make_user("third"), Reason.OFFENSIVE)
        self.client.force_login(self.admin)
        response = self.client.get(self.queue, {"tab": "flagged"})
        self.assertContains(response, "Hotspot review")
        self.assertContains(response, "3 user flags")
        self.assertContains(response, f'href="{self.hotspot.get_absolute_url()}#review-{self.review.pk}"')
        self.assertContains(response, "Bryant Park (NYC ID 1344)")
        self.assertContains(response, "Spam or advertising ×2")
        self.assertContains(response, "Advertising watches")
        self.assertContains(response, "Buy cheap watches")
        self.assertEqual(response.context["open_item_count"], 1)

    def test_unflagged_and_resolved_items_are_not_in_flagged_view(self):
        other = Review.objects.create(hotspot=self.hotspot, author=self.reporter, rating=5, body="Fast and free")
        flag = make_flag(other, self.author)
        flag.status = ContentFlag.Status.DISMISSED
        flag.save()
        self.client.force_login(self.admin)
        response = self.client.get(self.queue, {"tab": "flagged"})
        self.assertEqual(response.context["items"], [])
        self.assertContains(response, "No flagged content")

    def test_recent_view_lists_ratings_and_reviews_with_flag_counts(self):
        rating_only = Review.objects.create(hotspot=self.hotspot, author=self.reporter, rating=4)
        make_flag(self.review, self.reporter)
        self.client.force_login(self.admin)
        response = self.client.get(self.queue, {"tab": "recent"})
        rows = {row["review"].pk: row["open_flags"] for row in response.context["reviews"]}
        self.assertEqual(rows, {self.review.pk: 1, rating_only.pk: 0})
        self.assertContains(response, "Rating only")
        self.assertContains(response, remove_url(rating_only))
        self.assertEqual(response.context["reviews"][0]["review"], rating_only)

    def test_author_deleting_own_review_withdraws_its_flags(self):
        make_flag(self.review, self.reporter)
        self.client.force_login(self.author)
        self.client.post(reverse("reviews:delete", args=[self.review.pk]))
        self.assertEqual(ContentFlag.objects.get().status, ContentFlag.Status.WITHDRAWN)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.queue, {"tab": "flagged"}).context["items"], [])

    def test_administration_page_links_to_moderation_with_counts(self):
        make_flag(self.review, self.reporter)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:admin_home"))
        self.assertContains(response, self.queue)
        self.assertEqual(response.context["open_flag_items"], 1)

    def test_held_tab_is_the_default_and_unknown_tabs_fall_back_to_it(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.queue).context["tab"], "held")
        self.assertEqual(self.client.get(self.queue, {"tab": "nope"}).context["tab"], "held")


class RemoveContentTests(ModerationTestCase):
    """US20 / #30."""

    def setUp(self):
        super().setUp()
        self.good = Review.objects.create(hotspot=self.hotspot, author=self.reporter, rating=5, body="Reliable")
        ReviewVote.objects.create(review=self.review, user=self.admin)
        make_flag(self.review, self.reporter, Reason.SPAM)
        make_flag(self.review, make_user("second"), Reason.OFFENSIVE)
        self.client.force_login(self.admin)

    def test_removal_requires_confirmation_and_a_reason(self):
        response = self.client.get(remove_url(self.review))
        self.assertContains(response, "Remove this hotspot review?")
        self.assertContains(response, "Buy cheap watches")
        self.assertContains(response, "Its open flags will be closed.")
        response = self.client.post(remove_url(self.review), {})
        self.assertContains(response, "Choose a moderation reason.")
        response = self.client.post(remove_url(self.review), {"reason": Reason.OTHER})
        self.assertContains(response, "Explain the reason")
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())
        self.assertFalse(ModerationRecord.objects.exists())

    def test_removed_review_disappears_publicly_and_average_updates(self):
        self.assertEqual(self.client.get(self.hotspot.get_absolute_url()).context["rating_summary"]["average"], 3.0)
        response = self.client.post(remove_url(self.review), {"reason": Reason.SPAM, "note": "Repeat advertiser"}, follow=True)
        self.assertRedirects(response, f"{reverse('moderation:queue')}?tab=flagged")
        self.assertContains(response, "Removed the hotspot review by author")
        self.assertFalse(Review.objects.filter(pk=self.review.pk).exists())
        self.assertFalse(ReviewVote.objects.exists())
        self.client.logout()
        profile = self.client.get(self.hotspot.get_absolute_url())
        self.assertNotContains(profile, "Buy cheap watches")
        self.assertEqual(profile.context["rating_summary"]["average"], 5.0)
        self.assertEqual(profile.context["rating_summary"]["count"], 1)
        record = self.client.get(reverse("hotspots:data")).json()["hotspots"][0]
        self.assertEqual((record["average_rating"], record["rating_count"]), (5.0, 1))

    def test_removal_is_logged_with_reason_snapshot_and_flags_closed(self):
        self.client.post(remove_url(self.review), {"reason": Reason.SPAM, "note": "Repeat advertiser"})
        record = ModerationRecord.objects.get()
        self.assertEqual(
            (record.action, record.reason, record.note, record.moderator, record.author_username,
             record.rating, record.content_text, record.flag_count, record.content_label),
            (ModerationRecord.Action.REMOVED, Reason.SPAM, "Repeat advertiser", self.admin, "author",
             1, "Buy cheap watches at spam.example", 2, "Hotspot review"),
        )
        self.assertEqual(set(ContentFlag.objects.values_list("status", flat=True)), {ContentFlag.Status.REMOVED})
        self.assertTrue(all(flag.resolution == record for flag in ContentFlag.objects.all()))
        log = self.client.get(reverse("moderation:queue"), {"tab": "log"})
        self.assertContains(log, "Repeat advertiser")
        self.assertContains(log, "Spam or advertising")

    def test_unflagged_rating_only_entry_can_be_removed(self):
        rating_only = Review.objects.create(hotspot=self.hotspot, author=make_user("rater"), rating=1)
        self.client.post(remove_url(rating_only), {"reason": Reason.MISLEADING})
        self.assertFalse(Review.objects.filter(pk=rating_only.pk).exists())
        self.assertEqual(ModerationRecord.objects.get().flag_count, 0)

    def test_administrators_never_edit_the_text(self):
        self.client.post(remove_url(self.review), {"reason": Reason.SPAM, "body": "Edited"})
        self.assertEqual(ModerationRecord.objects.get().content_text, "Buy cheap watches at spam.example")
        self.assertEqual(Review.objects.get(pk=self.good.pk).body, "Reliable")

    def test_dismissing_flags_keeps_content_and_logs_decision(self):
        dismiss = reverse("moderation:dismiss", args=["review", self.review.pk])
        self.assertEqual(self.client.get(dismiss).status_code, 405)
        response = self.client.post(dismiss, follow=True)
        self.assertContains(response, "Flags dismissed")
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())
        self.assertEqual(set(ContentFlag.objects.values_list("status", flat=True)), {ContentFlag.Status.DISMISSED})
        record = ModerationRecord.objects.get()
        self.assertEqual((record.action, record.flag_count), (ModerationRecord.Action.DISMISSED, 2))
        response = self.client.post(dismiss, follow=True)
        self.assertContains(response, "There are no open flags")
        self.assertEqual(ModerationRecord.objects.count(), 1)

    def test_missing_content_returns_404(self):
        self.assertEqual(self.client.get(reverse("moderation:remove", args=["review", 999999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("moderation:remove", args=["thread", self.review.pk])).status_code, 404)


class RegistryTests(TestCase):
    def test_review_type_is_registered_for_shared_workflow(self):
        self.assertIs(get_type("review"), REVIEW)
        self.assertIs(REVIEW.model, Review)
        self.assertTrue(REVIEW.affects_rating)

    def test_service_rejects_removal_without_a_reason(self):
        hotspot = make_hotspot()
        review = Review.objects.create(hotspot=hotspot, author=make_user("a"), rating=3, body="x")
        with self.assertRaises(ValueError):
            services.remove_content(REVIEW, review, make_administrator(), "")
        self.assertTrue(Review.objects.filter(pk=review.pk).exists())
