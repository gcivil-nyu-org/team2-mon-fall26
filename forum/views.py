from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import contributor_required
from moderation import automod
from moderation import services as moderation
from moderation.registry import FORUM_COMMENT, FORUM_POST
from notifications import services as notify

from .forms import ForumCommentForm, ForumPostForm
from .models import ForumComment, ForumVote
from .services import public_comments, public_posts, visible_posts

POST_HELD_MESSAGE = (
    "Thanks. Your discussion was saved and is waiting for a moderator before it "
    "appears publicly. Only you can see it until then."
)
COMMENT_HELD_MESSAGE = (
    "Thanks. Your reply was saved and is waiting for a moderator before it appears "
    "publicly. Only you can see it until then."
)


def _check_and_hold(flaggable, item):
    """E05 tier 2: hold suspicious text for an administrator. Returns True if held."""
    reasons = automod.forum_hold_reasons(item, is_new=True)
    if reasons:
        moderation.hold(flaggable, item, reasons)
    return item.is_held


def _vote_counts(queryset, user):
    user_id = user.pk
    return queryset.annotate(
        vote_count=Count("votes", distinct=True),
        user_vote_count=Count("votes", filter=Q(votes__user_id=user_id), distinct=True),
    )


def _comment_events(comments):
    """Render nested threads without recursive template calls."""
    pending = [("comment", comment) for comment in reversed(comments)]
    while pending:
        kind, comment = pending.pop()
        yield kind, comment
        if kind == "comment":
            pending.append(("close_comment", None))
            if comment.child_comments:
                pending.append(("close_children", None))
                pending.extend(
                    ("comment", child) for child in reversed(comment.child_comments)
                )
                pending.append(("open_children", None))


def _prune_hidden(comments):
    """Drop held comments the viewer may not see.

    A hidden comment that still has visible replies stays as a placeholder, so the
    replies keep their place in the thread.
    """
    kept = []
    for comment in comments:
        comment.child_comments = _prune_hidden(comment.child_comments)
        if not comment.hidden_for_viewer or comment.child_comments:
            kept.append(comment)
    return kept


def discussion_list(request):
    posts = _vote_counts(
        visible_posts(request.user)
        .select_related("author", "hotspot")
        .annotate(
            comment_count=Count(
                "comments", filter=Q(comments__is_held=False), distinct=True
            ),
        ),
        request.user,
    )
    return render(request, "forum/discussion_list.html", {"posts": posts})


def discussion_detail(request, pk, *, comment_form=None, reply_to_id=None):
    post = get_object_or_404(
        _vote_counts(
            visible_posts(request.user).select_related("author", "hotspot"),
            request.user,
        ),
        pk=pk,
    )
    comments = list(
        _vote_counts(
            ForumComment.objects.filter(post=post).select_related("author"),
            request.user,
        )
    )
    comment_by_id = {comment.pk: comment for comment in comments}
    top_level_comments = []
    for comment in comments:
        comment.child_comments = []
        # E05: held comments are visible only to their author.
        comment.hidden_for_viewer = (
            comment.is_held and comment.author_id != request.user.pk
        )
        if comment.parent_id in comment_by_id:
            comment_by_id[comment.parent_id].child_comments.append(comment)
        else:
            top_level_comments.append(comment)
    top_level_comments = _prune_hidden(top_level_comments)

    reply_to = None
    reply_to_id = reply_to_id or request.GET.get("reply_to")
    if reply_to_id:
        reply_to = next(
            (
                comment
                for comment in comments
                if str(comment.pk) == reply_to_id and not comment.is_held
            ),
            None,
        )
    return render(
        request,
        "forum/discussion_detail.html",
        {
            "post": post,
            "comments": top_level_comments,
            "comment_events": _comment_events(top_level_comments),
            "comment_count": sum(not comment.is_held for comment in comments),
            "comment_form": (
                comment_form if comment_form is not None else ForumCommentForm()
            ),
            "reply_to": reply_to,
            "flagged_post": post.pk in moderation.flagged_ids(request.user, FORUM_POST),
            "flagged_comment_ids": moderation.flagged_ids(request.user, FORUM_COMMENT),
        },
    )


@contributor_required
def create_post(request):
    submitted = request.method == "POST"
    searching = submitted and "hotspot_page" in request.POST
    form = ForumPostForm(
        data=request.POST if submitted and not searching else None,
        initial=request.POST.dict() if searching else None,
        hotspot_query=request.POST.get("hotspot_q", ""),
        page_number=request.POST.get("hotspot_page", 1),
    )
    if form.is_bound and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        if _check_and_hold(FORUM_POST, post):
            messages.info(request, POST_HELD_MESSAGE)
        else:
            notify.discussion_started(post)
            messages.success(request, "Your discussion has been posted.")
        return redirect("forum:detail", pk=post.pk)
    return render(request, "forum/post_form.html", {"form": form})


@contributor_required
def add_comment(request, post_pk):
    # Held discussions accept no comments until a moderator publishes them.
    post = get_object_or_404(public_posts(), pk=post_pk)
    if request.method != "POST":
        return redirect("forum:detail", pk=post.pk)

    form = ForumCommentForm(request.POST)
    parent = None
    parent_id = request.POST.get("parent_id", "").strip()
    if parent_id:
        try:
            parent_id = int(parent_id)
        except ValueError:
            raise Http404("Comment not found.") from None
        parent = get_object_or_404(public_comments(), pk=parent_id, post=post)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.parent = parent
        comment.save()
        if _check_and_hold(FORUM_COMMENT, comment):
            messages.info(request, COMMENT_HELD_MESSAGE)
        else:
            messages.success(request, "Your reply has been posted.")
        return redirect(f"{post.get_absolute_url()}#comment-{comment.pk}")
    return discussion_detail(
        request,
        post.pk,
        comment_form=form,
        reply_to_id=str(parent.pk) if parent else None,
    )


def _toggle_vote(request, post=None, comment=None):
    target = post or comment
    if request.method != "POST":
        return redirect("forum:detail", pk=post.pk if post else comment.post_id)
    if target.author_id == request.user.pk:
        messages.info(request, "You can't upvote your own forum content.")
        destination = (
            post.get_absolute_url() if post else comment.post.get_absolute_url()
        )
        fragment = "comments" if post else f"comment-{comment.pk}"
        return redirect(f"{destination}#{fragment}")

    filters = {"user": request.user}
    filters["post" if post else "comment"] = target
    vote = ForumVote.objects.filter(**filters)
    if vote.exists():
        vote.delete()
    else:
        ForumVote.objects.get_or_create(**filters)
    destination = post.get_absolute_url() if post else comment.post.get_absolute_url()
    return redirect(
        f"{destination}#comments" if post else f"{destination}#comment-{comment.pk}"
    )


@contributor_required
def toggle_post_vote(request, post_pk):
    post = get_object_or_404(public_posts(), pk=post_pk)
    return _toggle_vote(request, post=post)


@contributor_required
def toggle_comment_vote(request, comment_pk):
    comment = get_object_or_404(
        public_comments().select_related("post", "author"),
        pk=comment_pk,
    )
    return _toggle_vote(request, comment=comment)
