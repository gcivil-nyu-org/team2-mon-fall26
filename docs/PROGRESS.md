# Project progress

Last updated: **November 8, 2026**.

This document records implementation progress, remaining work, and development history for Connect NYC. GitHub and ZenHub remain the sources for requirements, assignments, and workflow status. Update this record as work progresses; preserve the dated archive below.

## Current release and presentation record — November 2, 2026

PR #71 merged at `595330032ec5bb890ca25969e73eb9f6cca57cca`. Main and develop have identical file contents; main has two additional merge-history commits. [Main Travis build 279108564](https://app.travis-ci.com/github/gcivil-nyu-org/team2-mon-fall26/builds/279108564) passed all 223 tests and completed the configured production deployment stage. Production read-only checks show following, availability, review flagging, the administrator moderation queue/log and the discussion forum. Full write/decision acceptance remains separate from those observations.

The Week 7 milestone records **8 of 8 Stories closed and 11 closed points**. E05 US19–US21 and E06 US22–US24 are closed. E07 US25/US26 passed production acceptance on November 2 and are closed without point estimates; their GitHub status was rechecked on November 8. E08 US28–US30 are merged additional implementation, tracked separately from the eight-story milestone and moved to Review/QA. The original Sprint Planning forecast was not recorded; no retrospective estimate is substituted for it.

The [Week 7 Sprint Plan](https://github.com/gcivil-nyu-org/team2-mon-fall26/wiki/Week-7-Sprint-Plan) follows the required eight-part presentation order. The README and Wiki show main CI and develop coverage badges. The verified develop badge reports 98%; the main coverage badge returns unknown. Coverage includes tests and migrations under the configured `--source=.` scope.

Week 6 remains accepted and complete: Boqing confirmed production on October 26, all 11 Stories closed, and the nine estimated Stories completed 19 of 19 points. Older review entries below preserve the state at the time they were written.

## E07 US27 notifications — November 8, 2026

US27 in-app notifications merged into `develop` through PR #77 and are being reviewed for production in [PR #78](https://github.com/gcivil-nyu-org/team2-mon-fall26/pull/78). Followers receive review/report summaries, availability alerts, linked discussions and retirement notices; authors and flaggers receive moderation decisions. Channel, timing and preference rules are documented in [E07-NOTIFICATIONS.md](E07-NOTIFICATIONS.md).

Review reproduced duplicate summaries and duplicate outage alerts under simultaneous requests. The follow-up fix serializes these writes with MySQL row locks and adds two regression tests. All **266 tests passed on isolated MySQL 8.4**, with Black, Flake8, Django system checks and migration consistency checks passing. The fix still requires an independent PR approval before merging into `develop`; production promotion and acceptance remain pending. US27 is not closed.

## E07 production PR — November 2, 2026

[PR #62](https://github.com/gcivil-nyu-org/team2-mon-fall26/pull/62) promotes US25/US26 from the E07 branch to `main`. It synchronizes the existing main/E04 changes, preserving all administrator data-management routes, and fixes the expired-session follow/unfollow login return. These POST-only actions now send visitors back to the hotspot profile after sign-in so they can retry. US27 notifications remain unimplemented. Merge, CI/deployment completion and production acceptance are separate states; see the dated validation entry below.

The earlier milestone notes below are retained as historical context. E04 is already included in main `6510446`; this PR does not introduce a second E04 implementation. E05/E06 work on `develop` is outside this E07 production PR.

## Earlier milestone record

E01 discovery is integrated in `main` through PRs #47 and #48. The E01 Epic, source-label story #28, and data/acceptance support tasks #42 and #43 are closed. The production deployment was recorded in PR #50; this review does not verify which revision is currently deployed.

E02 account registration and access (US06–US10) merged through [PR #52](https://github.com/gcivil-nyu-org/team2-mon-fall26/pull/52) on October 24 (New York time). E03 review creation, editing, deletion and helpful votes merged through [PR #53](https://github.com/gcivil-nyu-org/team2-mon-fall26/pull/53) on October 26. E02/E03 Epic and Story workflow closure and deployed acceptance remain separate from code implementation.

The October 26 review passed **92 automated tests against isolated MySQL 8.4**, Django system checks and migration consistency checks. Browser checks covered registration and return to the hotspot, review validation, creation, editing, rating updates, helpful vote add/remove, and deletion confirmation/cancellation. Actual deletion and ownership protections are covered by the automated tests.

E04 administrator import/list/edit/retirement (US16–US17, Boqing) is implemented in [PR #54](https://github.com/gcivil-nyu-org/team2-mon-fall26/pull/54) on `boqing-E04-US16-17`. The integrated suite passed **114 tests on isolated MySQL 8.4**; Django system and migration consistency checks passed. The author self-review and independent code-review pass found no remaining blockers. GitHub requires an approval from another account before merge, and automatic merge is disabled; production deployment and acceptance are also pending. The original Week 6 forecast remains 19 points for nine E02/E03 stories; the two E04 stories were added on October 26 without retrospective point estimates.

## Epic overview

| Epic | Implementation status | Remaining scope |
| --- | --- | --- |
| [E01 — Finding a Wi-Fi Hotspot](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/1) | Merged; Epic closed | Preserve discovery behavior while integrating new contributions. |
| [E02 — Account Registration & Access](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/2) | Accepted and closed in Week 6; production confirmed by Boqing on October 26 | Preserve account and permission regressions. |
| [E03 — Rate & Review Hotspots](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/3) | Accepted and closed in Week 6, including helpful votes | Preserve rating/review ownership and moderation behavior. |
| [E04 — Maintain Official Hotspot Data](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/4) | PR #54 merged; accepted and closed in Week 6 | Scheduled refresh and restoration remain outside the current increment. |
| [E05 — Moderate Community Content](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/5) | US19–US21 closed; PR #60 promoted to main through #67; production moderation interface visible | Complete the deployed reporting/decision journey. Review-only registration is implemented; shared forum moderation remains separate. |
| [E06 — Report Availability & Assess Reliability](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/6) | US22–US24 closed (11 points); implementation and #68 login-return fix merged into main | Complete deployed submission checks. Seating/accessibility tags remain unimplemented. |
| [E07 — Follow Hotspots & Receive Updates](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/7) | US25/US26 accepted and closed; US27 merged into develop through #77 | Merge the reviewed notification concurrency fix, complete PR #78 promotion, and verify US27 in production. |
| [E08 — Discussion Forum & Community Interaction](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/15) | US28–US30 merged in #64 and synchronized in #66; moved to Review/QA | Complete deployed topic/reply/vote acceptance; E05 reporting/moderation remains a separate dependency. |

## User Story progress

“Implemented” means the specified demo behavior exists and has been checked. “Partial” means supporting code exists but the complete story or its acceptance verification remains outstanding. “Not implemented” does not imply that no planning or design work has been done.

### E01 — Discovery and profiles

| Story | Owner | Status and remaining work |
| --- | --- | --- |
| [US01 / #8 — Interactive map](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/8) | Boqing | Implemented. Official markers, matching preview/profile links, and distinct selection for records sharing coordinates. |
| [US02 / #9 — Location search](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/9) | Jiahao | Merged in PR #48. Free-text `q` search over name, address/description, neighborhood, borough and ZIP; every word must match. Matching markers only, "X of Y hotspots match" count, and a separate no-match message. |
| [US03 / #10 — Borough/neighborhood filters](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/10) | Jiahao | Merged in PR #48. `borough` and `neighborhood` (2010 NTA name, grouped by borough) filters; each can be selected, changed, or removed with its chip or "Clear all". |
| [US04 / #11 — Provider filter](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/11) | Jiahao | Merged in PR #48. `provider` filter using the same select/change/remove behavior. |
| [US05 / #12 — Hotspot-type filter](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/12) | Jiahao | Merged in PR #48 against the official `type` field (`access_type`: Free, Limited Free, Partner Site), labelled "Access type". Team to confirm whether a grouped `location_type` filter is also wanted. |
| [US31 / #41 — Profile and existing reviews](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/41) | Boqing | Implemented. Public official profile, hotspot-specific reviews, average/no-rating state, and explicit demo labels. |

E01 also integrates US12 / #22 from E03 and US18 / #28 from E04. Their original Epic parents and owners remain unchanged.

### E02 — Account access

Owner: Jiahao (Week 6). All five stories are implemented and merged through PR #52.

| Story | Status and remaining work |
| --- | --- |
| [US06 / #16 — Sign up](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/16) | Accepted and closed. Merged in PR #52. `/accounts/signup/` asks for username, email and password. Clear errors for invalid input, weak passwords, and usernames/emails that already exist (case-insensitive). New accounts join `Contributors` and are signed in. |
| [US07 / #17 — Log in](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/17) | Accepted and closed. Merged in PR #52. `/accounts/login/` with a single generic error for wrong username, wrong password or inactive account. Header shows "Signed in as …" and a success message. |
| [US08 / #18 — Log out](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/18) | Accepted and closed. Merged in PR #52. Header Log out button (POST) ends the session, returns to the map with a message, and contribution views redirect to login afterwards. |
| [US09 / #19 — Sign-in for contributions](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/19) | Accepted and closed. Merged in PR #52 for the E02 side. Public pages stay anonymous. Profiles show a "Rate this hotspot" prompt that sends visitors to log in or sign up and returns them to `#contribute`. `contributor_required` gives any contribution view the same login-and-return behavior. PR #53 integrates the E03 form entry point; registration and return to the hotspot were checked locally on October 26. Report/flag actions belong to E05. |
| [US10 / #20 — Administrator access](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/20) | Accepted and closed. Merged in PR #52. Visitor/contributor/administrator roles (superuser or `Administrators` group). `/manage/` and the Admin header link are administrator-only; contributors get 403 even by direct URL and cannot use Django admin. `set_administrator` command grants or revokes the role. E04/E05 tools should use `administrator_required`. |

### E03 — Hotspot ratings and reviews

| Story | Status and remaining work |
| --- | --- |
| [US11 / #21 — Rate/review a hotspot](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/21) | Accepted and closed. Implemented (code + automated tests). Signed-in contributors choose 1–5 stars and an optional review (max 2,000 characters) at `/hotspots/<id>/review/`; saved against the hotspot and the user. One review per user per hotspot (database constraint); a second attempt goes to edit. Visitors are redirected to log in. |
| [US12 / #22 — Average rating](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/22) | Read-side implemented; Jiahao retains ownership. Owner acceptance test merged in PR #48 and rechecked with E03: 1 and 3 → 2.0; add 5 → 3.0; edit 1 to 4 → 4.0; delete 5 → 3.5; unrated hotspot shows "No ratings yet" and a null API average. Contribution UI is implemented in PR #53. |
| [US13 / #23 — Edit own rating/review](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/23) | Accepted and closed. Implemented (code + automated tests). Edit link only on the author's own entries; `/reviews/<id>/edit/` returns 404 for other users and for demo reviews. Averages update from the saved rating. |
| [US14 / #24 — Delete own rating/review](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/24) | Accepted and closed. Implemented (code + automated tests). Delete link only on own entries; a confirmation page precedes a POST-only delete; other users get 404; averages update. |
| [US15 / #25 — Helpful-review upvotes](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/25) | Accepted and closed. Implemented (code + automated tests, MLP). `ReviewVote` is unique per user and review; POST toggles add/remove; count shown on each written review; no downvotes; votes never affect star averages. Authors cannot upvote their own review; the current implementation is included in the team’s accepted scope. |

### E04 — Official data

| Story | Status and remaining work |
| --- | --- |
| [US16 / #26 — Import/view official records](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/26) | Accepted and closed. Implemented by Boqing. Administrator CSV upload and paginated/searchable Active/Retired list; shared atomic importer validates the whole file, preserves IDs and contribution links, and reports created/updated counts. Merged in PR #54; production acceptance confirmed by Boqing on October 26. |
| [US17 / #27 — Update/remove records](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/27) | Accepted and closed. Implemented by Boqing. Allowlisted editing preserves identity/acquisition date; confirmed POST retires the record, hiding public discovery and contribution routes while retaining reviews/votes. Reimport and edits never reactivate retired records. Merged in PR #54; production acceptance confirmed by Boqing on October 26. |
| [US18 / #28 — Official/community labels](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/28) | Implemented by Boqing and integrated into E01. Official fields, source dates, community feedback, and fictional demo contributions are visibly distinguished. |

### E05–E08 — Remaining community features

| Epic | Story | Status |
| --- | --- | --- |
| E05 | [US19 / #29 — Review content and flags](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/29) | Story closed; implemented in PR #60 and promoted to main through #67. `/manage/moderation/` (administrators only; contributors get 403) opens on **Held for review** (automated holds and community auto-hides, with Approve/Remove and bulk actions) and also has flagged content (type, link to the original, flag count, reasons, notes), recent ratings and reviews (newest 50 per page, including rating-only entries, with open-flag counts), and the moderation log. Linked from `/manage/`. |
| E05 | [US20 / #30 — Remove violations](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/30) | Story closed; implemented in PR #60 and promoted to main through #67. Removal requires a confirmation page and a moderation reason (proposed list in `moderation.models.Reason`; team to confirm). The review is deleted, so it leaves public pages and the average recalculates; a `ModerationRecord` keeps a text snapshot, reason, note, flag count and administrator. Administrators cannot edit text. "Dismiss flags" closes flags without changing content and is logged. |
| E05 | [US21 / #31 — Flag inappropriate content](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/31) | Story closed; implemented in PR #60 and promoted to main through #67 for hotspot reviews. Signed-in contributors see a Flag link on other users' written reviews and choose a reason ("Something else" requires details). One flag per user per item, enforced by a database constraint; authors cannot flag their own reviews; visitors are sent to log in. Flags close automatically if the author deletes the review. E08 forum content uses the same flow once registered. |
| E06 | [US22 / #32 — Report Working/Unavailable](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/32) | Story closed (3 points). Working/Unavailable reporting and #68 safe login-return fix are merged into main. Production controls are visible; deployed submission acceptance remains to be completed. |
| E06 | [US23 / #33 — Reliability and report recency](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/33) | Story closed (5 points). Reliability and report recency are merged into main; the three-reporter threshold and 30-day reporting window are retained. |
| E06 | [US24 / #34 — Sort by rating/reliability](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/34) | Story closed (3 points). Rating/reliability sorting is merged into main and covered by the integrated test suite. |
| E07 | [US25 / #35 — Follow/unfollow](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/35) | Accepted in production on November 2 and closed. Follow/unfollow updates only the relationship, preserves the hotspot/reviews, and safely returns visitors after login. |
| E07 | [US26 / #36 — My followed hotspots](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/36) | Accepted in production on November 2 and closed. Verified the personal list, correct profile link and helpful empty state after unfollowing. |
| E07 | [US27 / #37 — Notifications](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/37) | Merged into develop through PR #77; production promotion is PR #78, pending the reviewed concurrency fix. In-app Inbox at `/inbox/` with header unread count, All/Unread filters, "Mark all as read" and per-type opt-outs at `/inbox/preferences/`. Followers get one unread summary per hotspot for new ratings/reviews (counted once, when public) and for availability reports; a "may be down" alert when 3 people report Unavailable within 24 hours or reliability falls below 50%, and a "working again" notice at 70%; linked discussions; and hotspot retirement. Authors and flaggers get moderation notices (held, hidden by flags, approved, removed with reason; flag outcome). Opening marks read and goes to the content, or back to the Inbox if it is gone. Rules in [E07-NOTIFICATIONS.md](E07-NOTIFICATIONS.md) await team agreement; not estimated. |
| E08 | [US28 / #38 — Browse/create discussion topics](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/38) | Review/QA; merged into main through PR #64, with integrated CI passing 223 tests. Production write acceptance remains open. Public discussion listing and detail; signed-in contributors create questions or discussion topics, optionally linked to an active hotspot. |
| E08 | [US29 / #39 — Comments and replies](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/39) | Review/QA; merged into main through PR #64, with integrated CI passing 223 tests. Production write acceptance remains open. Contributors add comments and threaded replies; public visitors can read them. |
| E08 | [US30 / #40 — Forum upvotes](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/40) | Review/QA; merged into main through PR #64, with integrated CI passing 223 tests. Production write acceptance remains open. One toggleable helpful upvote per user on posts/comments; no self-votes or downvotes. Separate from E03 review votes and star ratings. |

## Support and planning

| Item | Current record |
| --- | --- |
| [#42 — Data, mapping and ERD](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/42) | Kavya and Suvan. Issue closed; the data Wiki includes the ERD added October 19. Some original checklist text remains stale. |
| [#43 — Acceptance checks and demo verification](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/43) | Xiaoqi. Issue closed October 19 for the E01 increment. E02/E03 deployed acceptance is a separate follow-up. |
| [#45 — Week 4 design and backlog goal](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/45) | Closed Week 4 planning/design issue; retained as historical sprint work. |
| [#13 — Previous requirements sprint goal](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/13) | Closed planning issue. |
| [#14 — Superseded E08 entry](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/14) | Closed duplicate; active E08 is #15. This is not evidence of an implemented forum. |

Closed test issue #44 is excluded from product completion progress.

## Next development steps

1. Complete the production contribution/moderation and E07/E08 acceptance journeys against the current release. Prepare suitable demonstration content and close Stories only after their acceptance checks pass.
2. Obtain independent approval for the US27 concurrency fix, merge it into develop, and recheck PR #78 CI before production promotion. Verify notification preferences, delivery and target links in production before closing US27. US25/US26 are already accepted and closed.
3. Resolve main-specific Coveralls attribution. The current working coverage badge tracks develop; keep the existing CI formatting, linting and MySQL regression suite.
4. Record the original forecast and estimates during Sprint Planning. Keep added work explicit, maintain the Wiki/milestone records and add one tab per sprint to the cumulative retrospective report.
5. Preserve E03 hotspot-review, E08 discussion and E05 shared-moderation boundaries when planning forum reporting integration.

## Development archive

### November 8, 2026 — PR #78 notification concurrency review

- Reviewed the 28-file develop-to-main notification change, including event hooks, recipient ownership, preferences, moderation visibility, migration and UI links. Both Travis checks passed for original head `142e66a`; all original 264 tests also passed locally on MySQL 8.4.
- Reproduced two failures with independent MySQL connections: simultaneous reviews created two unread summaries instead of one; simultaneous reports generated two outage alerts for one state change. Added transaction and row locks for summary creation/update and alert transitions, plus two regression tests that fail before the fix and pass afterward.
- Verified the fixed code with all 266 MySQL tests, Black, Flake8, `manage.py check`, and `makemigrations --check --dry-run`. No migration or notification-policy change is required.
- Branch rules require a PR and one independent approval for develop. The fix is awaiting that approval; PR #78 and production acceptance remain pending. Reconciled US25/US26 progress against their existing accepted/closed GitHub records.

### November 7, 2026 — US27 follow-up: summaries and availability alerts

- After review, followers no longer get one notification per rating/review. Reviews are folded into one unread summary per hotspot ("3 new ratings and reviews on …"), like availability reports; `ReviewAnnouncement` ensures each review is counted once.
- Added availability alerts: a hotspot "may be down" when at least 3 different people's latest reports in the last 24 hours say Unavailable, or its E06 reliability score is below 50%; it is "working again" at 70% with no burst. Alerts are sent only on these state changes (`AvailabilityAlertState`) and have their own preference. Thresholds are settings (`AVAILABILITY_ALERT_*`). Rationale and sources are in E07-NOTIFICATIONS.md.
- The unmerged `notifications/0001` migration was regenerated. Verified with SQLite: all 264 tests pass (41 in `notifications`, 99% coverage of the app); Black, Flake8 and `makemigrations --check` pass. Not yet run on MySQL or CI.

### November 7, 2026 — E07 US27 in-app notifications

- Branched `linj-E07-US27-notifications` from develop `034e762`. Added the `notifications` app: `Notification` (recipient, kind, optional hotspot and generic target, text snapshots, batch count, read time) and `NotificationPreference` (three followed-hotspot opt-outs, default on), migration `notifications/0001`.
- Triggers are explicit calls after each change is saved: E03 review creation (`reviews/views.py`), E06 availability reports, E08 topic creation with a hotspot, E04 retirement (only on an active → retired change), and the shared E05 services (`hold`, `auto_hide_if_widely_flagged`, `approve`, `dismiss_flags`, `remove_content`). Followers never hear about their own actions; retired hotspots and demo reviews produce nothing.
- Added the Inbox, open/redirect, mark-all-read (POST) and preference views, the header "Inbox" link with unread badge (context processor), and styles. The signed-in mobile header previously overflowed at 390px width (510px page); it now moves the navigation to its own scrollable row and the page fits (390px) on the map, profile, followed and Inbox pages.
- Verified locally with Django's SQLite backend (MySQL client not available in this environment): all 258 tests pass (223 existing, 35 new in `notifications/tests.py`, 99% coverage of the app); Black, Flake8, `manage.py check` and `makemigrations --check` pass. Headless-Chrome checks at 1280px and 390px covered the Inbox, preferences, opening a notification and the mobile header. Not yet run against MySQL or in CI, not merged or deployed.

### November 2, 2026 — PR #67 promotion review and E06 login-return fix

- Reviewed develop head `1059966`, whose tree matches the previously reviewed PR #66 revision. E05/E06 and CI changes are promoted alongside the existing E07/E08 work; migrations add availability/moderation storage and the review hold flag without deleting user data.
- Two new MySQL regression tests reproduced the incorrect login destination for expired-session Working/Unavailable submissions. Replaced the endpoint-based redirect with a return to the active hotspot profile's availability section, retaining the shared active-contributor role check and POST-only writes.
- All 223 tests passed on isolated MySQL 8.4 in 37.683 seconds, including actual sign-in, successful profile return, no automatic report creation and an explicit retry for both statuses. Black checked 92 files; Flake8, Django system checks, migration consistency and diff checks passed.
- Latest-head CI, merge and deployment/production acceptance must be verified separately. No new Story closure or production database modification is claimed by the local validation.

### October 30, 2026 — E06 availability reports, reliability score and sorting (US22, US23, US24)

- Added the `availability` app: `AvailabilityReport` (hotspot, reporter, Working/Unavailable, timestamp) with migration `0001`, a POST-only `contributor_required` report view, and an "Availability reports" section on the hotspot profile. Reports are stored separately from `reviews.Review`, so ratings and averages are unchanged.
- Proposed reliability rules, kept as constants in `availability/services.py` for the team to adjust: a report counts for 30 days; each person's newest report per hotspot is the only one counted; the score is the share of those reports that say Working; no score is shown until 3 different people have reported ("Not enough reports yet"). The profile labels reports as community observations, not a guarantee of live connectivity, and shows each report's source and date.
- Added a "Sort by" control to the map page and `sort=rating|reliability` to the JSON API. Hotspots without a rating or enough reports come after those with data, ties keep the default order, and sorting combines with the existing filters. Sorting is not counted as a filter. The API records now include `reliability_score` and `availability_report_count`.
- Open decisions for the team: conflicting-report handling beyond "newest per person", seating/accessibility tags (not started), and whether reports need a cooldown against repeat submissions.
- Verified: 112 tests passed before merging `develop` (92 existing and 20 new in `availability/tests.py`), and all 204 pass after merging the E05 and E07 work from `develop` (Nov 1), with Django's SQLite backend, `makemigrations --check`, and a manual browser check of the profile section and the reliability sort against the 36-hotspot sample. Not yet run against MySQL or in CI, not yet deployed.

### November 1, 2026 — E05 content flags and moderation (US19, US20, US21)

- Branched `jiahao-E05-US19-21` from `develop` and merged `main` to bring E04 (PR #54) into the E07 line. The only conflict was `hotspots/urls.py`, resolved by keeping both the E07 follow routes and the E04 `/manage/hotspots/` routes. E07 follow views already exclude retired hotspots.
- Added the `moderation` app: `ContentFlag` (generic reference to the flagged item, unique per user per item, status open/removed/dismissed/withdrawn) and `ModerationRecord` (append-only log with a content snapshot), migration `moderation/0001`. A registry of flaggable types keeps one workflow for E03 reviews and future E08 content.
- Added the flag form, administrator moderation view (flagged / recent / log), removal confirmation with required reason, flag dismissal, an Administration-page panel, Flag links on the hotspot profile, and Django admin registrations (log is read-only).
- Design decision: removal deletes the review (as author deletion does) and keeps a snapshot in the log rather than soft-hiding it, so no existing review query changes. The author can post a new review afterwards.
- Added 26 tests in `moderation/tests.py`. The full **149-test suite passed** locally on MariaDB 10.11 with both `DEMO_MODE=1` and the CI settings (`DEMO_MODE=0`, `DJANGO_DEBUG=0`); Django system and migration consistency checks passed. CI on MySQL 8.4 has not run yet.
- Browser checks (Chromium): visitors see no Flag link; contributor flag with empty-reason error, success message and "Flagged for review" state; administrator panel counts, flagged view, recent view, removal confirmation and log; review gone from the public profile with the average updated; contributor gets 403 on `/manage/moderation/`.
- Added automated moderation the same day, before the branch was pushed (beyond the #29–#31 acceptance criteria, so the team may want a separate story or a note on E05): `moderation/automod.py` blocks links/emails/phone numbers and configured terms at submit; holds promotional wording, profanity, duplicates, ALL-CAPS, repetition, fast posting and repeat offenders; lets trusted authors skip the soft rules; and auto-hides a review after 3 distinct user flags. Held reviews (`Review.is_held`, migration `reviews/0003`) are excluded from public pages, the map API and averages via `visible_reviews()`; authors see an "Awaiting moderator approval" badge. Administrators get a default **Held for review** tab with per-item Approve/Remove and bulk approve/remove; approvals are logged. The unpushed `moderation/0001` migration was regenerated (automated flags have no user; the log records the author).
- Re-verified: **171 tests pass** (22 new in `moderation/test_automod.py`) locally on MariaDB 10.11 with `DEMO_MODE=1` and with the CI settings; migration consistency checks passed. Browser checks: blocked link error with nothing saved, held message and author badge, held review absent from the public page and average, held tab with automated reasons, bulk remove of two items, single approve, and the phone-width layout of the bulk toolbar.
- PR #60 review (Boqing, changes requested) fixes: (1) author edits now lock the review row and save only rating/text (`update_fields`), so a hold made during the edit is kept and a review removed during the edit is not recreated; moderator removals, dismissals and approvals lock the same row. Approvals also carry the version the administrator viewed and refuse to publish text edited after that. (2) Bulk removal is now two steps: the queue button opens a confirmation page listing the selected items and nothing is deleted until it is confirmed with a reason. (3) The policy and extended acceptance criteria are documented in `docs/E05-MODERATION-POLICY.md`, pending team agreement. Added `moderation/test_review_fixes.py` (13 tests), including deterministic interleavings that fail against the previous code. **184 tests pass** locally on MariaDB 10.11.
- Noted, not changed: on a 390 px viewport the signed-in header is wider than the screen because of the E07 "My followed hotspots" link.

### November 2, 2026 — E08 discussion forum MVP (US28–US30)

- Added the separate `forum` app with public discussion listing/detail, question/discussion topics, optional active-hotspot references, threaded comments/replies, and unique per-user helpful upvotes on posts and comments.
- Contributor-only create/reply/vote actions use E02 access controls. Forum votes never modify E03 reviews or hotspot rating aggregates. The navigation links to Discussions.
- Added automated tests for public reading, contributor-only writes, threaded replies, vote add/remove/uniqueness, and review-rating isolation. All **136 tests** pass against the Docker Compose MySQL database; Django system checks and `makemigrations --check --dry-run` pass. Production deployment, manual browser acceptance and GitHub workflow state were not checked. E05 content reporting/moderation remains out of scope.

### October 24, 2026 — E03 rate, edit, delete and upvote reviews (US11, US13, US14, US15)

- Added `reviews` forms, views and URLs, templates (`review_form.html`, `review_confirm_delete.html`), the `ReviewVote` model, and migration `0002` (unique review per author per hotspot; unique vote per user per review). All views use `contributor_required`.
- The profile's contribution panel now shows the rating form entry point, or the user's own rating with Edit/Delete; written reviews show an upvote control and count.
- Updated one existing hotspot test that created several reviews by the same author for one hotspot, which the new constraint forbids.
- Added tests for each acceptance criterion in `reviews/tests.py`. Verified: all 90 tests pass against the Docker Compose MySQL database (`scripts/test.sh`). Not yet checked manually in a browser.


### October 20, 2026 — E02 account registration and access (US06–US10)

- Added the `accounts` app. `roles.py` defines visitor/contributor/administrator on Django's user model and groups (no custom user model, so existing review data is unaffected). Migration `accounts/0001_role_groups` creates the `Contributors` and `Administrators` groups.
- Added shared access checks in `accounts/permissions.py` (`contributor_required`, `administrator_required` and matching class-based mixins) and a `roles` context processor (`user_role`, `user_is_administrator`).
- Added sign-up, login (generic error) and POST-only logout views and templates, safe `?next=` handling, flash messages, header account navigation, the `/manage/` administrator area, a project 403 page, and the `set_administrator` management command.
- Added the US09 "Rate this hotspot" prompt to hotspot profiles (`hotspots/templates/hotspots/_contribute.html`) for E03 to extend.
- Settings: `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`; optional `DJANGO_CSRF_TRUSTED_ORIGINS` and `DJANGO_BEHIND_HTTPS_PROXY` for HTTPS deployment (documented in `.env.example` and README).
- Added 33 tests in `accounts/tests.py`, mapped to each story's acceptance criteria (stand-in contributor/administrator views test access rules ahead of E03/E04).
- Verified: all 72 tests, `manage.py check` and `makemigrations --check` pass against a local MySQL-compatible server (MariaDB 10.11), not yet in the Compose MySQL 8.4 container. Checked sign-up, login (including a wrong password), return to `#contribute`, the 403 for contributors on `/manage/`, logout, and the admin area in a headless browser at 1280, 375 and 320 px widths, with no horizontal scroll.
- Branch: `jiahao-E02-US06-10`.

### October 18, 2026 — E01 search and filters (US02–US05) and US12 checks

- Added `hotspots/filters.py`, shared by the map page and `/api/hotspots/`: `q` location search and `borough`, `neighborhood`, `provider` and `type` (official access type) filters, combined with AND. Blank values remove a filter; inactive records are never returned.
- Added the search/filter form above the map with removable filter chips, "Clear all", an "X of Y hotspots match" count, and a "No hotspots match your search" state separate from the empty-dataset state. Dropdowns apply on change with JavaScript and through the Search button without it. The API echoes the applied filters.
- Added 15 search/filter tests (expected hotspot IDs on page and API, select/change/remove, combined filters, no-match) and the US12 average-rating sequence test.
- Verified locally: all 39 tests, `manage.py check`, and `makemigrations --check` pass on SQLite. Checked the page against the 36-record sample in a desktop and a mobile browser. All 39 tests then passed against the Docker Compose MySQL database (`docker compose exec web python manage.py test`).
- Added optional `compose.dev.yaml` for live-reload development (documented in README).
- Branch: `jiahao-E01-US02-05`.

### October 16, 2026 — E01 foundation and first working demo

- Added Python/Django/MySQL project setup, migrations, Gunicorn/WhiteNoise, generated local environment settings, and Docker Compose startup with database/web readiness checks.
- Implemented US01, US31, and US18 behavior, including map selection, shared-coordinate record selection, public profiles, existing review display, source labels, and empty states.
- Integrated the team's official sample with stable `doitt_id` upserts and preserved review relationships. Added clearly labeled optional demo ratings/reviews that are hidden outside demo mode.
- Verified 21 tests against MySQL, Django system checks, and migration consistency. Verified desktop/mobile pages and fresh startup from a separate empty MySQL volume, including import and demo seeding.
- Initial implementation commit: `c0c309e`; initial draft: [PR #46](https://github.com/gcivil-nyu-org/team2-mon-fall26/pull/46).

### October 16, 2026 — Naming, project documentation, and handoff

- Renamed the profile's review section from “Community experience” to “Hotspot Reviews” while retaining its community-source label.
- Expanded README with the project description, implemented scope, and links to this progress record and agents.md. Corrected the average-rating dependency to US12 / #22.
- Created this Epic/Story progress baseline from current GitHub issues and implemented code. Added next steps and archival instructions.
- Created `boqing-E01-US01/31/18` from the implementation branch and pulled the latest main; no incoming changes or conflicts were found.
- Rebuilt the updated demo and reran all 21 MySQL tests, Django system checks, and migration consistency checks successfully before publication.
- Published the consolidated implementation and documentation in [PR #47](https://github.com/gcivil-nyu-org/team2-mon-fall26/pull/47), superseding the earlier draft #46.

### October 26, 2026 — PR #53 review and migration safeguard

- Reviewed E03 against US11, US13, US14 and US15, including authentication, ownership, CSRF, rating aggregates and helpful-vote isolation.
- Added a duplicate-review preflight before any MySQL DDL in migration 0002. Legacy duplicate hotspot/author pairs now stop with an actionable error; the migration never chooses or deletes user content automatically.
- Added two migration regression tests: unchanged unique/demo records upgrade successfully; duplicate records leave data/schema untouched and can be retried after an explicit data decision.
- Verified all 92 tests against a separate MySQL 8.4 Compose project, plus `manage.py check`, `makemigrations --check --dry-run`, and `git diff --check`.
- Verified the browser flows listed in the current milestone on the isolated localhost:8001 instance. Deletion was confirmed by automated tests; the browser check exercised confirmation and cancellation.
- Reconciled stale E01/E02 progress text with merged PRs and closed E01 issues. This records local review results, not new production acceptance or Story closure.

### October 26, 2026 — E04 administrator data maintenance (US16–US17)

- Assigned E04 and US16/US17 to Boqing and recorded the manual-refresh/non-destructive-retirement policy on the Epic and US17. US18 remains previously implemented and closed.
- Extracted the validated atomic CSV importer for web/CLI reuse; added administrator upload/list/search/status-filter/pagination, official-field editing and confirmed retirement.
- Retired records stay out of discovery, profiles and contribution actions. Existing reviews and helpful votes remain stored. Reimport does not reactivate records; field-limited edits cannot undo concurrent retirement or change source identity/acquisition date.
- Added 22 regression tests. The full **114-test suite passed on isolated MySQL 8.4**, plus Django system checks, migration consistency checks and diff whitespace validation. No schema migration is required.
- Browser checks verified visitor login/return, stored-record search, editing reflected on the public profile, cancellation and confirmed retirement, and the Retired filter. CLI reimport and database/public-route checks verified the retired record retained four local review fixtures and one helpful vote without returning to public discovery. CSV upload validation/idempotence/rollback were tested through Django's HTTP test client.
- Updated README and this progress archive. [PR #54](https://github.com/gcivil-nyu-org/team2-mon-fall26/pull/54) contains the implementation and author self-review. A normal merge attempt was blocked by the required external approval; automatic merge is disabled. No branch protections were changed. Deployment and production acceptance remain with the team; Docker is local validation only.


### November 2, 2026 — PR #63 CI quality and coverage review

- Added Black, Flake8 and coverage collection to the existing Docker/MySQL Travis workflow. The formatting changes preserve the AST of all changed production Python files and migrations; the only other Python change removes an unused test import.
- Review found that Coveralls was reading the default `/app/.coverage` instead of the generated `/tmp/.coverage`, and the application image contains neither Git nor `.git`. The upload command now points to the measured data and supplies Git metadata from the CI checkout through Coveralls' supported environment fallback. PR builds receive their PR number; normal branch builds omit the `false` sentinel in the uploader only, preserving the original Travis variable for deployment decisions.
- The reviewed code passed all **204 tests on isolated MySQL 8.4** (37.577 seconds), Black (83 files unchanged), Flake8, Django system checks and migration consistency checks. Coverage reported **99% across the configured `--source=.` scope**, which includes tests and migrations; this is not an application-only metric.
- Offline Coveralls payload checks against that actual coverage file produced **81 source files and 3,272 covered lines**, the exact tested head `368f549339c94cb1b41b80b6e99fc5caf1df2373`, and the expected PR association. A separate branch-build check correctly omitted the PR field. No payload was uploaded to Coveralls during local verification.
- Review fixes affect CI reporting only. PR merge, remote CI/Coveralls delivery, integration deployment and production acceptance remain separate steps and are not asserted by this validation record.

### November 2, 2026 — E07 production PR review and login fix

- Reviewed PR #62 at its original E07 head `4205bdc`. Synchronized main `6510446` into the branch and resolved `hotspots/urls.py` by retaining both E04 management and E07 follow/list routes. No E05/E06 code was included.
- Fixed the previously reproduced expired-session follow/unfollow HTTP 405: sign-in returns to the GET-safe hotspot profile for an explicit retry. Mutations remain POST-only, user-scoped and CSRF-protected.
- Added regression tests for follow and unfollow through actual login/return/retry, and GET mutation rejection. All **126 tests passed on isolated MySQL 8.4**, including existing E04 coverage. Django system checks, migration consistency and diff checks passed.
- Independent review found no additional blocking authorization, data or migration issue. The additive migration creates only HotspotFollow with a unique user/hotspot pair; existing rows are not rewritten.
- PR #62 targets main; existing Travis configuration can deploy production after a successful main build. This entry records local validation before merge, not CI success or completed production deployment/acceptance. US27 notifications remain future work. The login fix should also be synchronized back to develop.


### November 2, 2026 — PR #64 forum review fixes

- Reviewed the forum against US28–US30 and reproduced three defects before fixing them: discussion-list helpful counts multiplied by comment count; a malformed reply parent ID raised HTTP 500; and a 300-level reply chain raised RecursionError while rendering the thread.
- Count distinct forum votes across comment joins and validate reply IDs before querying. Render the existing nested comment markup using an iterative traversal, preserving sibling order and arbitrary reply nesting without recursive template calls.
- Added four regression tests covering combined comment/vote counts, invalid parent input, deep thread rendering and parent/sibling ordering. All **140 tests passed on isolated MySQL 8.4** (15.587 seconds); Django system checks, migration consistency checks and whitespace validation passed. No schema change is required for these fixes.
- This records local review validation before merge. CI success, deployment completion and production acceptance are not asserted; E05 reporting/moderation remains separate.

### November 2, 2026 — Week 7 presentation and delivery reconciliation

- Reconciled merged PRs #63–#71 with main/develop, the current milestone and production read-only observations. Main build 279108564 passed 223 tests. No new application tests or production writes were performed for this documentation update.
- Added branch-labeled CI/coverage badges and corrected stale README statements that CI, availability and reliability were unimplemented. Public badge responses were checked: main CI passing, develop coverage 98%, main coverage unknown.
- Updated the Wiki and milestone to the required eight-part presentation sequence, preserving the original E05 goal and recording E06/E07/E08/CI as additional work. Kept the original forecast unrecorded and distinguished 11 closed points from 6/8 closed milestone Stories.
- Created the cumulative retrospective report with separate Week 4–7 tabs, preserving earlier published retrospective matrices. Added implementation/acceptance notes to open E07/E08 Stories and moved implemented E08 Stories to Review/QA without closing or estimating them.
