# Project progress

Last updated: **October 16, 2026**.

This document records implementation progress, remaining work, and development history for Connect NYC. GitHub and ZenHub remain the sources for requirements, assignments, and workflow status. Update this record as work progresses; preserve the dated archive below.

## Current milestone

The Django/MySQL foundation and Boqing's assigned E01 demo work are implemented: interactive map (US01), hotspot profiles with existing reviews (US31), and official/community source labels (US18, an E04 dependency). The profile section is titled **Hotspot Reviews**. The demo has been validated with 21 automated tests against MySQL and desktop/mobile browser checks.

**Full E01 is still in progress.** Search and filters, the remaining data-design deliverable, and full-journey acceptance checks are outstanding. Existing review display does not mean review creation, editing, or deletion has been implemented.

Implementation statuses below describe the code, not automatic issue closure. At this snapshot, all eight active Epic issues and all 31 User Story issues are open. US01, US31, and US18 were moved to In Progress in ZenHub. Work is published on `boqing-E01-US01/31/18` through [PR #47](https://github.com/gcivil-nyu-org/team2-mon-fall26/pull/47), which records review and merge state.

## Epic overview

| Epic | Implementation status | Remaining scope |
| --- | --- | --- |
| [E01 — Finding a Wi-Fi Hotspot](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/1) | Partially implemented | Location search, filters, rating integration verification, ERD, and complete acceptance checks. |
| [E02 — Account Registration & Access](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/2) | Framework foundation only | Product sign-up, login/logout, contribution sign-in flow, and administrator access workflow. |
| [E03 — Rate & Review Hotspots](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/3) | Review model and rating read-side implemented | Create/edit/delete own contributions; owner verification of US12; helpful-review votes remain MLP. |
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
| [US02 / #9 — Location search](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/9) | Jiahao | Not implemented. Add the existing location/address/landmark search requirements and result feedback. |
| [US03 / #10 — Borough/neighborhood filters](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/10) | Jiahao | Not implemented. Connect filters to official borough and NTA fields. |
| [US04 / #11 — Provider filter](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/11) | Jiahao | Not implemented. Add provider filtering and filter change/removal behavior. |
| [US05 / #12 — Hotspot-type filter](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/12) | Jiahao | Not implemented. Apply the agreed access-type/location-type mapping. |
| [US31 / #41 — Profile and existing reviews](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/41) | Boqing | Implemented. Public official profile, hotspot-specific reviews, average/no-rating state, and explicit demo labels. |

E01 also integrates US12 / #22 from E03 and US18 / #28 from E04. Their original Epic parents and owners remain unchanged.

### E02 — Account access

| Story | Status and remaining work |
| --- | --- |
| [US06 / #16 — Sign up](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/16) | Not implemented. Django's user model is available; public registration is absent. |
| [US07 / #17 — Log in](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/17) | Not implemented as a product workflow. |
| [US08 / #18 — Log out](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/18) | Not implemented as a product workflow. |
| [US09 / #19 — Sign-in for contributions](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/19) | Partial foundation. Map/profile/review reading is anonymous; contribution authentication and return-to-action behavior are absent. |
| [US10 / #20 — Administrator access](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/20) | Framework foundation only. Django admin/auth is installed; the project's administrator workflow is not delivered. |

### E03 — Hotspot ratings and reviews

| Story | Status and remaining work |
| --- | --- |
| [US11 / #21 — Rate/review a hotspot](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/21) | Partial foundation. Review model, author/hotspot links, optional body, and 1–5 rating constraint exist. No submission interface. |
| [US12 / #22 — Average rating](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/22) | Read-side implemented; Jiahao retains ownership. Average/count/no-rating behavior includes rating-only records. Complete owner acceptance checks for stored rating additions, edits, and deletions. Contribution UI is not required for that verification. |
| [US13 / #23 — Edit own rating/review](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/23) | Not implemented. Add authenticated ownership enforcement and editing. |
| [US14 / #24 — Delete own rating/review](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/24) | Not implemented. Add authenticated ownership enforcement and deletion confirmation. |
| [US15 / #25 — Helpful-review upvotes](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/25) | Planned MLP; not implemented. Votes must remain separate from star ratings. |

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

1. **Jiahao:** implement and integrate US02–US05 (#9–#12) with the current map, active-hotspot queryset, and profile links. Check changed/removed filters and no-match cases against the existing story criteria.
2. **Jiahao and Boqing:** finish US12 (#22) integration verification using stored rating additions, edits, and deletions; keep rating-only entries and no-rating behavior correct.
3. **Kavya and Suvan:** finish the ERD in #42 and confirm the data handoff. The running demo currently uses 36 official sample records, not the full citywide dataset.
4. **Xiaoqi, with Boqing/Jiahao fixing defects:** complete #43 across the signed-out map → search/filter → profile → existing reviews/ratings journey.
5. **Boqing:** check the full E01 scope and required dependencies against the shared Definition of Done before marking the Epic complete.
6. **Subsequent feature work:** prioritize E02 identity flows and E03 review creation/edit/deletion. Continue E04 administration and E05 shared moderation under their existing stories. Keep E08 discussions separate; E06/E07 and helpful-review voting remain MLP.

CI/CD timing and AWS deployment remain to be confirmed against course requirements. Neither is configured in this demo.

## Development archive

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
