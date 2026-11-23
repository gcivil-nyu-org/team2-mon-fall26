from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from hotspots.importing import HotspotImportError, import_hotspots
from hotspots.models import Hotspot


class Command(BaseCommand):
    help = "Validate and upsert official hotspot CSV rows without deleting existing hotspots or reviews."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Initialize an empty catalog and preserve existing records on startup.",
        )
        parser.add_argument(
            "path",
            nargs="?",
            default=str(settings.BASE_DIR / "data" / "connectnyc_hotspots_sample.csv"),
        )
        parser.add_argument(
            "--source-date",
            default="2026-10-14",
            help="Acquisition date (YYYY-MM-DD); the bundled sample was acquired on 2026-10-14.",
        )

    def handle(self, *args, **options):
        if options["if_empty"] and Hotspot.objects.exists():
            self.stdout.write("Hotspot catalog already initialized. Skipped import.")
            return
        try:
            source_date = date.fromisoformat(options["source_date"])
        except ValueError as exc:
            raise CommandError(
                "--source-date must be a valid YYYY-MM-DD date."
            ) from exc

        try:
            with Path(options["path"]).open(encoding="utf-8-sig", newline="") as source:
                result = import_hotspots(
                    source, source_date, create_only=options["if_empty"]
                )
        except HotspotImportError as exc:
            raise CommandError(str(exc)) from exc
        except OSError as exc:
            raise CommandError(f"Unable to read CSV: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {result['total']} official hotspots: {result['created']} created, "
                f"{result['updated']} updated. No records were removed."
            )
        )
