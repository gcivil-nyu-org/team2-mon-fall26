# Connect NYC

Connect NYC is an English-language web application that helps New York City residents, students, and visitors discover public Wi-Fi hotspots. It brings official NYC location information and clearly labeled community feedback together so people can compare places to connect before they visit.

## Project description

The core user journey is to browse a map, search or filter locations, and open a hotspot profile to see its provider, access information, ratings, and reviews. Public browsing does not require an account. The planned contribution features let signed-in users share hotspot reviews, while a separate discussion area supports Wi-Fi questions and conversations. Availability reporting, reliability indicators, and following hotspots are planned extensions.

The application uses **Python 3.13, Django 5.2, and MySQL 8.4**. The frontend is built with Django templates, HTML, CSS, and JavaScript; Leaflet and OpenStreetMap provide the map. The current local demo runs as one web application and one database through Docker Compose.

For current implementation status, remaining work, and dated development history, see [docs/PROGRESS.md](docs/PROGRESS.md). Contributors and coding agents should also read [agents.md](agents.md).

## Implemented demo

The current E01 demo includes Boqing's map/profile stories and the shared E04 source-label story:

| Story | Demo behavior |
| --- | --- |
| [US01 / #8](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/8) | Browse official hotspots on an interactive map, select a marker, and see the corresponding location/provider information. |
| [US31 / #41](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/41) | Open the selected hotspot's public profile and read its existing ratings and reviews. |
| [US18 / #28](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/28) | See clearly separated, labeled official data and community feedback. |
| [US02–US05 / #9–#12](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/9) | Search by location, address or landmark, and filter by borough/neighborhood, provider and access type. Filters combine, can be removed one at a time, and show a message when nothing matches. |
| [US06–US10 / #16–#20](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/2) (E02, branch `jiahao-E02-US06-10`) | Sign up, log in and log out. Visitors keep public browsing and are asked to sign in only to contribute, then returned to the hotspot they started from. Administrators get an admin-only area that contributors and visitors cannot open, even by direct URL. |

The profile includes a small rating aggregation service for its dependency on US12 / #22 under E03; that story remains owned by Jiahao. US18 / #28 retains its E04 parent and is integrated into the E01 interface. Contribution forms (E03), availability reporting, reliability scores, and notifications are not yet implemented. The full E01 Epic remains in progress.

## Run the demo

Prerequisites: Docker Desktop running and Python 3 available on the host. MySQL runs in its own container and does not use an existing host database.

```sh
python3 scripts/create_env.py
docker compose up --build --wait
docker compose exec web python manage.py import_hotspots
docker compose exec web python manage.py seed_demo_reviews
```

Open **http://localhost:8000**. The environment script generates local secrets in an ignored `.env` file and never overwrites an existing file. The first start downloads images and builds dependencies. The command waits for both MySQL and the web page to be ready before returning; check `docker compose logs web` if startup fails. Migrations and static asset collection run at startup.

Suggested walkthrough:

1. Select a map marker or use **Choose a hotspot**. The adjacent panel changes to the same hotspot.
2. Open **View hotspot profile** and compare its official information with **Hotspot Reviews**.
3. Visit [Bryant Park](http://localhost:8000/hotspots/1344/) for three explicitly fictional demo ratings (average 4.0) and two written demo reviews.
4. Visit [Union Square](http://localhost:8000/hotspots/1343/) for the empty-rating/review state.

All viewing works without signing in. A profile directory remains available without JavaScript. Hotspots sharing coordinates remain distinct records and can be selected from the map popup or the chooser. If external map tiles cannot load, profile access and official data remain available.

```sh
# Rebuild after editing source files; the default demo does not bind-mount code.
docker compose up --build --wait

# Stop the demo while preserving the MySQL volume.
docker compose down
```

For development, `compose.dev.yaml` mounts your checkout into the container and runs Django's auto-reloading development server with `DJANGO_DEBUG=1`, so code, template and static-file changes show up without rebuilding. Use it only on your own machine:

```sh
docker compose -f compose.yaml -f compose.dev.yaml up --build --wait
```

## Data and provenance

The existing team sample, `data/connectnyc_hotspots_sample.csv`, contains **36 official records across four boroughs**. It was acquired on October 14, 2026 from [NYC Wi-Fi Hotspot Locations](https://data.cityofnewyork.us/City-Government/NYC-Wi-Fi-Hotspot-Locations/yjub-udmw); the source snapshot was last updated on September 26, 2019. The sample is not the complete citywide dataset and does not indicate live connectivity.

The importer follows the team's [E01 data and field mapping](https://github.com/gcivil-nyu-org/team2-mon-fall26/wiki/E01-Data-and-Field-Mapping):

- `doitt_id` is the stable hotspot primary key. Matching coordinates do not imply duplicate records.
- Imports validate all rows before an atomic upsert. Re-importing updates official fields without replacing hotspots, removing absent rows, changing active status, or breaking review relationships.
- Borough comes from `boroname`; neighborhood comes from the 2010 NTA fields. `type` is access type, while `location_t` is the physical location type.
- Missing names receive a display fallback. Blank/zero source references and the `9999-09-09` activation sentinel become null.

To import another compatible CSV, first copy it into the container:

```sh
docker compose cp /absolute/path/hotspots.csv web:/tmp/hotspots.csv
docker compose exec web python manage.py import_hotspots /tmp/hotspots.csv --source-date 2026-10-16
```

`seed_demo_reviews` is optional and idempotent. It requires `DEMO_MODE=1`, creates inactive demonstration accounts with unusable passwords, and flags every sample contribution as fictional. Set `DEMO_MODE=0` and recreate the web service to hide those contributions from both pages and the JSON endpoint. The official CSV is never modified by seeding.

## Development and validation

```sh
# Run the suite against MySQL, including database constraints and importer behavior.
sh scripts/test.sh

docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
```

The test helper grants the application user access only to its `test_<database>` schema inside the local Compose MySQL container, then runs Django's test runner. It does not expose the database port or pass root credentials to the web service. The test database is separate from the demo database.

To generate new migrations and save them to the checkout:

```sh
docker compose run --rm --volume "$PWD:/app" web python manage.py makemigrations
docker compose up --build --wait
```

Tests cover stable imports and review relationships, invalid-file rollback, shared coordinates, missing-source normalization, public read routes, hotspot-specific ratings/reviews, rating-only submissions, demo isolation, escaped review content, and database rating bounds.

## Project structure and integration points

```text
config/             Django settings, URL routing, WSGI/ASGI entry points
hotspots/           Official location model, importer, public views and map API
  templates/        English map and profile pages
  static/hotspots/  Responsive styles and map selection logic
reviews/            Review model, shared rating summary and demo seed command
accounts/           E02 sign-up/login/logout, roles, shared access checks, admin area
templates/          Project-wide templates (403 page)
data/               Team-provided official CSV sample and data verification script
scripts/            Local environment generation and MySQL test helper
docs/PROGRESS.md     Epic/story status, next steps, and dated development archive
agents.md            Instructions for maintaining the project progress record
```

`Hotspot` owns official fields. `Review` links to a hotspot and Django's user model; rating-only entries have an empty body and still count toward the average. `reviews.services` provides the read-side summary. Reviews are escaped in templates and map labels are inserted as text.

Public routes:

| Route | Purpose |
| --- | --- |
| `/` | Interactive map and selected hotspot preview |
| `/hotspots/<doitt_id>/` | Official profile and that hotspot's community feedback |
| `/api/hotspots/` | Active hotspot records, profile URLs, and rating summaries as JSON |
| `/accounts/signup/`, `/accounts/login/` | Account registration and login (both accept a safe `?next=` return path) |
| `/accounts/logout/` | Log out (POST only, from the header button) |
| `/manage/` | Administrator-only area; visitors are sent to log in, contributors get 403 |

`/` and `/api/hotspots/` accept the same optional query parameters: `q` (location search), `borough`, `neighborhood`, `provider` and `type` (official access type). For example, `/api/hotspots/?q=library&borough=Brooklyn`.

Jiahao can extend the active-hotspot queryset and map interface for search/filter stories. The data team can continue supplying compatible CSVs and refining the ERD without changing hotspot IDs. New review-writing workflows should reuse the `Review` model and shared summary service.

## Accounts and roles (E02)

Accounts use Django's built-in user model and session login. Passwords are stored only as salted PBKDF2-SHA256 hashes, and the existing password validators apply at sign-up. Usernames and emails are unique regardless of letter case.

| Role | Who | Can |
| --- | --- | --- |
| Visitor | Not signed in | Browse the map, search, filter and read reviews |
| Contributor | Any active account; sign-ups join the `Contributors` group | Contribution features (E03 and later) |
| Administrator | Superusers and members of the `Administrators` group | Everything above, plus `/manage/` and Django admin |

Create the first administrator with `python manage.py createsuperuser`, or promote an existing account with `python manage.py set_administrator <username>` (use `--revoke` to undo). In Docker, prefix these with `docker compose exec web`.

New views should enforce roles with the shared helpers in `accounts/permissions.py` rather than ad hoc checks:

```python
from accounts.permissions import administrator_required, contributor_required

@contributor_required        # E03 review create/edit/delete: visitors go to login and come back
def create_review(request, pk): ...

@administrator_required      # E04/E05 admin tools: contributors get 403, even by direct URL
def import_records(request): ...
```

Class-based views can use `ContributorRequiredMixin` and `AdministratorRequiredMixin`. Templates receive `user_role` (`visitor`, `contributor` or `administrator`) and `user_is_administrator`. The hotspot profile's contribution prompt lives in `hotspots/templates/hotspots/_contribute.html`; E03 / US11 replaces its signed-in branch with the review form.

Behind an HTTPS load balancer, set `DJANGO_CSRF_TRUSTED_ORIGINS` to the public `https://` origin and `DJANGO_BEHIND_HTTPS_PROXY=1`, together with `DJANGO_SECURE_COOKIES=1`, so sign-up and login forms pass CSRF checks over HTTPS.

## Runtime notes

The local demo runs one Django web service with Gunicorn/WhiteNoise and one MySQL service. Leaflet 1.9.4 is vendored with its license; map tiles come from OpenStreetMap with visible attribution. Internet access is needed for the map background, not for the stored hotspot records.

AWS deployment and CI/CD are not configured yet. A later AWS deployment needs an HTTPS endpoint, correct allowed hosts, secure cookies, managed secrets, a persistent MySQL database, and deployment-specific security review. Keep `DJANGO_DEBUG=0` and `DEMO_MODE=0` outside a clearly identified demo environment.
