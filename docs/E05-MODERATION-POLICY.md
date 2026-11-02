# E05 moderation policy and extended acceptance criteria

Status: **proposed in PR #60, pending team agreement.** #30 leaves the exact moderation policy to the team, and the automated checks, community auto-hide and bulk actions go beyond the current US19–US21 descriptions. This page records the policy and the acceptance criteria the implementation and tests follow, so the team can agree on them, change the thresholds, or move them into a separate story.

Code: `moderation/automod.py` (rules), `moderation/services.py` (decisions), `moderation/views.py` (pages). Thresholds live in `config/settings.py`.

## Policy

### Reasons

The same reasons are used for user flags (US21) and administrator removals (US20): spam or advertising; harassment, hate or offensive language; false or misleading information; not about the hotspot or its Wi-Fi; shares someone's personal information; something else (details required).

### Automated checks on written reviews

The checks run on every new or edited written review, before any user flags. They are tiered so administrators only see the grey area.

| Tier | Triggers | Outcome |
| --- | --- | --- |
| Block | A link, except official domains such as `.gov`/`.edu`; an email address; a phone number; a term listed in `MODERATION_BLOCKED_TERMS` (empty by default; set as a comma-separated environment value) | The form shows an error and nothing is saved. |
| Hold | Promotional wording; profanity; text identical to another review; mostly capital letters; heavily repeated characters or words; more than `MODERATION_BURST_LIMIT` (3) earlier reviews within `MODERATION_BURST_MINUTES` (10) minutes; an author with `MODERATION_REPEAT_OFFENDER_REMOVALS` (2) or more removed reviews | Saved but hidden from the public, the map API and average ratings until an administrator approves or removes it. |
| Trust | `MODERATION_TRUSTED_MIN_REVIEWS` (3) published reviews at least `MODERATION_TRUSTED_MIN_AGE_HOURS` (24) hours old, with none ever removed | The capitals, repetition and posting-speed rules are skipped. Spam, profanity and duplicate rules still apply. |

Rating-only entries have no text. They are held only for repeat offenders.

### Community auto-hide

When `MODERATION_AUTO_HIDE_FLAGS` (3) different users have open flags on a public review, it is hidden in the same way as an automated hold.

### Decisions

- Only administrators approve, remove or dismiss.
- Removal deletes the item (as author deletion does). The moderation log keeps a copy of the text, the author, the reason, an optional note, the flag count and the administrator. Administrators never edit an author's words.
- Every approval, removal and dismissal is logged.
- Authors are not notified; a held author sees "Awaiting moderator approval" on their own review. Notifications are future work (E07 #37).

## Acceptance criteria for the extensions

**Automated checks**
- A review containing a link, email address, phone number or configured blocked term is rejected with an explanation and nothing is saved.
- A review matching a hold rule is saved, hidden from the public page, the map API and the average, and listed under **Held for review** with the rule that triggered it.
- The author sees their held review marked "Awaiting moderator approval"; other users and visitors do not see it, and it cannot be flagged or upvoted.
- An edit is re-checked. An edit never publishes a held review, and it never clears a hold or restores a removed review, even when the hold or removal happens while the author is editing.
- A trusted author is not held for capitals, repetition or posting speed.

**Community auto-hide**
- The third distinct user flag on a public review hides it until an administrator decides. Earlier flags leave it public.

**Administrator decisions**
- An administrator can approve a held item. Approval publishes exactly the text the administrator viewed; if the author edited it after the queue was opened, nothing is published and the administrator is told to check the new text.
- Bulk approval publishes only selected items that are still held and unchanged, and reports any it skipped.
- Bulk removal is two steps, consistent with US20's confirmation requirement. The first submission only shows a confirmation page with the count, each selected item and the consequences, and deletes nothing. Items are removed only after the confirmation is submitted with a reason. Cancel keeps every record.
- Removing an item that no longer exists changes nothing and logs nothing.
- Visitors are sent to log in and contributors get 403 for every administrator page and action.

Test coverage: `moderation/tests.py` (US19–US21), `moderation/test_automod.py` (rules, holds, auto-hide, bulk), `moderation/test_review_fixes.py` (concurrent edits, stale approvals, bulk confirmation).
