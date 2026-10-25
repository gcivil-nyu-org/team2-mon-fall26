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


from django.urls import reverse  # noqa: E402

from .models import ReviewVote  # noqa: E402

PASSWORD = "Transit-Wifi-2026!"


def sign_in(client, username="alex"):
    user = get_user_model().objects.create_user(username=username, password=PASSWORD)
    client.force_login(user)
    return user


class ContributionTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.create_url = reverse("reviews:create", args=[self.hotspot.pk])
        self.detail_url = self.hotspot.get_absolute_url()

    def test_visitor_is_sent_to_login_and_cannot_post(self):
        response = self.client.post(self.create_url, {"rating": 5})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertFalse(Review.objects.exists())

    def test_signed_in_user_saves_rating_with_optional_review(self):
        user = sign_in(self.client)
        response = self.client.post(self.create_url, {"rating": "4", "body": "  Fast and steady.  "})
        self.assertRedirects(response, f"{self.detail_url}#reviews", fetch_redirect_response=False)
        review = Review.objects.get()
        self.assertEqual((review.hotspot, review.author, review.rating, review.body), (self.hotspot, user, 4, "Fast and steady."))

    def test_rating_alone_is_allowed_and_counts_toward_average(self):
        sign_in(self.client)
        self.client.post(self.create_url, {"rating": "3"})
        self.assertEqual(rating_summary(Review.objects.all())["average"], 3.0)

    def test_invalid_rating_is_rejected(self):
        sign_in(self.client)
        for data in [{}, {"rating": "0"}, {"rating": "6"}, {"rating": "abc"}]:
            with self.subTest(data=data):
                response = self.client.post(self.create_url, data)
                self.assertEqual(response.status_code, 200)
        self.assertFalse(Review.objects.exists())

    def test_second_submission_redirects_to_edit_instead_of_duplicating(self):
        sign_in(self.client)
        self.client.post(self.create_url, {"rating": "4"})
        response = self.client.post(self.create_url, {"rating": "1"})
        review = Review.objects.get()
        self.assertEqual(review.rating, 4)
        self.assertRedirects(response, reverse("reviews:edit", args=[review.pk]))

    def test_inactive_hotspot_is_not_reviewable(self):
        sign_in(self.client)
        self.hotspot.is_active = False
        self.hotspot.save()
        self.assertEqual(self.client.post(self.create_url, {"rating": "4"}).status_code, 404)

    def test_one_review_per_author_per_hotspot_in_database(self):
        user = get_user_model().objects.create_user(username="dup")
        Review.objects.create(hotspot=self.hotspot, author=user, rating=4)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(hotspot=self.hotspot, author=user, rating=5)


class EditDeleteTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.owner = get_user_model().objects.create_user(username="owner", password=PASSWORD)
        self.other = get_user_model().objects.create_user(username="other", password=PASSWORD)
        self.review = Review.objects.create(hotspot=self.hotspot, author=self.owner, rating=2, body="Slow.")
        self.edit_url = reverse("reviews:edit", args=[self.review.pk])
        self.delete_url = reverse("reviews:delete", args=[self.review.pk])

    def test_edit_and_delete_links_only_appear_for_the_author(self):
        detail = self.hotspot.get_absolute_url()
        self.assertNotContains(self.client.get(detail), self.edit_url)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(detail), self.edit_url)
        self.client.force_login(self.owner)
        page = self.client.get(detail)
        self.assertContains(page, self.edit_url)
        self.assertContains(page, self.delete_url)

    def test_owner_can_change_rating_and_text_and_average_updates(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.edit_url, {"rating": "5", "body": "Much better now."})
        self.assertEqual(response.status_code, 302)
        self.review.refresh_from_db()
        self.assertEqual((self.review.rating, self.review.body), (5, "Much better now."))
        self.assertContains(self.client.get(self.hotspot.get_absolute_url()), "Much better now.")
        self.assertEqual(rating_summary(Review.objects.all())["average"], 5.0)

    def test_other_users_and_visitors_cannot_edit_or_delete(self):
        for url in (self.edit_url, self.delete_url):
            with self.subTest(url=url, who="visitor"):
                self.assertEqual(self.client.post(url, {"rating": "1"}).status_code, 302)
        self.client.force_login(self.other)
        for url in (self.edit_url, self.delete_url):
            with self.subTest(url=url, who="other"):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {"rating": "1"}).status_code, 404)
        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 2)

    def test_delete_requires_confirmation_and_updates_average(self):
        self.client.force_login(self.owner)
        confirm = self.client.get(self.delete_url)
        self.assertContains(confirm, "Delete your rating and review?")
        self.assertTrue(Review.objects.exists())
        self.client.post(self.delete_url)
        self.assertFalse(Review.objects.exists())
        self.assertNotContains(self.client.get(self.hotspot.get_absolute_url()), "Slow.")
        self.assertIsNone(rating_summary(Review.objects.all())["average"])


    @override_settings(DEMO_MODE=True)
    def test_demo_reviews_cannot_be_edited(self):
        self.review.is_demo = True
        self.review.save()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.edit_url).status_code, 404)


class UpvoteTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.author = get_user_model().objects.create_user(username="author", password=PASSWORD)
        self.voter = get_user_model().objects.create_user(username="voter", password=PASSWORD)
        self.review = Review.objects.create(hotspot=self.hotspot, author=self.author, rating=3, body="Okay.")
        self.url = reverse("reviews:vote", args=[self.review.pk])

    def test_visitor_cannot_vote_and_vote_requires_post(self):
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.assertFalse(ReviewVote.objects.exists())
        self.client.force_login(self.voter)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_user_upvotes_once_and_can_remove_vote(self):
        self.client.force_login(self.voter)
        self.client.post(self.url)
        self.assertEqual(ReviewVote.objects.count(), 1)
        self.assertContains(self.client.get(self.hotspot.get_absolute_url()), "Remove upvote · 1")
        self.client.post(self.url)
        self.assertEqual(ReviewVote.objects.count(), 0)

    def test_vote_count_is_shown_and_does_not_change_average(self):
        ReviewVote.objects.create(review=self.review, user=self.voter)
        page = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(page, "1 found this helpful")
        self.assertEqual(rating_summary(Review.objects.all())["average"], 3.0)

    def test_votes_are_database_unique(self):
        ReviewVote.objects.create(review=self.review, user=self.voter)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReviewVote.objects.create(review=self.review, user=self.voter)

    def test_author_cannot_upvote_own_review(self):
        self.client.force_login(self.author)
        self.client.post(self.url)
        self.assertFalse(ReviewVote.objects.exists())

    def test_vote_redirect_ignores_offsite_next(self):
        self.client.force_login(self.voter)
        response = self.client.post(self.url, {"next": "https://evil.example/"})
        self.assertTrue(response["Location"].startswith(self.hotspot.get_absolute_url()))
