# Connect NYC

Find public Wi-Fi locations in New York City and distinguish official location data from community feedback. This English-language demo uses **Python 3.13, Django 5.2, and MySQL 8.4**, with server-rendered templates and Leaflet maps.

## Current scope

This branch implements the E01 stories assigned to Boqing (`jay-den-21`):

| Story | Demo behavior |
| --- | --- |
| [US01 / #8](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/8) | Browse official hotspots on an interactive map, select a marker, and see the corresponding location/provider information. |
| [US31 / #41](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/41) | Open the selected hotspot's public profile and read its existing ratings and reviews. |
| [US18 / #28](https://github.com/gcivil-nyu-org/team2-mon-fall26/issues/28) | See clearly separated, labeled official data and community feedback. |

The profile includes a small rating aggregation service for its dependency on US16 / #22; that story remains owned by Jiahao. Search and filters (#9–#12), contribution forms, authentication flows, availability reporting, reliability scores, and notifications are outside this implementation.

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
2. Open **View hotspot profile** and compare its official information with the community section.
3. Visit [Bryant Park](http://localhost:8000/hotspots/1344/) for three explicitly fictional demo ratings (average 4.0) and two written demo reviews.
4. Visit [Union Square](http://localhost:8000/hotspots/1343/) for the empty-rating/review state.

All viewing works without signing in. A profile directory remains available without JavaScript. Hotspots sharing coordinates remain distinct records and can be selected from the map popup or the chooser. If external map tiles cannot load, profile access and official data remain available.

```sh
# Rebuild after editing source files; the default demo does not bind-mount code.
docker compose up --build --wait

# Stop the demo while preserving the MySQL volume.
docker compose down
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
data/               Team-provided official CSV sample and data verification script
scripts/            Local environment generation and MySQL test helper
```

`Hotspot` owns official fields. `Review` links to a hotspot and Django's user model; rating-only entries have an empty body and still count toward the average. `reviews.services` provides the read-side summary. Reviews are escaped in templates and map labels are inserted as text.

Public routes:

| Route | Purpose |
| --- | --- |
| `/` | Interactive map and selected hotspot preview |
| `/hotspots/<doitt_id>/` | Official profile and that hotspot's community feedback |
| `/api/hotspots/` | Active hotspot records, profile URLs, and rating summaries as JSON |

Jiahao can extend the active-hotspot queryset and map interface for search/filter stories. The data team can continue supplying compatible CSVs and refining the ERD without changing hotspot IDs. New review-writing workflows should reuse the `Review` model and shared summary service.

## Runtime notes

The local demo runs one Django web service with Gunicorn/WhiteNoise and one MySQL service. Leaflet 1.9.4 is vendored with its license; map tiles come from OpenStreetMap with visible attribution. Internet access is needed for the map background, not for the stored hotspot records.

This change does not deploy to AWS or set up CI/CD. A later AWS deployment needs an HTTPS endpoint, correct allowed hosts, secure cookies, managed secrets, a persistent MySQL database, and deployment-specific security review. Keep `DJANGO_DEBUG=0` and `DEMO_MODE=0` outside a clearly identified demo environment.
