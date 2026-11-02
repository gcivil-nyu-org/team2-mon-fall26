"""E05 automated moderation: block at submit, hold for review, trust, community auto-hide."""

from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.tests import make_administrator, make_user
from hotspots.tests import make_hotspot
from reviews.models import Review

from . import services
from .automod import blocking_problems, hold_reasons, is_trusted
from .models import ContentFlag, ModerationRecord, Reason
from .registry import REVIEW

CLEAN = (
    "Strong signal near the fountain, easy to connect and fast enough for video calls."
)


def reasons_for(review, is_new=True):
    return [detail for _, detail in hold_reasons(review, is_new)]


class BlockingRuleTests(TestCase):
    """Tier 1: rejected by the form, nothing saved."""

    def test_links_emails_and_phone_numbers_are_blocked(self):
        for text in [
            "Great deals at https://cheap.example",
            "see www.example.org for more",
            "visit cheapwatches.com today",
            "Email me at spammer@example.net",
            "Call 212-555-0187 now",
            "Call (212) 555 0187",
        ]:
            with self.subTest(text=text):
                self.assertTrue(blocking_problems(text))

    def test_ordinary_reviews_are_not_blocked(self):
        for text in [
            CLEAN,
            "Great signal.Me and my friend both connected.",  # missing space is not a link
            "Hours are listed on nyc.gov and the library site.",  # official domains allowed
            "Speeds around 100 Mbps, 5G nearby, open 9 to 5.",
            "",
        ]:
            with self.subTest(text=text):
                self.assertEqual(blocking_problems(text), [])

    @override_settings(MODERATION_BLOCKED_TERMS=["badword", "two words"])
    def test_configured_blocked_terms_are_rejected(self):
        self.assertTrue(blocking_problems("This is a BADWORD review"))
        self.assertTrue(blocking_problems("b4dword here"))  # simple look-alike digits
        self.assertTrue(blocking_problems("contains two   words together"))
        self.assertEqual(blocking_problems("badwords is a different word"), [])


@override_settings(DEMO_MODE=False)
class HoldRuleTests(TestCase):
    """Tier 2: saved but hidden until an administrator decides."""

    def setUp(self):
        self.hotspots = [make_hotspot(i, name=f"Site {i}") for i in range(1, 8)]
        self.author = make_user("author")

    def review(self, body, hotspot=0, author=None, **fields):
        return Review.objects.create(
            hotspot=self.hotspots[hotspot],
            author=author or self.author,
            rating=3,
            body=body,
            **fields,
        )

    def test_clean_reviews_and_ratings_are_not_held(self):
        self.assertEqual(reasons_for(self.review(CLEAN)), [])
        self.assertEqual(reasons_for(self.review("", hotspot=1)), [])
        self.assertEqual(
            reasons_for(self.review("Free Wi-Fi that actually works!", hotspot=2)), []
        )

    def test_each_suspicious_signal_is_held_with_an_explanation(self):
        cases = {
            "Use promo code SAVE20 at the cafe next door": "Promotional wording",
            "This wifi is shit, never connects": "Contains profanity",
            "This wifi is sh1t, never connects": "Contains profanity",
            "THIS HOTSPOT IS THE WORST I HAVE EVER USED": "Mostly written in capital letters",
            "Sooooooooo slow": "Heavily repeated characters or words",
            "bad bad bad bad connection": "Heavily repeated characters or words",
        }
        for index, (text, expected) in enumerate(cases.items()):
            with self.subTest(text=text):
                details = reasons_for(self.review(text, hotspot=index))
                self.assertTrue(
                    any(detail.startswith(expected) for detail in details), details
                )

    def test_duplicate_text_is_held(self):
        self.review(CLEAN, hotspot=0)
        self.assertIn(
            "Same text as another of this author's reviews",
            reasons_for(self.review(CLEAN.upper().lower(), hotspot=1)),
        )
        other = self.review(CLEAN, hotspot=2, author=make_user("copycat"))
        self.assertIn("Same text as a review by another account", reasons_for(other))

    def test_posting_too_fast_is_held_for_new_reviews_only(self):
        for index in range(3):
            self.review(f"Review number {index} with enough detail.", hotspot=index)
        fourth = self.review("Fourth review in a few minutes.", hotspot=3)
        self.assertIn("Posting many reviews in a short time", reasons_for(fourth))
        self.assertNotIn(
            "Posting many reviews in a short time", reasons_for(fourth, is_new=False)
        )
        Review.objects.update(created_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(
            reasons_for(self.review("Later review, after a break.", hotspot=4)), []
        )

    def test_trusted_authors_skip_soft_rules_but_not_spam_rules(self):
        for index in range(3):
            self.review(f"Helpful review {index} about this hotspot.", hotspot=index)
        Review.objects.update(created_at=timezone.now() - timedelta(days=2))
        self.assertTrue(is_trusted(self.author))
        self.assertEqual(
            reasons_for(
                self.review("THE SIGNAL HERE IS AMAZING, BEST IN MIDTOWN", hotspot=3)
            ),
            [],
        )
        self.assertTrue(
            reasons_for(self.review("DM me for a discount code", hotspot=4))
        )

    def test_repeat_offenders_have_everything_held(self):
        admin = make_administrator()
        for index in range(2):
            services.remove_content(
                REVIEW,
                self.review(f"spam number {index}", hotspot=index),
                admin,
                Reason.SPAM,
            )
        self.assertFalse(is_trusted(self.author))
        details = reasons_for(self.review("", hotspot=2))
        self.assertEqual(
            details, ["Author has had several reviews removed by moderators"]
        )


@override_settings(DEMO_MODE=False)
class SubmitAndHoldFlowTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.author = make_user("author")
        self.admin = make_administrator("moderator")
        Review.objects.create(
            hotspot=self.hotspot,
            author=make_user("fan"),
            rating=5,
            body="Reliable connection.",
        )
        self.client.force_login(self.author)

    def submit(self, body, rating=1):
        return self.client.post(
            reverse("reviews:create", args=[self.hotspot.pk]),
            {"rating": rating, "body": body},
            follow=True,
        )

    def profile(self):
        return self.client.get(self.hotspot.get_absolute_url())

    def test_blocked_text_shows_an_error_and_saves_nothing(self):
        response = self.submit("Cheap watches at https://watches.example")
        self.assertContains(
            response, "can&#x27;t include links, email addresses or phone numbers"
        )
        self.assertFalse(Review.objects.filter(author=self.author).exists())

    def test_held_review_is_hidden_from_public_and_average_until_approved(self):
        response = self.submit("Use promo code WIFI50 for 50% off at my shop")
        self.assertContains(response, "waiting for a moderator")
        review = Review.objects.get(author=self.author)
        self.assertTrue(review.is_held)
        flag = ContentFlag.objects.get(object_id=review.pk)
        self.assertTrue(flag.is_automated)
        self.assertIn("Promotional wording", flag.note)

        own_view = self.profile()
        self.assertContains(own_view, "Awaiting moderator approval")
        self.assertEqual(own_view.context["rating_summary"]["average"], 5.0)
        self.client.logout()
        public = self.profile()
        self.assertNotContains(public, "promo code")
        self.assertEqual(public.context["rating_summary"]["count"], 1)
        api = self.client.get(reverse("hotspots:data")).json()["hotspots"][0]
        self.assertEqual((api["average_rating"], api["rating_count"]), (5.0, 1))

        self.client.force_login(self.admin)
        queue = self.client.get(reverse("moderation:queue"))
        self.assertEqual([item["pk"] for item in queue.context["items"]], [review.pk])
        self.assertContains(queue, "Automated check:")
        self.assertContains(queue, "Promotional wording")
        self.client.post(
            reverse("moderation:approve", args=["review", review.pk]),
            {"version": REVIEW.describe(review)["version"]},
        )
        review.refresh_from_db()
        self.assertFalse(review.is_held)
        self.assertEqual(
            ContentFlag.objects.get(object_id=review.pk).status,
            ContentFlag.Status.DISMISSED,
        )
        self.assertEqual(
            ModerationRecord.objects.get().action, ModerationRecord.Action.APPROVED
        )
        self.client.logout()
        self.assertEqual(self.profile().context["rating_summary"]["average"], 3.0)

    def test_clean_review_publishes_immediately(self):
        response = self.submit(CLEAN, rating=4)
        self.assertContains(response, "Your rating has been saved")
        self.assertFalse(Review.objects.get(author=self.author).is_held)
        self.assertFalse(ContentFlag.objects.exists())

    def test_editing_a_published_review_into_spam_holds_it(self):
        self.submit(CLEAN, rating=4)
        review = Review.objects.get(author=self.author)
        response = self.client.post(
            reverse("reviews:edit", args=[review.pk]),
            {"rating": 4, "body": "DM me on telegram for crypto tips"},
            follow=True,
        )
        self.assertContains(response, "waiting for a moderator")
        review.refresh_from_db()
        self.assertTrue(review.is_held)

    def test_editing_a_held_review_keeps_it_held(self):
        self.submit("Promo code inside, message me")
        review = Review.objects.get(author=self.author)
        self.client.post(
            reverse("reviews:edit", args=[review.pk]), {"rating": 3, "body": CLEAN}
        )
        review.refresh_from_db()
        self.assertTrue(review.is_held)
        self.assertEqual(
            ContentFlag.objects.filter(
                object_id=review.pk, status=ContentFlag.Status.OPEN
            ).count(),
            1,
        )

    def test_held_reviews_cannot_be_flagged_or_upvoted(self):
        self.submit("Promo code inside, message me")
        review = Review.objects.get(author=self.author)
        self.client.force_login(make_user("other"))
        self.assertEqual(
            self.client.get(
                reverse("moderation:flag", args=["review", review.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("reviews:vote", args=[review.pk])).status_code, 404
        )


@override_settings(DEMO_MODE=False, MODERATION_AUTO_HIDE_FLAGS=3)
class CommunityAutoHideTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.review = Review.objects.create(
            hotspot=self.hotspot,
            author=make_user("author"),
            rating=1,
            body="Rude review here",
        )
        self.url = reverse("moderation:flag", args=["review", self.review.pk])

    def flag(self, username):
        self.client.force_login(make_user(username))
        self.client.post(self.url, {"reason": Reason.OFFENSIVE})

    def test_three_separate_flags_hide_the_review(self):
        self.flag("one")
        self.flag("two")
        self.review.refresh_from_db()
        self.assertFalse(self.review.is_held)
        self.flag("three")
        self.review.refresh_from_db()
        self.assertTrue(self.review.is_held)
        self.client.logout()
        self.assertNotContains(
            self.client.get(self.hotspot.get_absolute_url()), "Rude review here"
        )
        self.client.force_login(make_administrator())
        held = self.client.get(reverse("moderation:queue"))
        self.assertEqual(held.context["items"][0]["flag_count"], 3)
        self.assertContains(held, "after several users flagged it")
        self.assertEqual(
            self.client.get(reverse("moderation:queue"), {"tab": "flagged"}).context[
                "items"
            ],
            [],
        )


@override_settings(DEMO_MODE=False)
class BulkActionTests(TestCase):
    def setUp(self):
        self.hotspots = [make_hotspot(i, name=f"Site {i}") for i in range(1, 4)]
        self.admin = make_administrator()
        self.held = []
        for index, hotspot in enumerate(self.hotspots):
            review = Review.objects.create(
                hotspot=hotspot,
                author=make_user(f"spammer{index}"),
                rating=1,
                body=f"promo code {index}",
            )
            services.hold(
                REVIEW, review, [(Reason.SPAM, "Promotional wording: promo code")]
            )
            self.held.append(review)
        self.bulk = reverse("moderation:bulk")
        self.client.force_login(self.admin)

    def keys(self, reviews):
        return [
            f"review:{review.pk}|{REVIEW.describe(review)['version']}"
            for review in reviews
        ]

    def test_bulk_remove_logs_each_item(self):
        response = self.client.post(
            self.bulk,
            {
                "action": "remove",
                "confirm": "yes",
                "reason": Reason.SPAM,
                "note": "Spam wave",
                "items": self.keys(self.held[:2]),
            },
            follow=True,
        )
        self.assertContains(response, "Removed 2 items")
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(
            ModerationRecord.objects.filter(
                action=ModerationRecord.Action.REMOVED
            ).count(),
            2,
        )

    def test_bulk_approve_publishes_only_held_items(self):
        self.client.post(
            self.bulk,
            {
                "action": "approve",
                "items": self.keys(self.held) + ["review:999999", "nope"],
            },
        )
        self.assertFalse(Review.objects.filter(is_held=True).exists())
        self.assertEqual(
            ModerationRecord.objects.filter(
                action=ModerationRecord.Action.APPROVED
            ).count(),
            3,
        )

    def test_bulk_requires_a_selection_and_a_valid_reason(self):
        self.assertContains(
            self.client.post(
                self.bulk, {"action": "remove", "reason": Reason.SPAM}, follow=True
            ),
            "Select at least one item",
        )
        response = self.client.post(
            self.bulk,
            {
                "action": "remove",
                "confirm": "yes",
                "reason": "",
                "items": self.keys(self.held),
            },
        )
        self.assertContains(response, "Choose a moderation reason.")
        self.assertTemplateUsed(response, "moderation/confirm_bulk_remove.html")
        self.assertEqual(Review.objects.count(), 3)

    def test_contributors_cannot_approve_or_bulk_act(self):
        self.client.force_login(make_user("contributor"))
        self.assertEqual(
            self.client.post(
                reverse("moderation:approve", args=["review", self.held[0].pk]),
                {"version": REVIEW.describe(self.held[0])["version"]},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                self.bulk, {"action": "approve", "items": self.keys(self.held)}
            ).status_code,
            403,
        )
        self.assertEqual(Review.objects.filter(is_held=True).count(), 3)

    def test_approving_a_published_review_returns_404(self):
        published = Review.objects.create(
            hotspot=self.hotspots[0], author=make_user("fine"), rating=5, body="Good"
        )
        self.assertEqual(
            self.client.post(
                reverse("moderation:approve", args=["review", published.pk])
            ).status_code,
            404,
        )

    def test_administration_page_shows_held_count(self):
        self.assertEqual(
            self.client.get(reverse("accounts:admin_home")).context["held_count"], 3
        )
