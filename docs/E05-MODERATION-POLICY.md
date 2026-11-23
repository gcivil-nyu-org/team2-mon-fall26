# E05 moderation policy and extended acceptance criteria

Status: **proposed in PR #60, pending team agreement.** #30 leaves the exact moderation policy to the team, and the automated checks, community auto-hide and bulk actions go beyond the current US19–US21 descriptions. This page records the policy and the acceptance criteria the implementation and tests follow, so the team can agree on them, change the thresholds, or move them into a separate story.

Code: `moderation/automod.py` (rules), `moderation/services.py` (decisions), `moderation/views.py` (pages). Thresholds live in `config/settings.py`.

## Policy

### Reasons

The same reasons are used for user flags (US21) and administrator removals (US20): spam or advertising; harassment, hate or offensive language; false or misleading information; not about the hotspot or its Wi-Fi; shares someone's personal information; something else (details required).

### Content covered

Hotspot reviews (E03), discussion posts, and discussion comments and replies (E08) all follow this policy through one shared workflow (`moderation/registry.py`). Where this page says "review", the same applies to forum content unless noted below.

### Automated checks on ratings and written reviews

The checks run when a contributor submits or edits a rating or written review.

| Tier | Triggers | Outcome |
| --- | --- | --- |
| Block | External links in any letter case, email addresses, phone numbers, and terms from `MODERATION_BLOCKED_TERMS`. People can cite government, education and NYPL sites and identify an official SSID or the guest.net network by name. | The form keeps the draft and explains the error. |
| Hold | Promotional wording; profanity; text identical to another review; mostly capital letters; heavily repeated characters or words; at least `MODERATION_BURST_LIMIT` (3) earlier reviews within `MODERATION_BURST_MINUTES` (10) minutes; an author with `MODERATION_REPEAT_OFFENDER_REMOVALS` (2) or more removed reviews | Saved but hidden from the public, the map API and average ratings until an administrator approves or removes it. |
| Trust | `MODERATION_TRUSTED_MIN_REVIEWS` (3) published reviews at least `MODERATION_TRUSTED_MIN_AGE_HOURS` (24) hours old, with none ever removed | The capitals, repetition and posting-speed rules are skipped. Spam, profanity and duplicate rules still apply. |

Star-only ratings count toward the same posting limit as written reviews. The account-history and trust rules also apply. Contributors can flag another person's published rating from its hotspot profile. Held ratings enter the public average after approval.

### Discussion posts and comments

- The same block and hold rules run on a new post (title and body) or comment. Duplicates are compared with the author's other posts, or other comments. Comments are held for posting speed only after `MODERATION_COMMENT_BURST_LIMIT` (10) earlier comments in `MODERATION_BURST_MINUTES`, since conversations are faster than reviews.
- Trust: trusted reviewers, or authors with `MODERATION_TRUSTED_MIN_REVIEWS` (3) public posts/comments at least `MODERATION_TRUSTED_MIN_AGE_HOURS` old and nothing ever removed.
- A held post is visible only to its author, takes no comments or votes, and is announced to followers of its hotspot only when approved. A held comment is visible only to its author; if it has public replies, others see a "hidden while a moderator reviews it" placeholder so the replies keep their place.
- Removing a post deletes its comments; removing a comment deletes its replies. The removal page says how many will go.
- Administrators also get a **Recent discussions** tab (newest posts and comments, with open-flag counts).

### Community auto-hide

All flags are visible to moderators. An item is hidden automatically when `MODERATION_AUTO_HIDE_FLAGS` (3) different reporters have open flags and each account was at least `MODERATION_FLAGGER_MIN_AGE_HOURS` (24) hours old when its flag was submitted. A flag retains its original eligibility as the account ages.

### Decisions

- Only administrators approve, remove or dismiss.
- Removal deletes the item (as author deletion does). The moderation log keeps a copy of the text, the author, the reason, an optional note, the flag count and the administrator. Administrators never edit an author's words.
- Every approval, removal and dismissal is logged.
- A held author sees "Awaiting moderator approval" on their own content. In-app notices for holds, hides, approvals, removals and flag outcomes are described in `docs/E07-NOTIFICATIONS.md`.

## Acceptance criteria for the extensions

**Automated checks**
- A review containing a link, email address, phone number or configured blocked term is rejected with an explanation and nothing is saved.
- A review matching a hold rule is saved, hidden from the public page, the map API and the average, and listed under **Held for review** with the rule that triggered it.
- The author sees their held review marked "Awaiting moderator approval"; other users and visitors do not see it, and it cannot be flagged or upvoted.
- An edit is re-checked. An edit never publishes a held review, and it never clears a hold or restores a removed review, even when the hold or removal happens while the author is editing.
- A trusted author is not held for capitals, repetition or posting speed.

**Community auto-hide**
- The third eligible flag on a public item hides it until an administrator decides. Flags from newer accounts stay available for manual review.

**Administrator decisions**
- An administrator can approve a held item. Approval publishes exactly the text the administrator viewed; if the author edited it after the queue was opened, nothing is published and the administrator is told to check the new text.
- Bulk approval publishes only selected items that are still held and unchanged, and reports any it skipped.
- Bulk removal is two steps, consistent with US20's confirmation requirement. The first submission only shows a confirmation page with the count, each selected item and the consequences, and deletes nothing. Items are removed only after the confirmation is submitted with a reason. Cancel keeps every record.
- Removing an item that no longer exists changes nothing and logs nothing.
- Visitors are sent to log in and contributors get 403 for every administrator page and action.

Test coverage: `moderation/tests.py` (US19–US21), `moderation/test_automod.py` (rules, holds, auto-hide, bulk), `moderation/test_review_fixes.py` (concurrent edits, stale approvals, bulk confirmation), `moderation/test_forum.py` (the same rules for discussion posts and comments).
