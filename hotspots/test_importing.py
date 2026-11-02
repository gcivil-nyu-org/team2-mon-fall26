import csv
from datetime import date
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from reviews.models import Review, ReviewVote

from .importing import HotspotImportError, import_hotspots
from .models import Hotspot


class SharedHotspotImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with (settings.BASE_DIR / "data" / "connectnyc_hotspots_sample.csv").open(newline="") as source:
            cls.row = next(csv.DictReader(source))

    def csv_source(self, rows):
        source = StringIO()
        writer = csv.DictWriter(source, fieldnames=self.row.keys())
        writer.writeheader()
        writer.writerows(rows)
        source.seek(0)
        return source

    def test_result_counts_and_reimport_preserve_retirement_reviews_and_votes(self):
        acquired = date(2026, 10, 14)
        result = import_hotspots(self.csv_source([self.row]), acquired)
        self.assertEqual(result, {"total": 1, "created": 1, "updated": 0})
        hotspot = Hotspot.objects.get()
        user = get_user_model().objects.create_user(username="review-author")
        voter = get_user_model().objects.create_user(username="review-voter")
        review = Review.objects.create(hotspot=hotspot, author=user, rating=5, body="Useful.")
        vote = ReviewVote.objects.create(review=review, user=voter)
        hotspot.is_active = False
        hotspot.save(update_fields=["is_active"])

        changed = dict(self.row, name="Updated official record")
        result = import_hotspots(self.csv_source([changed]), date(2026, 10, 26))

        self.assertEqual(result, {"total": 1, "created": 0, "updated": 1})
        self.assertEqual(Hotspot.objects.count(), 1)
        hotspot.refresh_from_db()
        self.assertEqual(hotspot.name, "Updated official record")
        self.assertEqual(hotspot.source_acquired_on, date(2026, 10, 26))
        self.assertFalse(hotspot.is_active)
        self.assertTrue(Review.objects.filter(pk=review.pk, hotspot=hotspot, body="Useful.").exists())
        self.assertTrue(ReviewVote.objects.filter(pk=vote.pk, review=review).exists())

    def test_extra_or_missing_row_values_reject_the_file(self):
        for values in [list(self.row.values()) + ["extra"], list(self.row.values())[:-1]]:
            with self.subTest(values=len(values)):
                source = self.csv_source([self.row])
                source.seek(0, 2)
                csv.writer(source).writerow(values)
                source.seek(0)
                with self.assertRaisesMessage(HotspotImportError, "number of values"):
                    import_hotspots(source, date(2026, 10, 14))
                self.assertFalse(Hotspot.objects.exists())

    def test_duplicate_column_names_reject_the_file(self):
        source = StringIO()
        writer = csv.writer(source)
        writer.writerow([*self.row.keys(), "name"])
        writer.writerow([*self.row.values(), "Ambiguous name"])
        source.seek(0)
        with self.assertRaisesMessage(HotspotImportError, "Duplicate CSV column"):
            import_hotspots(source, date(2026, 10, 14))
        self.assertFalse(Hotspot.objects.exists())

    def test_unclosed_quoted_row_rejects_the_file(self):
        source = self.csv_source([self.row])
        source.seek(0, 2)
        source.write('"Unclosed CSV field')
        source.seek(0)
        with self.assertRaisesMessage(HotspotImportError, "Unable to read CSV"):
            import_hotspots(source, date(2026, 10, 14))
        self.assertFalse(Hotspot.objects.exists())
