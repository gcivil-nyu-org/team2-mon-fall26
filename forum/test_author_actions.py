from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.tests import make_user
from hotspots.tests import make_hotspot
from moderation.models import ContentFlag, Reason
from moderation.registry import FORUM_COMMENT, FORUM_POST
from moderation.services import approve

from .models import ForumComment, ForumPost, ForumVote


class ForumAuthorActionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = make_user("TopicAuthor")
        cls.reader = make_user("ReplyAuthor")
        cls.hotspot = make_hotspot()
        cls.topic = ForumPost.objects.create(
            author=cls.author,
            topic_type=ForumPost.TopicType.QUESTION,
            title="Library Wi-Fi hours",
            body="When is the library connection available?",
            hotspot=cls.hotspot,
        )
        cls.reply = ForumComment.objects.create(
            author=cls.reader, post=cls.topic, body="It was available on Saturday."
        )

    def setUp(self):
        self.client.force_login(self.author)

    def action(self, name, obj):
        return reverse(f"forum:{name}", args=[obj.pk])

    def test_only_authors_see_controls_and_can_use_their_own_routes(self):
        detail = self.topic.get_absolute_url()
        topic_edit = self.action("edit_post", self.topic)
        reply_edit = self.action("edit_comment", self.reply)
        page = self.client.get(detail)
        self.assertContains(page, topic_edit)
        self.assertNotContains(page, reply_edit)
        visitor = Client()
        self.assertNotContains(visitor.get(detail), topic_edit)
        self.assertEqual(visitor.post(topic_edit).status_code, 302)
        for action in ("edit_comment", "delete_comment"):
            self.assertEqual(
                self.client.post(self.action(action, self.reply)).status_code, 404
            )
        self.client.force_login(self.reader)
        page = self.client.get(detail)
        self.assertNotContains(page, topic_edit)
        self.assertContains(page, reply_edit)
        for action in ("edit_post", "delete_post"):
            self.assertEqual(
                self.client.post(self.action(action, self.topic)).status_code, 404
            )

    def test_edit_prefills_fields_and_preserves_topic_type_hotspot_and_votes(self):
        url = self.action("edit_post", self.topic)
        ForumVote.objects.create(post=self.topic, user=self.reader)
        form = self.client.get(url).context["form"]
        self.assertEqual(list(form.fields), ["title", "body"])
        self.assertEqual(form.initial["body"], self.topic.body)
        data = {
            "title": "Weekend library Wi-Fi",
            "body": "The lobby opens at nine.",
            "hotspot": "",
            "topic_type": "discussion",
        }
        with patch("forum.views.notify.discussion_started") as announce:
            response = self.client.post(url, data)
        announce.assert_not_called()
        self.assertRedirects(response, self.topic.get_absolute_url())
        self.topic.refresh_from_db()
        self.assertEqual(
            (self.topic.title, self.topic.body), (data["title"], data["body"])
        )
        self.assertEqual(self.topic.hotspot, self.hotspot)
        self.assertEqual(self.topic.topic_type, ForumPost.TopicType.QUESTION)
        self.assertTrue(self.topic.votes.filter(user=self.reader).exists())

    @override_settings(MODERATION_BLOCKED_TERMS=["fixtureword"])
    def test_invalid_edits_keep_entered_values_and_original_record(self):
        url = self.action("edit_post", self.topic)
        response = self.client.post(
            url, {"title": "Updated title", "body": "fixtureword"}
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("body", form.errors)
        self.assertEqual(form["title"].value(), "Updated title")
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.title, "Library Wi-Fi hours")

    def test_edit_of_published_text_can_place_it_on_hold(self):
        self.client.force_login(self.reader)
        response = self.client.post(
            self.action("edit_comment", self.reply),
            {"body": "THE LIBRARY HOURS HAVE CHANGED THIS MONTH"},
        )
        self.assertEqual(response.status_code, 302)
        self.reply.refresh_from_db()
        self.assertTrue(self.reply.is_held)
        self.assertNotContains(
            Client().get(self.topic.get_absolute_url()), self.reply.body
        )

    def test_edit_to_held_comment_preserves_hold_and_invalidates_stale_approval(self):
        self.reply.is_held = True
        self.reply.save(update_fields=["is_held"])
        version = FORUM_COMMENT.describe(self.reply)["version"]
        self.client.force_login(self.reader)
        url = self.action("edit_comment", self.reply)
        self.assertContains(self.client.get(url), self.reply.body)
        updated = "The library posted its weekend hours."
        response = self.client.post(url, {"body": updated})
        self.assertEqual(
            response.url, f"{self.topic.get_absolute_url()}#comment-{self.reply.pk}"
        )
        self.reply.refresh_from_db()
        self.assertEqual(self.reply.body, updated)
        self.assertTrue(self.reply.is_held)
        self.assertIsNotNone(self.reply.edited_at)
        self.assertIsNone(approve(FORUM_COMMENT, self.reply, self.author, version))
        self.assertNotContains(Client().get(self.topic.get_absolute_url()), updated)

    def test_removing_topic_with_replies_preserves_others_and_withdraws_topic_flags(
        self,
    ):
        flag = ContentFlag.objects.create(
            content_object=self.topic, flagged_by=self.reader, reason=Reason.OTHER
        )
        ForumVote.objects.create(post=self.topic, user=self.reader)
        url = self.action("delete_post", self.topic)
        self.assertContains(self.client.get(url), "Cancel")
        self.assertEqual(
            ForumPost.objects.get(pk=self.topic.pk).title, self.topic.title
        )
        self.assertRedirects(self.client.post(url), self.topic.get_absolute_url())
        self.topic.refresh_from_db()
        self.assertTrue(self.topic.author_removed)
        self.assertEqual(self.topic.body, "")
        self.assertIsNone(self.topic.hotspot_id)
        self.assertFalse(self.topic.votes.exists())
        flag.refresh_from_db()
        self.assertEqual(flag.status, ContentFlag.Status.WITHDRAWN)
        public = Client().get(self.topic.get_absolute_url())
        self.assertContains(public, "Deleted discussion")
        self.assertContains(public, self.reply.body)
        self.assertNotContains(public, "Library Wi-Fi hours")
        self.assertNotContains(public, self.author.username)
        self.assertNotContains(
            Client().get(reverse("forum:list")), "Library Wi-Fi hours"
        )
        self.client.force_login(self.reader)
        self.assertEqual(
            self.client.post(
                self.action("comment", self.topic), {"body": "Later"}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(self.action("post_vote", self.topic)).status_code, 404
        )
        self.assertFalse(FORUM_POST.public_queryset().filter(pk=self.topic.pk).exists())
        self.assertRedirects(
            self.client.post(self.action("delete_comment", self.reply)),
            reverse("forum:list"),
        )
        self.assertFalse(ForumPost.objects.filter(pk=self.topic.pk).exists())

    def test_removing_comment_reparents_direct_replies_and_keeps_descendants(self):
        own = ForumComment.objects.create(
            post=self.topic, parent=self.reply, author=self.author, body="Old wording."
        )
        child = ForumComment.objects.create(
            post=self.topic, parent=own, author=self.reader, body="A useful follow-up."
        )
        grandchild = ForumComment.objects.create(
            post=self.topic, parent=child, author=self.reader, body="Clarification."
        )
        flag = ContentFlag.objects.create(
            content_object=child, flagged_by=self.author, reason=Reason.OTHER
        )
        url = self.action("delete_comment", own)
        self.assertContains(self.client.get(url), "Delete your comment?")
        self.assertTrue(ForumComment.objects.filter(pk=own.pk).exists())
        self.client.post(url)
        self.assertFalse(ForumComment.objects.filter(pk=own.pk).exists())
        child.refresh_from_db()
        grandchild.refresh_from_db()
        self.assertEqual(child.parent_id, self.reply.pk)
        self.assertEqual(grandchild.parent_id, child.pk)
        flag.refresh_from_db()
        self.assertEqual(flag.status, ContentFlag.Status.OPEN)

    def test_topic_without_replies_is_removed(self):
        self.reply.delete()
        self.assertRedirects(
            self.client.post(self.action("delete_post", self.topic)),
            reverse("forum:list"),
        )
        self.assertFalse(ForumPost.objects.filter(pk=self.topic.pk).exists())

    def test_withdrawal_never_publishes_a_held_topic(self):
        self.topic.is_held = True
        self.topic.save(update_fields=["is_held"])
        self.client.post(self.action("delete_post", self.topic))
        self.assertEqual(Client().get(self.topic.get_absolute_url()).status_code, 404)
        self.client.force_login(self.reader)
        self.assertEqual(
            self.client.get(self.action("edit_comment", self.reply)).status_code, 404
        )
