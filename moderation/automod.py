"""E05 automated moderation: rule-based checks that run before any user flags.

Built-in rules only (no external service or API key). Work is tiered so that
administrators only see the grey area, as on most review sites:

1. Block (``blocking_problems``): clear-cut cases are rejected by the review,
   discussion post or comment form with an explanation. Nothing is saved, and no administrator time is
   spent. The author can fix the text and resubmit.
2. Hold (``hold_reasons``): suspicious but possibly legitimate text is saved but
   hidden from the public and from the average until an administrator approves
   or removes it.
3. Trust: authors with a good track record skip the soft rules.

Reviews use ``hold_reasons``; discussion posts and comments use
``forum_hold_reasons``, which applies the same rules to forum text; replies to
reviews use ``reply_hold_reasons`` (the forum comment rules).

Thresholds and word lists can be tuned in settings (see ``config/settings.py``).
"""

import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Reason

# --- Tier 1: blocked outright -------------------------------------------------

# Official and educational domains stay allowed so people can cite city sources.
# Bare domains are matched in lower case only, so a missing space after a full
# stop ("Great signal.Me too") is not mistaken for a link.
_LINK = re.compile(
    r"(?i:(https?://|www\.)\S+)"
    r"|\b[a-z0-9-]+(\.[a-z0-9-]+)*\.(com|net|org|io|co|biz|info|xyz|ru|cn|top|shop|store|"
    r"site|online|click|link|app|me|ly|gg|tk|live|club|vip|win|bet|us)\b(/\S*)?"
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_PHONE = re.compile(
    r"(?<![\d.])(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?![\d.])"
)

# --- Tier 2: held for an administrator ----------------------------------------

_PROMO_PHRASES = [
    "promo code",
    "coupon",
    "discount code",
    "% off",
    "percent off",
    "buy now",
    "order now",
    "limited offer",
    "limited time offer",
    "click here",
    "dm me",
    "message me on",
    "text me",
    "whatsapp",
    "telegram",
    "crypto",
    "bitcoin",
    "forex",
    "make money",
    "earn money",
    "work from home",
    "casino",
    "betting",
    "follow me on",
    "subscribe to my",
    "check out my",
    "visit my",
    "best price",
    "cheap price",
]
# Common profanity is held rather than blocked: context matters, a person decides.
_PROFANITY = re.compile(
    r"\b(f+u+c+k+\w*|f\*+c?k\w*|sh[i1!*]+t+\w*|b[i1!*]+tch\w*|a+ss+h[o0]+le\w*|bastard\w*|"
    r"motherf\w*|bullsh\w*|cunt\w*|wh[o0]re\w*|dumbass\w*)\b",
    re.IGNORECASE,
)
_REPEATED_CHAR = re.compile(r"(\S)\1{5,}")
_REPEATED_WORD = re.compile(r"\b(\w+)(?:\W+\1\b){3,}", re.IGNORECASE)
_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)


def _setting(name, default):
    return getattr(settings, name, default)


def _normalize(text):
    return re.sub(r"\s+", " ", re.sub(r"[^\w%$ ]", " ", text.lower())).strip()


def _blocked_terms():
    return [
        term.strip().lower()
        for term in _setting("MODERATION_BLOCKED_TERMS", [])
        if term.strip()
    ]


_NOUNS = {
    "review": "Reviews",
    "post": "Discussion posts",
    "comment": "Comments",
    "reply": "Replies",
}


def _plural(noun):
    return "replies" if noun == "reply" else f"{noun}s"


def blocking_problems(text, content="review"):
    """Tier 1: messages explaining why this text can't be posted ([] when acceptable).

    ``content`` is ``review``, ``post``, ``comment`` or ``reply`` and only changes
    the wording.
    """
    if not text:
        return []
    problems = []
    if _LINK.search(text) or _EMAIL.search(text) or _PHONE.search(text):
        problems.append(
            f"{_NOUNS[content]} can't include links, email addresses or phone numbers. "
            + (
                "Please describe your experience in your own words."
                if content == "review"
                else "Please write your message in your own words."
            )
        )
    words = set(_normalize(text.translate(_LEET)).split())
    plain = _normalize(text.translate(_LEET))
    for term in _blocked_terms():
        if (" " in term and term in plain) or term in words:
            problems.append(
                f"This {content} contains language that isn't allowed on Connect NYC."
            )
            break
    return problems


def _is_shouting(text):
    letters = [char for char in text if char.isalpha()]
    return (
        len(letters) >= 20
        and sum(char.isupper() for char in letters) / len(letters) >= 0.7
    )


def _removed_count(user):
    from .models import ModerationRecord

    return ModerationRecord.objects.filter(
        author=user, action=ModerationRecord.Action.REMOVED
    ).count()


def is_trusted(user, exclude_pk=None, *, reviews=None):
    """Established authors: enough published reviews that have stood for a while, none removed.

    Requiring older reviews stops a new account from posting a few clean reviews in
    a row and immediately skipping the soft rules.
    """
    from reviews.models import Review

    settled_before = timezone.now() - timedelta(
        hours=_setting("MODERATION_TRUSTED_MIN_AGE_HOURS", 24)
    )
    if reviews is None:
        reviews = Review.objects.all()
    published = reviews.filter(
        author=user, is_held=False, is_demo=False, created_at__lte=settled_before
    ).exclude(pk=exclude_pk)
    return (
        published.count() >= _setting("MODERATION_TRUSTED_MIN_REVIEWS", 3)
        and _removed_count(user) == 0
    )


def _wording_reasons(text):
    """Promotional wording and profanity: checked for every author, trusted or not."""
    reasons = []
    lowered = text.lower()
    promo = [phrase for phrase in _PROMO_PHRASES if phrase in lowered]
    if promo:
        reasons.append((Reason.SPAM, f"Promotional wording: {', '.join(promo[:3])}"))
    profanity = _PROFANITY.search(text) or _PROFANITY.search(text.translate(_LEET))
    if profanity:
        reasons.append((Reason.OFFENSIVE, "Contains profanity"))
    return reasons


def _style_reasons(text):
    """Capitals and repetition: skipped for trusted authors."""
    reasons = []
    if _is_shouting(text):
        reasons.append((Reason.OTHER, "Mostly written in capital letters"))
    if _REPEATED_CHAR.search(text) or _REPEATED_WORD.search(text):
        reasons.append((Reason.SPAM, "Heavily repeated characters or words"))
    return reasons


def _duplicate_reason(text, author, others, noun):
    """Same text as another item of this kind (``others`` excludes the item itself)."""
    normalized = _normalize(text)
    if len(normalized) < 20:
        return None
    if others.filter(author=author, body__iexact=text.strip()).exists() or any(
        _normalize(body) == normalized
        for body in others.filter(author=author).values_list("body", flat=True)
    ):
        return (Reason.SPAM, f"Same text as another of this author's {_plural(noun)}")
    if others.exclude(author=author).filter(body__iexact=text.strip()).exists():
        return (Reason.SPAM, f"Same text as a {noun} by another account")
    return None


def _is_burst(queryset, limit_setting, default_limit):
    window = timezone.now() - timedelta(
        minutes=_setting("MODERATION_BURST_MINUTES", 10)
    )
    return queryset.filter(created_at__gte=window).count() >= _setting(
        limit_setting, default_limit
    )


def hold_reasons(review, is_new):
    """Tier 2: ``[(Reason, detail), ...]`` explaining why a saved review should be held."""
    from reviews.models import Review

    reasons = []
    author = review.author
    if _removed_count(author) >= _setting("MODERATION_REPEAT_OFFENDER_REMOVALS", 2):
        reasons.append(
            (Reason.SPAM, "Author has had several reviews removed by moderators")
        )
    text = review.body
    if text:
        reasons.extend(_wording_reasons(text))
        duplicate = _duplicate_reason(
            text,
            author,
            Review.objects.exclude(pk=review.pk).exclude(body=""),
            "review",
        )
        if duplicate:
            reasons.append(duplicate)

    if not is_trusted(author, exclude_pk=review.pk):
        reasons.extend(_style_reasons(text))
        if is_new and _is_burst(
            Review.objects.filter(author=author).exclude(pk=review.pk),
            "MODERATION_BURST_LIMIT",
            3,
        ):
            reasons.append((Reason.SPAM, "Posting many reviews in a short time"))
    return reasons


# --- Discussion forum (E08 content, same tiers) --------------------------------


def is_trusted_in_forum(user):
    """Trusted reviewers, or authors with enough settled public forum contributions.

    The same thresholds apply as for reviews: count and age from settings, and no
    removed content of any kind.
    """
    from forum.models import ForumComment, ForumPost

    if is_trusted(user):
        return True
    settled_before = timezone.now() - timedelta(
        hours=_setting("MODERATION_TRUSTED_MIN_AGE_HOURS", 24)
    )
    published = (
        ForumPost.objects.filter(
            author=user, is_held=False, created_at__lte=settled_before
        ).count()
        + ForumComment.objects.filter(
            author=user, is_held=False, created_at__lte=settled_before
        ).count()
    )
    return (
        published >= _setting("MODERATION_TRUSTED_MIN_REVIEWS", 3)
        and _removed_count(user) == 0
    )


def forum_hold_reasons(item, is_new=True, noun=None):
    """Tier 2 for a saved ``ForumPost`` or ``ForumComment`` (title and body are checked).

    Also used for replies to reviews (``ReviewReply``, ``noun="reply"``), which
    follow the comment rules.
    """
    from forum.models import ForumPost

    is_post = isinstance(item, ForumPost)
    noun = noun or ("post" if is_post else "comment")
    model = type(item)
    author = item.author
    reasons = []
    if _removed_count(author) >= _setting("MODERATION_REPEAT_OFFENDER_REMOVALS", 2):
        reasons.append(
            (Reason.SPAM, "Author has had several contributions removed by moderators")
        )
    text = f"{item.title}\n{item.body}" if is_post else item.body
    reasons.extend(_wording_reasons(text))
    duplicate = _duplicate_reason(
        item.body, author, model.objects.exclude(pk=item.pk), noun
    )
    if duplicate:
        reasons.append(duplicate)

    if not is_trusted_in_forum(author):
        reasons.extend(_style_reasons(text))
        if is_new and _is_burst(
            model.objects.filter(author=author).exclude(pk=item.pk),
            ("MODERATION_BURST_LIMIT" if is_post else "MODERATION_COMMENT_BURST_LIMIT"),
            3 if is_post else 10,
        ):
            reasons.append(
                (Reason.SPAM, f"Posting many {_plural(noun)} in a short time")
            )
    return reasons


def reply_hold_reasons(reply, is_new=True):
    """Tier 2 for a saved reply to a review: the same rules as discussion comments."""
    return forum_hold_reasons(reply, is_new=is_new, noun="reply")
