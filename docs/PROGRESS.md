# Project progress

Last updated: **October 20, 2026**.

This document records implementation progress, remaining work, and development history for Connect NYC. GitHub and ZenHub remain the sources for requirements, assignments, and workflow status. Update this record as work progresses; preserve the dated archive below.

## Current milestone

The Django/MySQL foundation and Boqing's assigned E01 demo work are implemented: interactive map (US01), hotspot profiles with existing reviews (US31), and official/community source labels (US18, an E04 dependency). The profile section is titled **Hotspot Reviews**. The demo has been validated with 21 automated tests against MySQL and desktop/mobile browser checks.

Jiahao's location search and borough/neighborhood, provider and access-type filters (US02–US05) and the US12 average-rating checks are implemented on branch `jiahao-E01-US02-05`. All 39 tests pass against MySQL; they are pending code review and merge.

**Full E01 is still in progress.** The remaining data-design deliverable (ERD) and full-journey acceptance checks are outstanding. Existing review display does not mean review creation, editing, or deletion has been implemented.

Implementation statuses below describe the code, not automatic issue closure. At this snapshot, all eight active Epic issues and all 31 User Story issues are open. US01, US31, and US18 were moved to In Progress in ZenHub. Work is published on `boqing-E01-US01/31/18` through [PR #47](https://github.com/gcivil-nyu-org/team2-mon-fall26/pull/47), which records review and merge state.

## Epic overview

| Epic | Implementation status | Remaining scope |
| --- | --- | --- |
| [E01 — Finding a Wi-Fi Hotspot](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/1) | Partially implemented | Search/filters and rating checks awaiting review and merge; ERD and complete acceptance checks. |
| [E02 — Account Registration & Access](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/2) | Implemented on branch `jiahao-E02-US06-10` (Jiahao); pending review and merge | Code review, merge, acceptance checks on the deployed site; E03 must plug its review form into the US09 entry point. |
| [E03 — Rate & Review Hotspots](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/3) | Create, edit, delete and helpful-vote code implemented (branch work, unreviewed) | Code review, merge, manual browser acceptance check; owner verification of US12. US15 remains MLP scope. |
| [E04 — Maintain Official Hotspot Data](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/4) | CLI import foundation and source labels implemented | Administrator import/list/update/removal workflows and retirement policy. |
| [E05 — Moderate Community Content](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/5) | Not implemented | Shared content flagging, moderation review, and removal. |
| [E06 — Report Availability & Assess Reliability](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/6) | Planned MLP; not implemented | Working/Unavailable reports, reliability/recency, rating/reliability sorting, and seating/accessibility tags (not yet decomposed into a Story). |
| [E07 — Follow Hotspots & Receive Updates](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/7) | Planned MLP; not implemented | Follow/unfollow, personal list, and notifications. |
| [E08 — Discussion Forum & Community Interaction](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/15) | Not implemented | Topic-based posts, comments/replies, and forum votes; separate from hotspot reviews. |

## User Story progress

“Implemented” means the specified demo behavior exists and has been checked. “Partial” means supporting code exists but the complete story or its acceptance verification remains outstanding. “Not implemented” does not imply that no planning or design work has been done.

### E01 — Discovery and profiles

| Story | Owner | Status and remaining work |
| --- | --- | --- |
| [US01 / #8 — Interactive map](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/8) | Boqing | Implemented. Official markers, matching preview/profile links, and distinct selection for records sharing coordinates. |
| [US02 / #9 — Location search](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/9) | Jiahao | Implemented (branch `jiahao-E01-US02-05`). Free-text `q` search over name, address/description, neighborhood, borough and ZIP; every word must match. Matching markers only, "X of Y hotspots match" count, and a separate no-match message. |
| [US03 / #10 — Borough/neighborhood filters](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/10) | Jiahao | Implemented (branch). `borough` and `neighborhood` (2010 NTA name, grouped by borough) filters; each can be selected, changed, or removed with its chip or "Clear all". |
| [US04 / #11 — Provider filter](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/11) | Jiahao | Implemented (branch). `provider` filter using the same select/change/remove behavior. |
| [US05 / #12 — Hotspot-type filter](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/12) | Jiahao | Implemented (branch) against the official `type` field (`access_type`: Free, Limited Free, Partner Site), labelled "Access type". Team to confirm whether a grouped `location_type` filter is also wanted. |
| [US31 / #41 — Profile and existing reviews](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/41) | Boqing | Implemented. Public official profile, hotspot-specific reviews, average/no-rating state, and explicit demo labels. |

E01 also integrates US12 / #22 from E03 and US18 / #28 from E04. Their original Epic parents and owners remain unchanged.

### E02 — Account access

Owner: Jiahao (Week 6). All five stories are implemented on branch `jiahao-E02-US06-10`, pending code review and merge.

| Story | Status and remaining work |
| --- | --- |
| [US06 / #16 — Sign up](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/16) | Implemented (branch). `/accounts/signup/` asks for username, email and password. Clear errors for invalid input, weak passwords, and usernames/emails that already exist (case-insensitive). New accounts join `Contributors` and are signed in. |
| [US07 / #17 — Log in](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/17) | Implemented (branch). `/accounts/login/` with a single generic error for wrong username, wrong password or inactive account. Header shows "Signed in as …" and a success message. |
| [US08 / #18 — Log out](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/18) | Implemented (branch). Header Log out button (POST) ends the session, returns to the map with a message, and contribution views redirect to login afterwards. |
| [US09 / #19 — Sign-in for contributions](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/19) | Implemented (branch) for the E02 side. Public pages stay anonymous. Profiles show a "Rate this hotspot" prompt that sends visitors to log in or sign up and returns them to `#contribute`. `contributor_required` gives any contribution view the same login-and-return behavior. Once E03 adds its form to `_contribute.html`, the sign-in-and-continue flow should be checked again. Report/flag actions belong to E05. |
| [US10 / #20 — Administrator access](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/20) | Implemented (branch). Visitor/contributor/administrator roles (superuser or `Administrators` group). `/manage/` and the Admin header link are administrator-only; contributors get 403 even by direct URL and cannot use Django admin. `set_administrator` command grants or revokes the role. E04/E05 tools should use `administrator_required`. |

### E03 — Hotspot ratings and reviews

| Story | Status and remaining work |
| --- | --- |
| [US11 / #21 — Rate/review a hotspot](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/21) | Implemented (code + automated tests). Signed-in contributors choose 1–5 stars and an optional review (max 2,000 characters) at `/hotspots/<id>/review/`; saved against the hotspot and the user. One review per user per hotspot (database constraint); a second attempt goes to edit. Visitors are redirected to log in. |
| [US12 / #22 — Average rating](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/22) | Read-side implemented; Jiahao retains ownership. Owner acceptance test added (branch): 1 and 3 → 2.0; add 5 → 3.0; edit 1 to 4 → 4.0; delete 5 → 3.5; unrated hotspot shows "No ratings yet" and a null API average. Contribution UI remains E03 work. |
| [US13 / #23 — Edit own rating/review](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/23) | Implemented (code + automated tests). Edit link only on the author's own entries; `/reviews/<id>/edit/` returns 404 for other users and for demo reviews. Averages update from the saved rating. |
| [US14 / #24 — Delete own rating/review](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/24) | Implemented (code + automated tests). Delete link only on own entries; a confirmation page precedes a POST-only delete; other users get 404; averages update. |
| [US15 / #25 — Helpful-review upvotes](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/25) | Implemented (code + automated tests, MLP). `ReviewVote` is unique per user and review; POST toggles add/remove; count shown on each written review; no downvotes; votes never affect star averages. Authors cannot upvote their own review (a choice not stated in the story; confirm with the team). |

### E04 — Official data

| Story | Status and remaining work |
| --- | --- |
| [US16 / #26 — Import/view official records](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/26) | Partial. Validated, atomic CLI upsert preserves stable IDs and review links. Administrator-triggered import and the restricted stored-record list are not implemented. |
| [US17 / #27 — Update/remove records](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/27) | Partial foundation. CLI reimport updates fields and public views exclude inactive records. No administrator edit/removal workflow; agree how retired hotspots retain reviews before implementing it. |
| [US18 / #28 — Official/community labels](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/28) | Implemented by Boqing and integrated into E01. Official fields, source dates, community feedback, and fictional demo contributions are visibly distinguished. |

### E05–E08 — Remaining community features

| Epic | Story | Status |
| --- | --- | --- |
| E05 | [US19 / #29 — Review content and flags](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/29) | Not implemented. |
| E05 | [US20 / #30 — Remove violations](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/30) | Not implemented. |
| E05 | [US21 / #31 — Flag inappropriate content](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/31) | Not implemented; shared by hotspot reviews and discussions. |
| E06 | [US22 / #32 — Report Working/Unavailable](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/32) | Planned MLP; not implemented. |
| E06 | [US23 / #33 — Reliability and report recency](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/33) | Planned MLP; not implemented. |
| E06 | [US24 / #34 — Sort by rating/reliability](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/34) | Planned MLP; not implemented. |
| E07 | [US25 / #35 — Follow/unfollow](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/35) | Planned MLP; not implemented. |
| E07 | [US26 / #36 — My followed hotspots](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/36) | Planned MLP; not implemented. |
| E07 | [US27 / #37 — Notifications](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/37) | Planned MLP; not implemented. |
| E08 | [US28 / #38 — Browse/create discussion topics](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/38) | Not implemented. |
| E08 | [US29 / #39 — Comments and replies](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/39) | Not implemented. |
| E08 | [US30 / #40 — Forum upvotes](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/40) | Not implemented; does not affect hotspot star ratings. |

## Support and planning

| Item | Current record |
| --- | --- |
| [#42 — Data, mapping and ERD](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/42) | Kavya and Suvan. Four deliverables are checked: sample/provenance, field mapping, identity/nullability/review links, and handoff instructions. The black-and-white ERD remains unchecked. |
| [#43 — Acceptance checks and demo verification](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/43) | Xiaoqi. The task remains open with its deliverables unchecked. Developer tests do not complete the full search/filter-to-profile QA workflow. |
| [#45 — Week 4 design and backlog goal](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/45) | Seven planning/design deliverables are checked. The sprint presentation/demo checkbox remains unchecked in the current issue. |
| [#13 — Previous requirements sprint goal](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/13) | Closed planning issue. |
| [#14 — Superseded E08 entry](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/14) | Closed duplicate; active E08 is #15. This is not evidence of an implemented forum. |

Closed test issue #44 is excluded from product completion progress.

## Next development steps

1. **Jiahao:** open the PR for `jiahao-E01-US02-05` and get review from Boqing. Confirm the US05 type mapping with the team.
2. **Jiahao and Boqing:** review the US12 (#22) acceptance test on the branch and move #9–#12 and #22 in ZenHub once merged.
3. **Kavya and Suvan:** finish the ERD in #42 and confirm the data handoff. The running demo currently uses 36 official sample records, not the full citywide dataset.
4. **Xiaoqi, with Boqing/Jiahao fixing defects:** complete #43 across the signed-out map → search/filter → profile → existing reviews/ratings journey.
5. **Boqing:** check the full E01 scope and required dependencies against the shared Definition of Done before marking the Epic complete.
6. **Subsequent feature work:** prioritize E02 identity flows and E03 review creation/edit/deletion. Continue E04 administration and E05 shared moderation under their existing stories. Keep E08 discussions separate; E06/E07 and helpful-review voting remain MLP.

CI/CD timing and AWS deployment remain to be confirmed against course requirements. Neither is configured in this demo.

## Development archive

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
