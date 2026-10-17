import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hotspots.models import Hotspot


REQUIRED_COLUMNS = {
    "doitt_id", "objectid", "name", "location", "latitude", "longitude",
    "boroname", "ntaname", "ntacode", "zip", "provider", "type",
    "location_t", "ssid", "remarks", "sourceid", "activated",
}
BOROUGHS = {"Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"}


def _record(row, source_date):
    def value(column):
        return (row.get(column) or "").strip()

    latitude = Decimal(value("latitude"))
    longitude = Decimal(value("longitude"))
    if not latitude.is_finite() or not longitude.is_finite():
        raise ValueError("Coordinates must be finite numbers.")
    if value("boroname") not in BOROUGHS:
        raise ValueError("Unknown borough name.")
    activated = value("activated")
    activated_on = (
        date.fromisoformat(activated[:10])
        if activated and not activated.startswith("9999-09-09")
        else None
    )
    hotspot = Hotspot(
        hotspot_id=int(value("doitt_id")),
        source_object_id=int(value("objectid")),
        name=value("name") or None,
        location_description=value("location"),
        latitude=latitude,
        longitude=longitude,
        borough=value("boroname"),
        neighborhood_name=value("ntaname"),
        neighborhood_code=value("ntacode"),
        zip_code=value("zip"),
        provider=value("provider"),
        access_type=value("type"),
        location_type=value("location_t"),
        ssid=value("ssid"),
        remarks=value("remarks"),
        source_ref=None if value("sourceid") in {"", "0"} else value("sourceid"),
        activated_on=activated_on,
        source_acquired_on=source_date,
    )
    hotspot.full_clean(validate_unique=False, validate_constraints=False)
    return hotspot


class Command(BaseCommand):
    help = "Validate and upsert official hotspot CSV rows without deleting existing hotspots or reviews."

    def add_arguments(self, parser):
        parser.add_argument(
            "path", nargs="?",
            default=str(settings.BASE_DIR / "data" / "connectnyc_hotspots_sample.csv"),
        )
        parser.add_argument(
            "--source-date", default="2026-10-14",
            help="Acquisition date (YYYY-MM-DD); the bundled sample was acquired on 2026-10-14.",
        )

    def handle(self, *args, **options):
        try:
            source_date = date.fromisoformat(options["source_date"])
        except ValueError as exc:
            raise CommandError("--source-date must be a valid YYYY-MM-DD date.") from exc

        records = []
        identifiers = set()
        try:
            with Path(options["path"]).open(encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source, strict=True)
                missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
                if missing:
                    raise CommandError(f"Missing CSV columns: {', '.join(sorted(missing))}")
                for line_number, row in enumerate(reader, start=2):
                    try:
                        hotspot = _record(row, source_date)
                        if hotspot.pk in identifiers:
                            raise ValueError(f"Duplicate doitt_id {hotspot.pk} in the file.")
                    except (ValueError, InvalidOperation, ValidationError) as exc:
                        raise CommandError(f"Invalid row {line_number}: {exc}") from exc
                    identifiers.add(hotspot.pk)
                    records.append(hotspot)
        except (OSError, csv.Error, UnicodeError) as exc:
            raise CommandError(f"Unable to read CSV: {exc}") from exc
        if not records:
            raise CommandError("The CSV has no hotspot rows; nothing was changed.")

        created_count = 0
        with transaction.atomic():
            for hotspot in records:
                defaults = {
                    field.name: getattr(hotspot, field.name)
                    for field in Hotspot._meta.concrete_fields
                    if not field.primary_key and field.name != "is_active"
                }
                _, created = Hotspot.objects.update_or_create(
                    hotspot_id=hotspot.pk, defaults=defaults
                )
                created_count += created
        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(records)} official hotspots: {created_count} created, "
            f"{len(records) - created_count} updated. No records were removed."
        ))
