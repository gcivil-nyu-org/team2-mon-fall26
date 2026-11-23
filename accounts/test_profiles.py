"""Public user profiles: totals, badges and recent public activity only."""

from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from availability.models import AvailabilityReport
from forum.models import ForumComment, ForumPost
from hotspots.tests import make_hotspot
from reviews.models import Review, ReviewReply, ReviewVote

from .tests import make_administrator, make_user


def profile_url(user):
    return reverse("accounts:profile", args=[user.username])


class ProfilePageTests(TestCase):
    def setUp(self):
        self.user = make_user("maria")
        self.hotspot = make_hotspot()

    def test_anyone_can_view_a_profile(self):
        page = self.client.get(profile_url(self.user))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "maria")
        self.assertContains(page, "Member since")
        self.assertContains(page, "No badges yet")

    def test_unknown_and_inactive_users_are_not_found(self):
        self.assertEqual(
            self.client.get(reverse("accounts:profile", args=["nobody"])).status_code,
            404,
        )
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get(profile_url(self.user)).status_code, 404)

    def test_shows_public_activity_and_totals(self):
        review = Review.objects.create(
            hotspot=self.hotspot, author=self.user, rating=5, body="Strong signal."
        )
        for index in range(2):
            ReviewVote.objects.create(review=review, user=make_user(f"fan{index}"))
        ReviewVote.objects.create(
            review=review, user=make_user("critic"), value=ReviewVote.DOWN
        )
        other_review = Review.objects.create(
            hotspot=make_hotspot(2000), author=make_user("ana"), rating=3, body="Ok."
        )
        ReviewReply.objects.create(
            review=other_review, author=self.user, body="Agreed with this."
        )
        post = ForumPost.objects.create(
            author=self.user,
            topic_type=ForumPost.TopicType.QUESTION,
            title="Best Wi-Fi in Midtown?",
            body="Looking for somewhere quiet.",
        )
        ForumComment.objects.create(post=post, author=self.user, body="Bump.")
        AvailabilityReport.objects.create(
            hotspot=self.hotspot,
            reporter=self.user,
            status=AvailabilityReport.Status.WORKING,
        )
        page = self.client.get(profile_url(self.user))
        stats = page.context["stats"]
        self.assertEqual(
            stats,
            {
                "reviews": 1,
                "helpful_votes": 2,
                "replies": 1,
                "reports": 1,
                "posts": 1,
                "comments": 1,
            },
        )
        self.assertContains(page, "Strong signal.")
        self.assertContains(page, "▲ 2 · ▼ 1")
        self.assertContains(page, "Best Wi-Fi in Midtown?")
        self.assertContains(page, "Reply to ana")
        self.assertContains(page, "First review")

    def test_hidden_content_is_never_shown(self):
        Review.objects.create(
            hotspot=self.hotspot,
            author=self.user,
            rating=1,
            body="Held text",
            is_held=True,
        )
        Review.objects.create(hotspot=make_hotspot(2000), author=self.user, rating=4)
        retired = make_hotspot(3000)
        Review.objects.create(
            hotspot=retired, author=self.user, rating=2, body="Retired text"
        )
        retired.is_active = False
        retired.save()
        ForumPost.objects.create(
            author=self.user,
            topic_type=ForumPost.TopicType.DISCUSSION,
            title="Held topic",
            body="Body.",
            is_held=True,
        )
        page = self.client.get(profile_url(self.user))
        self.assertEqual(page.context["stats"]["reviews"], 0)
        self.assertEqual(page.context["stats"]["posts"], 0)
        for text in ("Held text", "Retired text", "Held topic"):
            self.assertNotContains(page, text)
        # Star-only ratings stay anonymous to others (#100).
        self.assertIsNone(page.context["rating_count"])
        self.assertNotContains(page, "published rating")

    def test_own_profile_shows_private_counts_and_settings_link(self):
        Review.objects.create(hotspot=self.hotspot, author=self.user, rating=4)
        Review.objects.create(
            hotspot=make_hotspot(2000),
            author=self.user,
            rating=1,
            body="Held",
            is_held=True,
        )
        self.client.force_login(self.user)
        page = self.client.get(profile_url(self.user))
        self.assertContains(page, "This is how other people see your profile.")
        self.assertContains(page, "You have 1 published rating")
        self.assertContains(page, "1 of your reviews is waiting for a moderator")
        self.assertContains(page, reverse("accounts:settings"))
        # The header name links to your own profile.
        self.assertContains(
            self.client.get(reverse("hotspots:map")), f'href="{profile_url(self.user)}"'
        )

    def test_badges(self):
        trusted_age = timezone.now() - timedelta(days=3)
        boroughs = ["Manhattan", "Brooklyn", "Queens"]
        for index, borough in enumerate(boroughs):
            review = Review.objects.create(
                hotspot=make_hotspot(5000 + index, borough=borough),
                author=self.user,
                rating=4,
                body=f"Review number {index} with details.",
            )
            Review.objects.filter(pk=review.pk).update(created_at=trusted_age)
            for voter in range(2):
                ReviewVote.objects.create(
                    review=review, user=make_user(f"v{index}{voter}")
                )
        for index in range(5):
            AvailabilityReport.objects.create(
                hotspot=make_hotspot(6000 + index),
                reporter=self.user,
                status=AvailabilityReport.Status.WORKING,
            )
        for index in range(3):
            ForumPost.objects.create(
                author=self.user,
                topic_type=ForumPost.TopicType.QUESTION,
                title=f"Question {index}",
                body="Body.",
            )
        labels = {
            badge.label
            for badge in self.client.get(profile_url(self.user)).context["badges"]
        }
        self.assertEqual(
            labels,
            {
                "Trusted reviewer",
                "First review",
                "Borough explorer",
                "Helpful voice",
                "Signal scout",
                "Conversation starter",
            },
        )
        admin = make_administrator()
        self.assertIn(
            "Moderator",
            {
                badge.label
                for badge in self.client.get(profile_url(admin)).context["badges"]
            },
        )

    def test_author_names_link_to_profiles(self):
        review = Review.objects.create(
            hotspot=self.hotspot, author=self.user, rating=5, body="Linked."
        )
        ReviewReply.objects.create(review=review, author=make_user("ana"), body="Hi.")
        post = ForumPost.objects.create(
            author=self.user,
            topic_type=ForumPost.TopicType.QUESTION,
            title="Linked topic",
            body="Body.",
        )
        profile_page = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(profile_page, f'href="{profile_url(self.user)}"')
        self.assertContains(
            profile_page, f'href="{reverse("accounts:profile", args=["ana"])}"'
        )
        self.assertContains(
            self.client.get(post.get_absolute_url()), f'href="{profile_url(self.user)}"'
        )

    @override_settings(DEMO_MODE=True)
    def test_demo_review_authors_are_not_linked(self):
        demo_author = make_user("demo_ana")
        Review.objects.create(
            hotspot=self.hotspot,
            author=demo_author,
            rating=5,
            body="Demo.",
            is_demo=True,
        )
        page = self.client.get(self.hotspot.get_absolute_url())
        self.assertNotContains(page, profile_url(demo_author))
