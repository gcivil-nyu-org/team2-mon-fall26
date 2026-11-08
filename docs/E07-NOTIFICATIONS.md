# E07 US27 — Notification rules (proposed for team agreement)

Story: [US27 / #37](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/37). The acceptance criteria require the team to agree on channels, preferences and timing; this document is the proposal implemented in the `notifications` app. Adjust it here and in `notifications/services.py` if the team decides differently.

## Channel, timing and preferences

- **Channel:** in-app only — the **Inbox** page (`/inbox/`) and an unread count in the header for signed-in contributors. No email or push: the app has no mail configuration and the Story only needs in-app delivery.
- **Timing:** a notification is created immediately, when the content becomes publicly visible. A review held by the automated checks notifies followers only when an administrator approves it. There are no digests.
- **Preferences:** `/inbox/preferences/`. Each followed-hotspot update type (reviews, availability reports, discussions) can be switched off. Everything is on by default; no preference row means all on. Moderation notices and hotspot retirement are always sent.
- **Never notified:** about your own actions, about activity on retired hotspots, or about demo reviews.

## Followed hotspots (sent to each follower)

| Event | Text example | Opens | Opt-out |
| --- | --- | --- | --- |
| New rating/review published (on save, or on approval of a held review) | sam rated Bryant Park 4/5 and wrote a review. | The review (`#review-<id>`); rating-only → `#reviews` | Yes |
| New Working/Unavailable report | 3 new availability reports on Bryant Park. Latest: unavailable. | `#availability` | Yes |
| New discussion topic linked to the hotspot | ana started a discussion about Bryant Park: “…”. | The topic | Yes |
| Hotspot retired by an administrator (E04) | Bryant Park was removed from the public hotspot list. | My followed hotspots | No |

- Editing a review does not notify. A review is announced at most once, even if it is later hidden by flags and approved again.
- Availability reports are **batched**: while a follower has an unread availability notification for a hotspot, new reports update that one (count and latest status) instead of adding more.

## Moderation (sent to the author or flagger; always on)

| Event | Recipient | Opens |
| --- | --- | --- |
| Review held by the automated checks (first time only, not again on each edit while held) | Author | The author's contribution panel (`#contribute`) |
| Review hidden after enough community flags | Author | `#contribute` |
| Held review approved | Author | `#contribute` |
| Review removed — includes the moderation reason; never the private log note or who flagged it | Author | The hotspot's contribution panel |
| Flagged review removed / kept (dismissed or approved) | Each user who flagged it | The review if still public, otherwise the hotspot's reviews |

Dismissing flags does not notify the author, who was never told the review was flagged.

## Opening a notification

Selecting a notification marks it read and opens the related hotspot, review or discussion. If that content no longer exists or is no longer public (deleted, removed, held, or its hotspot retired), the user returns to the Inbox with an explanation. Users can open only their own notifications (others return 404). The Inbox has All/Unread filters, "Mark all as read" (POST), and 20 notifications per page.

## Not included (possible follow-ups)

- Replies to your forum posts/comments and helpful votes on your reviews.
- Moderation notices for E08 forum content: the hooks live in the shared moderation services, so they will fire once forum types are registered, but the wording currently says "review".
- Email delivery, digests and retention/cleanup of old notifications.
