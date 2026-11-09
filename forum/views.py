from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import contributor_required
from notifications import services as notify

from .forms import ForumCommentForm, ForumPostForm
from .models import ForumComment, ForumPost, ForumVote


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


def discussion_list(request):
    posts = _vote_counts(
        ForumPost.objects.select_related("author", "hotspot").annotate(
            comment_count=Count("comments", distinct=True),
        ),
        request.user,
    )
    return render(request, "forum/discussion_list.html", {"posts": posts})


def discussion_detail(request, pk):
    post = get_object_or_404(
        _vote_counts(
            ForumPost.objects.select_related("author", "hotspot"), request.user
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
        if comment.parent_id in comment_by_id:
            comment_by_id[comment.parent_id].child_comments.append(comment)
        else:
            top_level_comments.append(comment)

    reply_to = None
    reply_to_id = request.GET.get("reply_to")
    if reply_to_id:
        reply_to = next(
            (comment for comment in comments if str(comment.pk) == reply_to_id),
            None,
        )
    return render(
        request,
        "forum/discussion_detail.html",
        {
            "post": post,
            "comments": top_level_comments,
            "comment_events": _comment_events(top_level_comments),
            "comment_count": len(comments),
            "comment_form": ForumCommentForm(),
            "reply_to": reply_to,
        },
    )


@contributor_required
def create_post(request):
    form = ForumPostForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        notify.discussion_started(post)
        messages.success(request, "Your discussion has been posted.")
        return redirect("forum:detail", pk=post.pk)
    return render(request, "forum/post_form.html", {"form": form})


@contributor_required
def add_comment(request, post_pk):
    post = get_object_or_404(ForumPost, pk=post_pk)
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
        parent = get_object_or_404(ForumComment, pk=parent_id, post=post)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.parent = parent
        comment.save()
        messages.success(request, "Your reply has been posted.")
        return redirect(f"{post.get_absolute_url()}#comment-{comment.pk}")
    messages.error(request, "Please enter a comment before posting.")
    return redirect(f"{post.get_absolute_url()}#comments")


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
    post = get_object_or_404(ForumPost, pk=post_pk)
    return _toggle_vote(request, post=post)


@contributor_required
def toggle_comment_vote(request, comment_pk):
    comment = get_object_or_404(
        ForumComment.objects.select_related("post", "author"),
        pk=comment_pk,
    )
    return _toggle_vote(request, comment=comment)
