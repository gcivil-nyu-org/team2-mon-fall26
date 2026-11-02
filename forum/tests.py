from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from hotspots.tests import make_hotspot
from reviews.models import Review
from reviews.services import rating_summary

from .models import ForumComment, ForumPost, ForumVote

User = get_user_model()


def make_user(username):
    return User.objects.create_user(username=username, password="Transit-Wifi-2026!")


class ForumTests(TestCase):
    def setUp(self):
        self.author = make_user("forum-author")
        self.reader = make_user("forum-reader")
        self.post = ForumPost.objects.create(
            author=self.author,
            topic_type=ForumPost.TopicType.QUESTION,
            title="Where can I find quiet Wi-Fi near NYU?",
            body="I need a quiet place for a video call.",
        )

    def test_discussions_and_comments_are_public(self):
        comment = ForumComment.objects.create(
            post=self.post,
            author=self.author,
            body="Try the library.",
        )
        self.assertEqual(self.client.get(reverse("forum:list")).status_code, 200)
        response = self.client.get(reverse("forum:detail", args=[self.post.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.post.title)
        self.assertContains(response, comment.body)
        self.assertNotContains(response, "Your rating")

    def test_contributor_can_create_question_with_optional_hotspot_reference(self):
        hotspot = make_hotspot()
        self.client.force_login(self.reader)
        response = self.client.post(
            reverse("forum:create"),
            {
                "topic_type": ForumPost.TopicType.DISCUSSION,
                "title": "Good spots for video calls",
                "body": "Where can I take a call?",
                "hotspot": hotspot.pk,
            },
        )
        created = ForumPost.objects.get(title="Good spots for video calls")
        self.assertRedirects(response, reverse("forum:detail", args=[created.pk]))
        self.assertEqual((created.author, created.hotspot), (self.reader, hotspot))
        self.assertFalse(Review.objects.exists())

    def test_inactive_hotspots_cannot_be_linked(self):
        hotspot = make_hotspot()
        hotspot.is_active = False
        hotspot.save()
        self.client.force_login(self.reader)
        response = self.client.post(
            reverse("forum:create"),
            {
                "topic_type": ForumPost.TopicType.QUESTION,
                "title": "A discussion",
                "body": "Question text.",
                "hotspot": hotspot.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ForumPost.objects.filter(title="A discussion").exists())

    def test_invalid_post_does_not_create_topic(self):
        self.client.force_login(self.reader)
        response = self.client.post(
            reverse("forum:create"),
            {"topic_type": "invalid", "title": "", "body": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ForumPost.objects.count(), 1)

    def test_commenter_can_reply_and_parent_must_belong_to_post(self):
        parent = ForumComment.objects.create(
            post=self.post,
            author=self.author,
            body="Original comment",
        )
        other_post = ForumPost.objects.create(
            author=self.author,
            topic_type=ForumPost.TopicType.DISCUSSION,
            title="Different topic",
            body="Another conversation.",
        )
        other_comment = ForumComment.objects.create(
            post=other_post,
            author=self.author,
            body="Different thread",
        )
        self.client.force_login(self.reader)
        response = self.client.post(
            reverse("forum:comment", args=[self.post.pk]),
            {"body": "Here is a reply.", "parent_id": parent.pk},
        )
        reply = ForumComment.objects.get(body="Here is a reply.")
        self.assertEqual(reply.parent, parent)
        self.assertRedirects(
            response,
            f"{reverse('forum:detail', args=[self.post.pk])}#comment-{reply.pk}",
            fetch_redirect_response=False,
        )
        response = self.client.post(
            reverse("forum:comment", args=[self.post.pk]),
            {"body": "Wrong thread.", "parent_id": other_comment.pk},
        )
        self.assertEqual(response.status_code, 404)

    def test_visitors_must_sign_in_to_create_comment_or_vote(self):
        response = self.client.post(reverse("forum:create"), {})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        response = self.client.post(
            reverse("forum:comment", args=[self.post.pk]),
            {"body": "Anonymous comment"},
        )
        self.assertIn("/accounts/login/", response["Location"])
        response = self.client.post(reverse("forum:post_vote", args=[self.post.pk]))
        self.assertIn("/accounts/login/", response["Location"])
        self.assertFalse(ForumComment.objects.exists())
        self.assertFalse(ForumVote.objects.exists())

    def test_helpful_votes_toggle_for_post_and_comment(self):
        comment = ForumComment.objects.create(
            post=self.post,
            author=self.author,
            body="An answer.",
        )
        self.client.force_login(self.reader)
        self.client.post(reverse("forum:post_vote", args=[self.post.pk]))
        self.client.post(reverse("forum:comment_vote", args=[comment.pk]))
        self.assertTrue(
            ForumVote.objects.filter(user=self.reader, post=self.post).exists()
        )
        self.assertTrue(
            ForumVote.objects.filter(user=self.reader, comment=comment).exists()
        )

        self.client.post(reverse("forum:post_vote", args=[self.post.pk]))
        self.client.post(reverse("forum:comment_vote", args=[comment.pk]))
        self.assertFalse(ForumVote.objects.exists())

    def test_authors_cannot_vote_for_their_own_content(self):
        self.client.force_login(self.author)
        self.client.post(reverse("forum:post_vote", args=[self.post.pk]))
        comment = ForumComment.objects.create(
            post=self.post,
            author=self.author,
            body="My comment",
        )
        self.client.post(reverse("forum:comment_vote", args=[comment.pk]))
        self.assertFalse(ForumVote.objects.exists())

    def test_duplicate_user_votes_are_rejected_by_database(self):
        ForumVote.objects.create(user=self.reader, post=self.post)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ForumVote.objects.create(user=self.reader, post=self.post)

    def test_forum_votes_do_not_change_hotspot_rating_average(self):
        hotspot = make_hotspot()
        review = Review.objects.create(
            hotspot=hotspot,
            author=self.author,
            rating=4,
            body="A real hotspot review.",
        )
        self.post.hotspot = hotspot
        self.post.save()
        before = rating_summary(Review.objects.filter(hotspot=hotspot))
        self.client.force_login(self.reader)
        self.client.post(reverse("forum:post_vote", args=[self.post.pk]))
        after = rating_summary(Review.objects.filter(hotspot=hotspot))
        self.assertEqual(before, after)
        self.assertEqual(after["average"], 4.0)
        self.assertEqual(Review.objects.get(pk=review.pk).rating, 4)

    def test_list_vote_counts_are_not_multiplied_by_comments(self):
        other_reader = make_user("another-forum-reader")
        ForumVote.objects.create(user=self.reader, post=self.post)
        ForumVote.objects.create(user=other_reader, post=self.post)
        for index in range(3):
            ForumComment.objects.create(
                post=self.post,
                author=self.author,
                body=f"Answer {index}",
            )
        self.client.force_login(self.reader)

        response = self.client.get(reverse("forum:list"))

        listed_post = response.context["posts"].get(pk=self.post.pk)
        self.assertEqual(listed_post.comment_count, 3)
        self.assertEqual(listed_post.vote_count, 2)
        self.assertEqual(listed_post.user_vote_count, 1)

    def test_malformed_reply_parent_is_rejected_without_creating_comment(self):
        self.client.force_login(self.reader)

        response = self.client.post(
            reverse("forum:comment", args=[self.post.pk]),
            {"body": "Reply text", "parent_id": "not-a-comment-id"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ForumComment.objects.exists())

    def test_deep_reply_thread_renders_without_recursive_template_failure(self):
        parent = None
        for index in range(300):
            parent = ForumComment.objects.create(
                post=self.post,
                author=self.author,
                parent=parent,
                body=f"Nested answer {index}",
            )

        response = self.client.get(reverse("forum:detail", args=[self.post.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nested answer 299")
        self.assertEqual(response.context["comment_count"], 300)

    def test_replies_stay_under_their_parent_before_the_next_root_comment(self):
        first = ForumComment.objects.create(
            post=self.post,
            author=self.author,
            body="First root answer",
        )
        second = ForumComment.objects.create(
            post=self.post,
            author=self.author,
            body="Second root answer",
        )
        reply = ForumComment.objects.create(
            post=self.post,
            author=self.reader,
            parent=first,
            body="First answer reply",
        )

        response = self.client.get(reverse("forum:detail", args=[self.post.pk]))

        html = response.content.decode()
        self.assertLess(html.index(first.body), html.index(reply.body))
        self.assertLess(html.index(reply.body), html.index(second.body))
