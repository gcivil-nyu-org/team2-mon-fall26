from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.permissions import administrator_required, contributor_required
from forum.models import ForumComment, ForumPost
from reviews.models import Review

from . import services
from .forms import FlagForm, RemovalForm
from .models import ContentFlag, ModerationRecord, Reason
from .registry import FORUM_COMMENT, FORUM_POST, REVIEW, get_type

TABS = {
    "held": "Held for review",
    "flagged": "Flagged content",
    "recent": "Recent ratings and reviews",
    "discussions": "Recent discussions",
    "log": "Moderation log",
}


def _back_to(info):
    return info["url"] or "/"


def _removal_effect(flaggable, obj):
    return flaggable.removal_effect(obj) if flaggable.removal_effect else ""


@contributor_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def flag_content(request, kind, pk):
    """US21: a signed-in contributor flags someone else's content, once."""
    flaggable = get_type(kind)
    items = flaggable.public_queryset()
    if request.method == "POST":
        items = items.select_for_update(of=("self",))
    obj = get_object_or_404(items, pk=pk)
    info = flaggable.describe(obj)
    if info["author_id"] == request.user.pk:
        messages.info(request, "You can't flag your own content.")
        return redirect(_back_to(info))
    if services.flags_for(flaggable, obj.pk).filter(flagged_by=request.user).exists():
        messages.info(
            request, "You already flagged this. An administrator will review it."
        )
        return redirect(_back_to(info))
    form = FlagForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Serialize the visibility check and decision with other flags and moderation.
            obj = get_object_or_404(
                flaggable.public_queryset().select_for_update(), pk=pk
            )
            _, created = ContentFlag.objects.get_or_create(
                content_type=services.content_type_for(flaggable),
                object_id=obj.pk,
                flagged_by=request.user,
                defaults={
                    "reason": form.cleaned_data["reason"],
                    "note": form.cleaned_data["note"],
                },
            )
            if created:
                services.auto_hide_if_widely_flagged(flaggable, obj)
        if created:
            messages.success(
                request, "Thanks for flagging this. An administrator will review it."
            )
        else:
            messages.info(
                request, "You already flagged this. An administrator will review it."
            )
        return redirect(_back_to(info))
    return render(
        request,
        "moderation/flag_form.html",
        {
            "form": form,
            "flaggable": flaggable,
            "info": info,
        },
    )


@administrator_required
@require_GET
def moderation_queue(request):
    """US19: administrators inspect held and flagged content, recent contributions and past decisions."""
    tab = request.GET.get("tab", "held")
    if tab not in TABS:
        tab = "held"
    context = {
        "tab": tab,
        "tabs": TABS,
        "tab_label": TABS[tab],
        "held_count": services.held_count(),
        "open_item_count": services.open_item_count(),
        "removed_count": ModerationRecord.objects.filter(
            action=ModerationRecord.Action.REMOVED
        ).count(),
        "removal_form": RemovalForm(initial={"reason": Reason.SPAM}),
    }
    if tab == "held":
        context["items"] = services.held_items()
    elif tab == "flagged":
        context["items"] = services.flagged_items()
    elif tab == "recent":
        page = Paginator(
            Review.objects.select_related("hotspot", "author").order_by(
                "-created_at", "-pk"
            ),
            50,
        ).get_page(request.GET.get("page"))
        counts = services.open_flag_counts(REVIEW, [review.pk for review in page])
        context["page_obj"] = page
        context["reviews"] = [
            {"review": review, "open_flags": counts.get(review.pk, 0)}
            for review in page
        ]
    elif tab == "discussions":
        context.update(_recent_discussions(request.GET.get("page")))
    else:
        context["page_obj"] = Paginator(
            ModerationRecord.objects.select_related("moderator"), 50
        ).get_page(request.GET.get("page"))
    return render(request, "moderation/queue.html", context)


def _recent_discussions(page_number):
    """Newest discussion posts and comments together, 50 per page, with open-flag counts.

    Covers the newest 500 posts and 500 comments; older items are still reachable
    from their discussion pages and the Django admin.
    """
    posts = list(
        ForumPost.objects.select_related("author").order_by("-created_at", "-pk")[:500]
    )
    comments = list(
        ForumComment.objects.select_related("author", "post").order_by(
            "-created_at", "-pk"
        )[:500]
    )
    rows = [{"type": FORUM_POST, "item": post} for post in posts] + [
        {"type": FORUM_COMMENT, "item": comment} for comment in comments
    ]
    rows.sort(key=lambda row: (row["item"].created_at, row["item"].pk), reverse=True)
    page = Paginator(rows, 50).get_page(page_number)
    post_flags = services.open_flag_counts(
        FORUM_POST, [row["item"].pk for row in page if row["type"] is FORUM_POST]
    )
    comment_flags = services.open_flag_counts(
        FORUM_COMMENT,
        [row["item"].pk for row in page if row["type"] is FORUM_COMMENT],
    )
    for row in page:
        counts = post_flags if row["type"] is FORUM_POST else comment_flags
        row["open_flags"] = counts.get(row["item"].pk, 0)
        row["info"] = row["type"].describe(row["item"])
    return {"page_obj": page, "discussion_rows": page}


@administrator_required
@require_http_methods(["GET", "POST"])
def remove_content(request, kind, pk):
    """US20: remove a guideline violation after confirming and recording a reason."""
    flaggable = get_type(kind)
    obj = get_object_or_404(flaggable.admin_queryset(), pk=pk)
    info = flaggable.describe(obj)
    form = RemovalForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        destination = f"{reverse('moderation:queue')}?tab={'held' if info['is_held'] else 'flagged'}"
        record = services.remove_content(
            flaggable,
            obj,
            request.user,
            form.cleaned_data["reason"],
            form.cleaned_data["note"],
        )
        if record is None:
            messages.info(
                request, "This item no longer exists; its author may have deleted it."
            )
        else:
            messages.success(
                request,
                f"Removed the {flaggable.label.lower()} by {info['author']}. The decision was logged.",
            )
        return redirect(destination)
    open_flags = services.open_flags_for(flaggable, obj.pk).select_related("flagged_by")
    return render(
        request,
        "moderation/confirm_remove.html",
        {
            "form": form,
            "flaggable": flaggable,
            "info": info,
            "pk": obj.pk,
            "open_flags": open_flags,
            "removal_effect": _removal_effect(flaggable, obj),
        },
    )


@administrator_required
@require_POST
def dismiss_flags(request, kind, pk):
    """Close the open flags on an item an administrator judged acceptable."""
    flaggable = get_type(kind)
    obj = get_object_or_404(flaggable.admin_queryset(), pk=pk)
    if not services.open_flags_for(flaggable, obj.pk).exists():
        messages.info(request, "There are no open flags on this item.")
    elif services.dismiss_flags(flaggable, obj, request.user) is None:
        messages.info(
            request, "This item no longer exists; its author may have deleted it."
        )
    else:
        messages.success(request, "Flags dismissed. The content was left unchanged.")
    return redirect(f"{reverse('moderation:queue')}?tab=flagged")


STALE_APPROVAL = (
    "Not published: the author edited this item after you opened the queue, or it was "
    "already handled. Check the current text before approving."
)


@administrator_required
@require_POST
def approve_content(request, kind, pk):
    """Publish an item that was held for review, exactly as the administrator saw it."""
    flaggable = get_type(kind)
    obj = get_object_or_404(flaggable.held_queryset(), pk=pk)
    if (
        services.approve(
            flaggable, obj, request.user, version=request.POST.get("version", "")
        )
        is None
    ):
        messages.error(request, STALE_APPROVAL)
    else:
        messages.success(
            request, f"Approved and published the {flaggable.label.lower()}."
        )
    return redirect(f"{reverse('moderation:queue')}?tab=held")


def _selected(values):
    """Parse ``kind:pk|version`` checkbox values into ``(type, object, version)``.

    Items that no longer exist are skipped.
    """
    selected = []
    for value in values:
        key, _, version = value.partition("|")
        kind, _, raw_pk = key.partition(":")
        if not raw_pk.isdigit():
            continue
        flaggable = get_type(kind)
        obj = flaggable.admin_queryset().filter(pk=int(raw_pk)).first()
        if obj is not None:
            selected.append((flaggable, obj, version))
    return selected


def _plural(count, word="item"):
    return f"{count} {word}{'' if count == 1 else 's'}"


@administrator_required
@require_POST
def bulk_action(request):
    """Approve or remove several items at once, so spam waves don't need one click each.

    Removal is two steps (US20 requires confirmation): the queue's button opens a
    confirmation page listing the selected items, and only its confirmed
    submission deletes anything.
    """
    tab = request.POST.get("tab") if request.POST.get("tab") in TABS else "held"
    destination = f"{reverse('moderation:queue')}?tab={tab}"
    action = request.POST.get("action")
    selected = _selected(request.POST.getlist("items"))
    if not selected:
        messages.info(request, "Select at least one item first.")
        return redirect(destination)

    if action == "approve":
        approved = sum(
            services.approve(flaggable, obj, request.user, version=version) is not None
            for flaggable, obj, version in selected
        )
        skipped = len(selected) - approved
        messages.success(request, f"Approved and published {_plural(approved)}.")
        if skipped:
            messages.info(
                request,
                f"{_plural(skipped)} not published: edited since you opened the queue, not held, or already handled.",
            )
        return redirect(destination)

    if action != "remove":
        messages.error(request, "Choose an action.")
        return redirect(destination)

    form = RemovalForm(
        request.POST if request.POST.get("confirm") == "yes" else None,
        initial={"reason": request.POST.get("reason") or Reason.SPAM},
    )
    if request.POST.get("confirm") == "yes" and form.is_valid():
        removed = sum(
            services.remove_content(
                flaggable,
                obj,
                request.user,
                form.cleaned_data["reason"],
                form.cleaned_data["note"],
            )
            is not None
            for flaggable, obj, _ in selected
        )
        messages.success(
            request, f"Removed {_plural(removed)}. Each removal was logged."
        )
        return redirect(destination)
    # First step, or a confirmation with errors: show what will be removed. Nothing is deleted.
    items = [
        {
            "type": flaggable,
            "pk": obj.pk,
            "info": flaggable.describe(obj),
            "value": f"{flaggable.key}:{obj.pk}|{version}",
            "effect": _removal_effect(flaggable, obj),
        }
        for flaggable, obj, version in selected
    ]
    return render(
        request,
        "moderation/confirm_bulk_remove.html",
        {
            "form": form,
            "items": items,
            "tab": tab,
            "destination": destination,
            "affects_rating": any(item["type"].affects_rating for item in items),
        },
    )
