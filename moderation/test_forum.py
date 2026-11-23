"""E05 moderation applied to E08 discussion posts and comments.

The same rules as hotspot reviews: blocked at submit, held for an administrator,
community flags and auto-hide, approve/remove/dismiss, and E07 notifications.
"""

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.tests import make_administrator, make_established_user, make_user
from forum.models import ForumComment, ForumPost, ForumVote
from hotspots.models import HotspotFollow
from hotspots.tests import make_hotspot
from notifications.models import Notification

from . import services
from .automod import forum_hold_reasons
from .models import ContentFlag, ModerationRecord, Reason
from .registry import FORUM_COMMENT, FORUM_POST

Kind = Notification.Kind
CLEAN_BODY = "The library on the second floor has a strong, steady signal all day."


def make_post(author, title="Quiet Wi-Fi near NYU?", body=CLEAN_BODY, **fields):
    return ForumPost.objects.create(
        author=author,
        topic_type=ForumPost.TopicType.QUESTION,
        title=title,
        body=body,
        **fields,
    )


def flag(flaggable, obj, user, reason=Reason.SPAM):
    return ContentFlag.objects.create(
        content_type=ContentType.objects.get_for_model(flaggable.model),
        object_id=obj.pk,
        flagged_by=user,
        reason=reason,
    )


def inbox(user):
    return Notification.objects.filter(recipient=user)


class ForumBlockingTests(TestCase):
    def setUp(self):
        self.author = make_user("author")
        self.client.force_login(self.author)

    def test_post_with_a_link_is_rejected_and_not_saved(self):
        response = self.client.post(
            reverse("forum:create"),
            {
                "topic_type": "question",
                "title": "Free Wi-Fi list",
                "body": "See https://cheap.example for a list",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Discussion posts can&#x27;t include links")
        self.assertFalse(ForumPost.objects.exists())

    def test_link_in_the_title_is_rejected(self):
        self.client.post(
            reverse("forum:create"),
            {"topic_type": "question", "title": "visit cheapwifi.com", "body": "Hi"},
        )
        self.assertFalse(ForumPost.objects.exists())

    def test_comment_with_a_phone_number_is_rejected_with_the_reason(self):
        post = make_post(make_user("other"))
        response = self.client.post(
            reverse("forum:comment", args=[post.pk]),
            {"body": "Call 212-555-0187 for help"},
            follow=True,
        )
        self.assertFalse(ForumComment.objects.exists())
        self.assertContains(response, "Comments can&#x27;t include links")


class ForumHoldTests(TestCase):
    def setUp(self):
        self.hotspot = make_hotspot()
        self.author = make_user("author")
        self.reader = make_user("reader")
        self.follower = make_user("follower")
        HotspotFollow.objects.create(user=self.follower, hotspot=self.hotspot)

    def create_post(self, body):
        self.client.force_login(self.author)
        return self.client.post(
            reverse("forum:create"),
            {
                "topic_type": "discussion",
                "title": "Best spot in the park",
                "body": body,
                "hotspot": self.hotspot.pk,
            },
            follow=True,
        )

    def test_suspicious_post_is_held_and_visible_only_to_its_author(self):
        response = self.create_post("Use promo code SAVE10 at the cafe for a discount")
        post = ForumPost.objects.get()
        self.assertTrue(post.is_held)
        self.assertContains(response, "waiting for a moderator")
        self.assertContains(response, "Awaiting moderator approval")

        self.client.force_login(self.reader)
        detail = self.client.get(post.get_absolute_url())
        self.assertEqual(detail.status_code, 404)
        self.assertNotContains(self.client.get(reverse("forum:list")), post.title)
        self.client.logout()
        self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 404)

    def test_held_post_notifies_the_author_but_not_followers(self):
        self.create_post("Use promo code SAVE10 at the cafe for a discount")
        notice = inbox(self.author).get()
        self.assertEqual(notice.kind, Kind.REVIEW_HELD)
        self.assertEqual(notice.content_label, "post")
        self.assertIn("discussion post “Best spot in the park”", notice.text)
        self.assertFalse(inbox(self.follower).exists())
        opened = self.client.get(reverse("notifications:open", args=[notice.pk]))
        self.assertRedirects(
            opened,
            ForumPost.objects.get().get_absolute_url(),
            fetch_redirect_response=False,
        )

    def test_clean_post_is_published_and_announced(self):
        self.create_post(CLEAN_BODY)
        self.assertFalse(ForumPost.objects.get().is_held)
        self.assertEqual(inbox(self.follower).get().kind, Kind.FOLLOWED_DISCUSSION)

    def test_approval_publishes_and_announces_once(self):
        self.create_post("Use promo code SAVE10 at the cafe for a discount")
        post = ForumPost.objects.get()
        admin = make_administrator()
        self.client.force_login(admin)
        self.client.post(
            reverse("moderation:approve", args=["post", post.pk]),
            {"version": FORUM_POST.describe(post)["version"]},
        )
        post.refresh_from_db()
        self.assertFalse(post.is_held)
        self.assertEqual(
            ModerationRecord.objects.get().action, ModerationRecord.Action.APPROVED
        )
        self.assertIn(
            Kind.REVIEW_APPROVED, inbox(self.author).values_list("kind", flat=True)
        )
        self.assertEqual(inbox(self.follower).count(), 1)

        # Hidden again by flags and approved again: followers are not told twice.
        for name in ("a", "b", "c"):
            flag(FORUM_POST, post, make_established_user(name))
        services.auto_hide_if_widely_flagged(FORUM_POST, post)
        post.refresh_from_db()
        self.assertTrue(post.is_held)
        services.approve(FORUM_POST, post, admin)
        self.assertEqual(inbox(self.follower).count(), 1)

    def test_held_post_takes_no_comments_or_votes(self):
        post = make_post(self.author, is_held=True)
        self.client.force_login(self.reader)
        self.assertEqual(
            self.client.post(
                reverse("forum:comment", args=[post.pk]), {"body": "Hi"}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("forum:post_vote", args=[post.pk])).status_code,
            404,
        )
        self.assertFalse(ForumComment.objects.exists())
        self.assertFalse(ForumVote.objects.exists())

    def test_held_post_appears_in_the_admin_queue(self):
        self.create_post("Use promo code SAVE10 at the cafe for a discount")
        item = services.held_items()[0]
        self.assertIs(item["type"], FORUM_POST)
        self.assertIn("Promotional wording: promo code", item["automated"][0])
        self.client.force_login(make_administrator())
        response = self.client.get(reverse("moderation:queue"))
        self.assertContains(response, "Discussion post")
        self.assertContains(response, "Best spot in the park")


class ForumCommentHoldTests(TestCase):
    def setUp(self):
        self.author = make_user("author")
        self.commenter = make_user("commenter")
        self.reader = make_user("reader")
        self.post = make_post(self.author)

    def test_suspicious_comment_is_held_and_hidden_from_others(self):
        self.client.force_login(self.commenter)
        response = self.client.post(
            reverse("forum:comment", args=[self.post.pk]),
            {"body": "DM me on telegram for faster internet"},
            follow=True,
        )
        comment = ForumComment.objects.get()
        self.assertTrue(comment.is_held)
        self.assertContains(response, "telegram")
        self.assertContains(response, "Awaiting moderator approval")
        self.assertEqual(inbox(self.commenter).get().content_label, "comment")

        self.client.force_login(self.reader)
        response = self.client.get(self.post.get_absolute_url())
        self.assertNotContains(response, "telegram")
        self.assertNotContains(response, "hidden while a moderator")
        self.assertEqual(response.context["comment_count"], 0)
        listing = self.client.get(reverse("forum:list"))
        self.assertEqual(listing.context["posts"][0].comment_count, 0)

    def test_hidden_comment_with_public_replies_keeps_a_placeholder(self):
        parent = ForumComment.objects.create(
            post=self.post, author=self.commenter, body="Original", is_held=True
        )
        ForumComment.objects.create(
            post=self.post, author=self.author, parent=parent, body="Useful reply"
        )
        self.client.force_login(self.reader)
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, "hidden while a moderator reviews it")
        self.assertContains(response, "Useful reply")
        self.assertNotContains(response, "Original")

    def test_cannot_reply_to_or_vote_on_a_held_comment(self):
        held = ForumComment.objects.create(
            post=self.post, author=self.commenter, body="Held text", is_held=True
        )
        self.client.force_login(self.reader)
        self.assertEqual(
            self.client.post(
                reverse("forum:comment", args=[self.post.pk]),
                {"body": "Reply", "parent_id": held.pk},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("forum:comment_vote", args=[held.pk])).status_code,
            404,
        )

    @override_settings(MODERATION_COMMENT_BURST_LIMIT=2)
    def test_fast_commenting_is_held(self):
        for body in ("First thought here", "Second thought here"):
            ForumComment.objects.create(
                post=self.post, author=self.commenter, body=body
            )
        comment = ForumComment.objects.create(
            post=self.post, author=self.commenter, body="Third thought here"
        )
        details = [detail for _, detail in forum_hold_reasons(comment)]
        self.assertIn("Posting many comments in a short time", details)

    def test_trusted_forum_author_skips_style_rules(self):
        old = timezone.now() - timedelta(days=2)
        for index in range(3):
            post = make_post(
                self.commenter, title=f"Topic {index}", body=f"Body {index}"
            )
            ForumPost.objects.filter(pk=post.pk).update(created_at=old)
        comment = ForumComment.objects.create(
            post=self.post,
            author=self.commenter,
            body="THE SIGNAL IS EXCELLENT ON THE NORTH SIDE TODAY",
        )
        self.assertEqual(forum_hold_reasons(comment), [])
        newcomer = ForumComment.objects.create(
            post=self.post,
            author=self.reader,
            body="THE SIGNAL IS EXCELLENT ON THE NORTH SIDE TODAY!!",
        )
        self.assertIn(
            "Mostly written in capital letters",
            [detail for _, detail in forum_hold_reasons(newcomer)],
        )


class ForumFlagTests(TestCase):
    def setUp(self):
        self.author = make_user("author")
        self.reader = make_user("reader")
        self.post = make_post(self.author)
        self.comment = ForumComment.objects.create(
            post=self.post, author=self.author, body="Try the third floor."
        )

    def test_flag_links_show_for_other_users_content_only(self):
        self.client.force_login(self.reader)
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(
            response, reverse("moderation:flag", args=["post", self.post.pk])
        )
        self.assertContains(
            response, reverse("moderation:flag", args=["comment", self.comment.pk])
        )
        self.client.force_login(self.author)
        response = self.client.get(self.post.get_absolute_url())
        self.assertNotContains(response, "/flag/")

    def test_contributor_flags_a_comment_once(self):
        self.client.force_login(self.reader)
        url = reverse("moderation:flag", args=["comment", self.comment.pk])
        self.assertContains(self.client.get(url), "Try the third floor.")
        response = self.client.post(url, {"reason": Reason.OFF_TOPIC})
        self.assertRedirects(
            response,
            f"{self.post.get_absolute_url()}#comment-{self.comment.pk}",
            fetch_redirect_response=False,
        )
        self.assertEqual(ContentFlag.objects.count(), 1)
        self.client.post(url, {"reason": Reason.SPAM})
        self.assertEqual(ContentFlag.objects.count(), 1)
        page = self.client.get(self.post.get_absolute_url())
        self.assertContains(page, "Flagged for review")
        self.assertIs(services.flagged_items()[0]["type"], FORUM_COMMENT)

    def test_authors_cannot_flag_their_own_post(self):
        self.client.force_login(self.author)
        self.client.post(
            reverse("moderation:flag", args=["post", self.post.pk]),
            {"reason": Reason.SPAM},
        )
        self.assertFalse(ContentFlag.objects.exists())

    def test_held_content_cannot_be_flagged(self):
        ForumPost.objects.filter(pk=self.post.pk).update(is_held=True)
        self.client.force_login(self.reader)
        response = self.client.get(
            reverse("moderation:flag", args=["comment", self.comment.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_third_flag_hides_a_post_and_tells_its_author(self):
        for name in ("a", "b", "c"):
            self.client.force_login(make_established_user(name))
            self.client.post(
                reverse("moderation:flag", args=["post", self.post.pk]),
                {"reason": Reason.SPAM},
            )
        self.post.refresh_from_db()
        self.assertTrue(self.post.is_held)
        notice = inbox(self.author).get()
        self.assertEqual(notice.kind, Kind.REVIEW_HIDDEN)
        self.assertIn("hidden after several community flags", notice.text)


class ForumDecisionTests(TestCase):
    def setUp(self):
        self.author = make_user("author")
        self.replier = make_user("replier")
        self.flagger = make_user("flagger")
        self.admin = make_administrator()
        self.post = make_post(self.author, title="Cheap internet here")
        self.comment = ForumComment.objects.create(
            post=self.post, author=self.replier, body="Spammy reply"
        )
        self.client.force_login(self.admin)

    def test_removing_a_post_removes_its_comments_and_logs_the_text(self):
        flag(FORUM_POST, self.post, self.flagger)
        comment_flag = flag(FORUM_COMMENT, self.comment, self.flagger)
        confirm = self.client.get(
            reverse("moderation:remove", args=["post", self.post.pk])
        )
        self.assertContains(confirm, "Its 1 comment and replies are removed with it.")
        self.client.post(
            reverse("moderation:remove", args=["post", self.post.pk]),
            {"reason": Reason.SPAM},
        )
        self.assertFalse(ForumPost.objects.exists())
        self.assertFalse(ForumComment.objects.exists())
        record = ModerationRecord.objects.get()
        self.assertEqual(record.content_label, "Discussion post")
        self.assertIn("Cheap internet here", record.content_text)
        self.assertEqual(record.flag_count, 1)
        comment_flag.refresh_from_db()
        self.assertEqual(comment_flag.status, ContentFlag.Status.WITHDRAWN)

        removed = inbox(self.author).get()
        self.assertEqual(removed.kind, Kind.REVIEW_REMOVED)
        self.assertEqual(
            removed.text,
            "A moderator removed your discussion post “Cheap internet here”. "
            "Reason: Spam or advertising.",
        )
        resolved = inbox(self.flagger).get()
        self.assertIn("the discussion post you flagged", resolved.text)
        self.client.force_login(self.flagger)
        self.assertRedirects(
            self.client.get(reverse("notifications:open", args=[resolved.pk])),
            reverse("forum:list"),
            fetch_redirect_response=False,
        )

    def test_removing_a_comment_keeps_the_post_and_opens_it(self):
        flag(FORUM_COMMENT, self.comment, self.flagger)
        self.client.post(
            reverse("moderation:remove", args=["comment", self.comment.pk]),
            {"reason": Reason.OFF_TOPIC},
        )
        self.assertTrue(ForumPost.objects.filter(pk=self.post.pk).exists())
        self.assertFalse(ForumComment.objects.exists())
        notice = inbox(self.replier).get()
        self.assertIn("comment on “Cheap internet here”", notice.text)
        self.client.force_login(self.replier)
        self.assertRedirects(
            self.client.get(reverse("notifications:open", args=[notice.pk])),
            self.post.get_absolute_url(),
            fetch_redirect_response=False,
        )

    def test_dismissing_comment_flags_tells_the_flagger_only(self):
        flag(FORUM_COMMENT, self.comment, self.flagger)
        self.client.post(
            reverse("moderation:dismiss", args=["comment", self.comment.pk])
        )
        self.assertTrue(ForumComment.objects.filter(pk=self.comment.pk).exists())
        self.assertFalse(inbox(self.replier).exists())
        notice = inbox(self.flagger).get()
        self.assertIn("decided to keep it", notice.text)
        self.assertIn("comment you flagged", notice.text)

    def test_bulk_removal_of_a_post_and_its_comment(self):
        ForumPost.objects.filter(pk=self.post.pk).update(is_held=True)
        ForumComment.objects.filter(pk=self.comment.pk).update(is_held=True)
        items = [
            f"post:{self.post.pk}|x",
            f"comment:{self.comment.pk}|x",
        ]
        self.client.post(
            reverse("moderation:bulk"),
            {
                "action": "remove",
                "tab": "held",
                "items": items,
                "confirm": "yes",
                "reason": Reason.SPAM,
            },
        )
        self.assertFalse(ForumPost.objects.exists())
        # The comment went with its post; only the post's removal is logged.
        self.assertEqual(ModerationRecord.objects.count(), 1)

    def test_recent_discussions_tab_lists_posts_and_comments(self):
        response = self.client.get(reverse("moderation:queue"), {"tab": "discussions"})
        self.assertContains(response, "Cheap internet here")
        self.assertContains(response, "Spammy reply")
        self.assertContains(
            response, reverse("moderation:remove", args=["comment", self.comment.pk])
        )

    def test_contributors_cannot_use_the_discussions_tab(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse("moderation:queue"), {"tab": "discussions"})
        self.assertEqual(response.status_code, 403)

    def test_stale_approval_of_an_edited_post_is_refused(self):
        ForumPost.objects.filter(pk=self.post.pk).update(is_held=True)
        self.post.refresh_from_db()
        version = FORUM_POST.describe(self.post)["version"]
        ForumPost.objects.filter(pk=self.post.pk).update(
            body="Changed", updated_at=timezone.now() + timedelta(seconds=5)
        )
        self.client.post(
            reverse("moderation:approve", args=["post", self.post.pk]),
            {"version": version},
        )
        self.post.refresh_from_db()
        self.assertTrue(self.post.is_held)
