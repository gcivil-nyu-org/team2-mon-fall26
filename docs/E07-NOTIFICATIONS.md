# E07 US27 — Notification rules (proposed for team agreement)

Story: [US27 / #37](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/37). The acceptance criteria require the team to agree on channels, preferences and timing; this document is the proposal implemented in the `notifications` app. Adjust it here and in `notifications/services.py` if the team decides differently.

## Channel, timing and preferences

- **Channel:** in-app only — the **Inbox** page (`/inbox/`) and an unread count in the header for signed-in contributors. No email or push: the app has no mail configuration and the Story only needs in-app delivery.
- **Timing:** notifications are created immediately, when the content becomes publicly visible (a held review counts only once approved). Routine followed-hotspot activity is folded into one unread summary per hotspot; there are no timed digests.
- **Preferences:** `/inbox/preferences/`. Each followed-hotspot type (review summaries, availability-report summaries, availability alerts, discussions) can be switched off. Everything is on by default; no preference row means all on. Moderation notices and hotspot retirement are always sent.
- **Never notified:** about your own actions, about activity on retired hotspots, or about demo reviews.

## Followed hotspots (sent to each follower)

Routine activity is **summarized**, not sent per item: while a follower has an unread summary for a hotspot, each new item increases its count and moves it to the top. After it is read, the next item starts a new summary. Availability **alerts** are the exception: they are sent individually, because they are what a follower most needs to see.

| Notification | Text example | Opens | Opt-out |
| --- | --- | --- | --- |
| Ratings and reviews summary | 3 new ratings and reviews on Bryant Park. Select to view. | `#reviews` | Yes |
| Availability reports summary | 3 new availability reports on Bryant Park. Latest: unavailable. | `#availability` | Yes |
| **Availability alert** — the hotspot may be down | Bryant Park may be down: 3 people reported it unavailable in the last 24 hours. | `#availability` | Yes (separately from the summary) |
| **Working again** — the alert has cleared | Bryant Park looks to be working again: its reliability score is back to 80%. | `#availability` | Same as alerts |
| New discussion linked to the hotspot | ana started a discussion about Bryant Park: “…”. | The topic | Yes |
| Hotspot retired by an administrator (E04) | Bryant Park was removed from the public hotspot list. | My followed hotspots | No |

- A rating or review counts when it becomes public: on save, or when an administrator approves a held review. Edits never count, and each review counts once even if it is later hidden by flags and approved again.

### Availability alert rules

Settings in `config/settings.py`; the values are proposals for the team.

- **May be down** when either:
  - **Burst:** at least `AVAILABILITY_ALERT_UNAVAILABLE_REPORTS` (3) different people's latest reports from the last `AVAILABILITY_ALERT_WINDOW_HOURS` (24) say Unavailable. This catches a sudden outage even at a hotspot with many old Working reports.
  - **Low reliability:** the E06 reliability score (30-day window, newest report per person, at least 3 people) is below `AVAILABILITY_ALERT_BELOW` (50%).
- **Working again** when there is no burst and the reliability score is at least `AVAILABILITY_RECOVER_AT` (70%).
- Alerts are sent only when the hotspot **changes state**, never on every report, so a hotspot that stays down produces one alert. The gap between 50% and 70% stops it flipping between "down" and "working again" on every report.

### Why these choices (how other systems do it)

- **Summaries instead of per-item notices.** Notification services recommend grouping similar notifications per item (here, per hotspot) so users are not flooded, while letting urgent alerts bypass batching ([SuprSend](https://docs.suprsend.com/docs/best-practices-for-batching-digest)).
- **Alert on a spike from several people, not one report.** Downdetector reports an incident only when problem reports are significantly above the normal level, and counts each person once ([Downdetector help guide, third-party copy](https://1-12b.pages.dev/help/guides/how-does-downdetector-determine-if-theres-an-incident); no official page was found). Our version is simpler: a fixed count of distinct people within 24 hours, plus the existing reliability score.
- **Separate start and clear thresholds.** Nagios uses a high threshold to start "flapping" and a lower one to stop, and sends one notice when the state starts and one when it ends ([Nagios](https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/4/en/flapping.html)). Our 50% / 70% pair and the "may be down" / "working again" pair follow the same pattern.

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
