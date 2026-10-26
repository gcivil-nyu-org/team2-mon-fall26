from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import contributor_required
from accounts.views import safe_next_url
from hotspots.models import Hotspot

from .forms import ReviewForm
from .models import Review, ReviewVote
from .services import visible_reviews


def _hotspot_url(hotspot):
    return f"{hotspot.get_absolute_url()}#reviews"


def _own_review_or_404(request, pk):
    # Other users' reviews return 404, so they cannot be edited or deleted by URL.
    return get_object_or_404(
        Review.objects.select_related("hotspot"),
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
        messages.info(request, "You already reviewed this hotspot. You can edit your review here.")
        return redirect("reviews:edit", pk=existing.pk)
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.hotspot = hotspot
        review.author = request.user
        try:
            with transaction.atomic():
                review.save()
        except IntegrityError:
            messages.info(request, "You already reviewed this hotspot.")
        else:
            messages.success(request, "Thanks. Your rating has been saved.")
        return redirect(_hotspot_url(hotspot))
    return render(request, "reviews/review_form.html", {"form": form, "hotspot": hotspot, "editing": False})


@contributor_required
def edit_review(request, pk):
    review = _own_review_or_404(request, pk)
    form = ReviewForm(request.POST or None, instance=review)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your changes have been saved.")
        return redirect(_hotspot_url(review.hotspot))
    return render(
        request,
        "reviews/review_form.html",
        {"form": form, "hotspot": review.hotspot, "review": review, "editing": True},
    )


@contributor_required
def delete_review(request, pk):
    review = _own_review_or_404(request, pk)
    if request.method == "POST":
        review.delete()
        messages.success(request, "Your rating and review have been deleted.")
        return redirect(_hotspot_url(review.hotspot))
    return render(request, "reviews/review_confirm_delete.html", {"review": review, "hotspot": review.hotspot})


@contributor_required
@require_POST
def toggle_vote(request, pk):
    review = get_object_or_404(
        visible_reviews().select_related("hotspot").exclude(body=""), pk=pk, hotspot__is_active=True
    )
    destination = safe_next_url(request) or _hotspot_url(review.hotspot)
    if review.author_id == request.user.pk:
        messages.info(request, "You can't upvote your own review.")
        return redirect(destination)
    vote = ReviewVote.objects.filter(review=review, user=request.user)
    if vote.exists():
        vote.delete()
    else:
        ReviewVote.objects.get_or_create(review=review, user=request.user)
    return redirect(destination)
