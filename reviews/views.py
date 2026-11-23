from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import redirect_to_login
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import contributor_required
from accounts.roles import is_contributor
from accounts.views import safe_next_url
from hotspots.models import Hotspot
from moderation import automod
from moderation import services as moderation
from moderation.registry import REVIEW, REVIEW_REPLY
from notifications import services as notify

from .forms import ReviewForm, ReviewReplyForm
from .models import Review, ReviewReply, ReviewVote
from .services import visible_reviews


def _hotspot_url(hotspot):
    return f"{hotspot.get_absolute_url()}#reviews"


REPLY_HELD_MESSAGE = (
    "Thanks. Your reply was saved and is waiting for a moderator before it appears "
    "publicly. Only you can see it until then."
)

HELD_MESSAGE = (
    "Thanks. Your review was saved and is waiting for a moderator before it appears "
    "publicly. Only you can see it until then."
)


def _check_and_hold(review, is_new):
    """E05 tier 2: hold suspicious text for an administrator. Returns True if held."""
    reasons = automod.hold_reasons(review, is_new)
    if reasons:
        moderation.hold(REVIEW, review, reasons)
    return review.is_held


def _own_review_or_404(request, pk, *, lock=False):
    # Other users' reviews return 404, so they cannot be edited or deleted by URL.
    reviews = Review.objects.select_related("hotspot")
    if lock:
        reviews = reviews.select_for_update(of=("self",))
    return get_object_or_404(
        reviews,
        pk=pk,
        author=request.user,
        is_demo=False,
        hotspot__is_active=True,
    )


@contributor_required
def create_review(request, hotspot_pk):
    hotspot = get_object_or_404(Hotspot, pk=hotspot_pk, is_active=True)
    existing = Review.objects.filter(hotspot=hotspot, author=request.user).first()
    if existing:
        messages.info(
            request, "You already reviewed this hotspot. You can edit your review here."
        )
        return redirect("reviews:edit", pk=existing.pk)
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.hotspot = hotspot
        review.author = request.user
        try:
            with transaction.atomic():
                # Count this author's submissions in order, even across different hotspots.
                get_user_model().objects.select_for_update().only("pk").get(
                    pk=request.user.pk
                )
                review.save()
                held = _check_and_hold(review, is_new=True)
        except IntegrityError:
            if not Review.objects.filter(hotspot=hotspot, author=request.user).exists():
                raise
            messages.info(request, "You already reviewed this hotspot.")
        else:
            if held:
                messages.info(request, HELD_MESSAGE)
            else:
                notify.review_published(review)
                messages.success(request, "Thanks. Your rating has been saved.")
        return redirect(_hotspot_url(hotspot))
    return render(
        request,
        "reviews/review_form.html",
        {"form": form, "hotspot": hotspot, "editing": False},
    )


@contributor_required
def edit_review(request, pk):
    review = _own_review_or_404(request, pk)
    form = ReviewForm(request.POST or None, instance=review)
    if request.method == "POST" and form.is_valid():
        # E05: a moderator or community flags may act between the lookup above and
        # this save. Lock the current row and write only the author's fields, so a
        # concurrent hold is never cleared and a removed review is never recreated.
        with transaction.atomic():
            current = (
                Review.objects.select_for_update()
                .filter(
                    pk=review.pk,
                    author=request.user,
                    is_demo=False,
                    hotspot__is_active=True,
                )
                .first()
            )
            if current is None:
                messages.info(
                    request,
                    "This review is no longer available. It may have been removed by a moderator.",
                )
                return redirect(_hotspot_url(review.hotspot))
            current.rating = form.cleaned_data["rating"]
            current.body = form.cleaned_data["body"]
            current.save(update_fields=["rating", "body", "updated_at"])
            # A held review stays held after an edit; an admin decides.
            held = _check_and_hold(current, is_new=False)
        if held:
            messages.info(request, HELD_MESSAGE)
        else:
            messages.success(request, "Your changes have been saved.")
        return redirect(_hotspot_url(current.hotspot))
    return render(
        request,
        "reviews/review_form.html",
        {"form": form, "hotspot": review.hotspot, "review": review, "editing": True},
    )


@contributor_required
@transaction.atomic
def delete_review(request, pk):
    review = _own_review_or_404(request, pk, lock=request.method == "POST")
    if request.method == "POST":
        review.delete()
        messages.success(request, "Your rating and review have been deleted.")
        return redirect(_hotspot_url(review.hotspot))
    return render(
        request,
        "reviews/review_confirm_delete.html",
        {
            "review": review,
            "hotspot": review.hotspot,
            "visible_reply_count": (
                review.replies.filter(Q(is_held=False) | Q(author=request.user)).count()
                if review.body
                else 0
            ),
        },
    )


def _votable_reviews():
    """Public written reviews of active hotspots: the ones that take votes and replies."""
    return (
        visible_reviews()
        .select_related("hotspot")
        .exclude(body="")
        .filter(hotspot__is_active=True)
    )


@require_POST
@transaction.atomic
def toggle_vote(request, pk):
    """Vote a written review up (helpful) or down (not helpful).

    Voting the same way again removes the vote; voting the other way switches it.
    Votes never change star averages.
    """
    review = get_object_or_404(
        _votable_reviews().select_for_update(of=("self",)), pk=pk
    )
    if not is_contributor(request.user):
        return redirect_to_login(_hotspot_url(review.hotspot))
    destination = safe_next_url(request) or _hotspot_url(review.hotspot)
    if review.author_id == request.user.pk:
        messages.info(request, "You can't vote on your own review.")
        return redirect(destination)
    value = (
        ReviewVote.DOWN if request.POST.get("direction") == "down" else ReviewVote.UP
    )
    vote, created = ReviewVote.objects.get_or_create(
        review=review, user=request.user, defaults={"value": value}
    )
    if not created:
        if vote.value == value:
            vote.delete()
        else:
            vote.value = value
            vote.save(update_fields=["value"])
    return redirect(destination)


@require_POST
@transaction.atomic
def add_reply(request, pk):
    """Reply to a public written review. Replies get the same E05 checks as comments."""
    # Demo reviews are sample content, so they take no replies.
    review = get_object_or_404(
        _votable_reviews().select_for_update(of=("self",)), pk=pk, is_demo=False
    )
    if not is_contributor(request.user):
        return redirect_to_login(
            f"{review.hotspot.get_absolute_url()}#review-{review.pk}"
        )
    form = ReviewReplyForm(request.POST)
    if not form.is_valid():
        for error in form.errors.get("body", []):
            messages.error(request, error)
        return redirect(f"{review.hotspot.get_absolute_url()}#review-{review.pk}")
    reply = form.save(commit=False)
    reply.review = review
    reply.author = request.user
    # Count this author's replies in order, so the posting-speed rule holds.
    get_user_model().objects.select_for_update().only("pk").get(pk=request.user.pk)
    reply.save()
    reasons = automod.reply_hold_reasons(reply, is_new=True)
    if reasons:
        moderation.hold(REVIEW_REPLY, reply, reasons)
    if reply.is_held:
        messages.info(request, REPLY_HELD_MESSAGE)
    else:
        notify.review_replied(reply)
        messages.success(request, "Your reply has been posted.")
    return redirect(f"{review.hotspot.get_absolute_url()}#reply-{reply.pk}")


@contributor_required
def delete_reply(request, pk):
    reply = get_object_or_404(
        ReviewReply.objects.select_related("review__hotspot"),
        pk=pk,
        author=request.user,
        review__hotspot__is_active=True,
    )
    hotspot = reply.review.hotspot
    if request.method == "POST":
        reply.delete()
        messages.success(request, "Your reply has been deleted.")
        return redirect(f"{hotspot.get_absolute_url()}#review-{reply.review_id}")
    return render(
        request,
        "reviews/reply_confirm_delete.html",
        {"reply": reply, "hotspot": hotspot},
    )
