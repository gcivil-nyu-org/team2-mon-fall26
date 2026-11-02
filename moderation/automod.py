"""E05 automated moderation: rule-based checks that run before any user flags.

Built-in rules only (no external service or API key). Work is tiered so that
administrators only see the grey area, as on most review sites:

1. Block (``blocking_problems``): clear-cut cases are rejected by the review
   form with an explanation. Nothing is saved, and no administrator time is
   spent. The author can fix the text and resubmit.
2. Hold (``hold_reasons``): suspicious but possibly legitimate text is saved but
   hidden from the public and from the average until an administrator approves
   or removes it.
3. Trust: authors with a good track record skip the soft rules.

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


def blocking_problems(text):
    """Tier 1: messages explaining why this text can't be posted ([] when acceptable)."""
    if not text:
        return []
    problems = []
    if _LINK.search(text) or _EMAIL.search(text) or _PHONE.search(text):
        problems.append(
            "Reviews can't include links, email addresses or phone numbers. "
            "Please describe your experience in your own words."
        )
    words = set(_normalize(text.translate(_LEET)).split())
    plain = _normalize(text.translate(_LEET))
    for term in _blocked_terms():
        if (" " in term and term in plain) or term in words:
            problems.append(
                "This review contains language that isn't allowed on Connect NYC."
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


def is_trusted(user, exclude_pk=None):
    """Established authors: enough published reviews that have stood for a while, none removed.

    Requiring older reviews stops a new account from posting a few clean reviews in
    a row and immediately skipping the soft rules.
    """
    from reviews.models import Review

    settled_before = timezone.now() - timedelta(
        hours=_setting("MODERATION_TRUSTED_MIN_AGE_HOURS", 24)
    )
    published = Review.objects.filter(
        author=user, is_held=False, is_demo=False, created_at__lte=settled_before
    ).exclude(pk=exclude_pk)
    return (
        published.count() >= _setting("MODERATION_TRUSTED_MIN_REVIEWS", 3)
        and _removed_count(user) == 0
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
    if not text:
        return reasons  # A rating with no text has nothing else to check.

    lowered = text.lower()
    promo = [phrase for phrase in _PROMO_PHRASES if phrase in lowered]
    if promo:
        reasons.append((Reason.SPAM, f"Promotional wording: {', '.join(promo[:3])}"))
    profanity = _PROFANITY.search(text) or _PROFANITY.search(text.translate(_LEET))
    if profanity:
        reasons.append((Reason.OFFENSIVE, "Contains profanity"))

    normalized = _normalize(text)
    if len(normalized) >= 20:
        others = Review.objects.exclude(pk=review.pk).exclude(body="")
        if others.filter(author=author, body__iexact=text.strip()).exists() or any(
            _normalize(body) == normalized
            for body in others.filter(author=author).values_list("body", flat=True)
        ):
            reasons.append(
                (Reason.SPAM, "Same text as another of this author's reviews")
            )
        elif others.exclude(author=author).filter(body__iexact=text.strip()).exists():
            reasons.append((Reason.SPAM, "Same text as a review by another account"))

    if not is_trusted(author, exclude_pk=review.pk):
        if _is_shouting(text):
            reasons.append((Reason.OTHER, "Mostly written in capital letters"))
        if _REPEATED_CHAR.search(text) or _REPEATED_WORD.search(text):
            reasons.append((Reason.SPAM, "Heavily repeated characters or words"))
        if is_new:
            window = timezone.now() - timedelta(
                minutes=_setting("MODERATION_BURST_MINUTES", 10)
            )
            recent = Review.objects.filter(
                author=author, created_at__gte=window
            ).exclude(pk=review.pk)
            if recent.count() >= _setting("MODERATION_BURST_LIMIT", 3):
                reasons.append((Reason.SPAM, "Posting many reviews in a short time"))
    return reasons
