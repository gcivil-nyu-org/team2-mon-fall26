"""Validated, atomic imports shared by the CLI and administrator upload form."""
import csv
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Hotspot


REQUIRED_COLUMNS = {
    "doitt_id", "objectid", "name", "location", "latitude", "longitude",
    "boroname", "ntaname", "ntacode", "zip", "provider", "type",
    "location_t", "ssid", "remarks", "sourceid", "activated",
}
BOROUGHS = {"Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"}


class HotspotImportError(ValueError):
    """An invalid CSV is rejected without changing stored records."""


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


def import_hotspots(source, source_date):
    """Import a decoded CSV stream, preserving retired records and review links.

    Validate the entire file before writing. Existing IDs are updated in place;
    absent rows are retained and an import never reactivates a retired hotspot.
    """
    records = []
    identifiers = set()
    try:
        reader = csv.DictReader(source, strict=True)
        columns = reader.fieldnames or []
        missing = REQUIRED_COLUMNS.difference(columns)
        if missing:
            raise HotspotImportError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        if len(columns) != len(set(columns)):
            raise HotspotImportError("Duplicate CSV column names are not allowed.")
        for row in reader:
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("The number of values does not match the CSV header.")
                hotspot = _record(row, source_date)
                if hotspot.pk in identifiers:
                    raise ValueError(f"Duplicate doitt_id {hotspot.pk} in the file.")
            except (ValueError, InvalidOperation, ValidationError) as exc:
                raise HotspotImportError(f"Invalid row {reader.line_num}: {exc}") from exc
            identifiers.add(hotspot.pk)
            records.append(hotspot)
    except (OSError, csv.Error, UnicodeError) as exc:
        raise HotspotImportError(f"Unable to read CSV: {exc}") from exc
    if not records:
        raise HotspotImportError("The CSV has no hotspot rows; nothing was changed.")

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
    return {
        "total": len(records),
        "created": created_count,
        "updated": len(records) - created_count,
    }
