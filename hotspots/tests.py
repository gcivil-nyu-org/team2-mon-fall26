import csv
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from reviews.models import Review

from .models import Hotspot


def make_hotspot(hotspot_id=1344, **overrides):
    fields = {
        "source_object_id": hotspot_id + 10000,
        "name": "Bryant Park",
        "location_description": "Entire park",
        "latitude": Decimal("40.7536"),
        "longitude": Decimal("-73.9832"),
        "borough": "Manhattan",
        "neighborhood_name": "Midtown",
        "provider": "Partner",
        "access_type": "Partner Site",
        "location_type": "Outdoor",
        "ssid": "Park Wi-Fi",
        "source_acquired_on": date(2026, 10, 14),
    }
    fields.update(overrides)
    return Hotspot.objects.create(hotspot_id=hotspot_id, **fields)


class ImportHotspotsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with (settings.BASE_DIR / "data" / "connectnyc_hotspots_sample.csv").open(newline="") as source:
            cls.sample_rows = list(csv.DictReader(source))

    def import_rows(self, rows, **options):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "hotspots.csv"
            with path.open("w", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=self.sample_rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            call_command("import_hotspots", str(path), stdout=StringIO(), **options)

    def test_bundled_sample_preserves_all_official_records_and_shared_coordinates(self):
        call_command("import_hotspots", stdout=StringIO())
        self.assertEqual(Hotspot.objects.count(), 36)
        first = Hotspot.objects.get(pk=999)
        second = Hotspot.objects.get(pk=1000)
        self.assertEqual((first.latitude, first.longitude), (second.latitude, second.longitude))
        self.assertNotEqual(first.pk, second.pk)

    def test_missing_name_and_source_sentinels_are_normalized(self):
        rows = [dict(self.sample_rows[0]), dict(self.sample_rows[3])]
        self.import_rows(rows)
        sentinel = Hotspot.objects.get(pk=int(rows[0]["doitt_id"]))
        missing_name = Hotspot.objects.get(pk=int(rows[1]["doitt_id"]))
        self.assertIsNone(sentinel.source_ref)
        self.assertIsNone(sentinel.activated_on)
        self.assertIsNone(missing_name.name)
        self.assertEqual(missing_name.display_name, "Downtown Brooklyn — 125 Court St.")
        self.assertEqual(missing_name.zip_code, "11201")
        zero_name = dict(rows[0], name="0", doitt_id="987654")
        self.import_rows([zero_name])
        hotspot = Hotspot.objects.get(pk=987654)
        self.assertEqual(hotspot.name, "0")
        self.assertEqual(hotspot.display_name, f"{hotspot.provider} — {hotspot.location_description}")

    def test_real_source_reference_and_activation_date_are_preserved(self):
        row = dict(self.sample_rows[0], sourceid="site-123", activated="2018-03-12T00:00:00.000")
        self.import_rows([row], source_date="2026-10-16")
        hotspot = Hotspot.objects.get()
        self.assertEqual(hotspot.source_ref, "site-123")
        self.assertEqual(hotspot.activated_on, date(2018, 3, 12))
        self.assertEqual(hotspot.source_acquired_on, date(2026, 10, 16))

    def test_reimport_updates_same_id_and_preserves_reviews_and_other_rows(self):
        row = dict(self.sample_rows[0])
        self.import_rows([row])
        hotspot = Hotspot.objects.get()
        author = get_user_model().objects.create_user(username="reviewer")
        review = Review.objects.create(hotspot=hotspot, author=author, rating=4, body="Helpful.")
        other = make_hotspot()
        hotspot.is_active = False
        hotspot.save(update_fields=["is_active"])
        row["name"] = "Updated official name"
        self.import_rows([row])
        self.import_rows([row])
        hotspot.refresh_from_db()
        review.refresh_from_db()
        self.assertEqual(Hotspot.objects.count(), 2)
        self.assertEqual(hotspot.name, "Updated official name")
        self.assertEqual(review.hotspot_id, hotspot.pk)
        self.assertEqual(review.body, "Helpful.")
        self.assertFalse(hotspot.is_active)
        self.assertTrue(Hotspot.objects.filter(pk=other.pk).exists())

    def test_invalid_later_row_leaves_database_unchanged(self):
        self.import_rows([self.sample_rows[0]])
        original = Hotspot.objects.get()
        changed = dict(self.sample_rows[0], name="Should not be saved")
        invalid = dict(self.sample_rows[1], latitude="91")
        with self.assertRaisesMessage(CommandError, "Invalid row 3"):
            self.import_rows([changed, invalid])
        original.refresh_from_db()
        self.assertEqual(original.name, self.sample_rows[0]["name"])
        self.assertEqual(Hotspot.objects.count(), 1)

    def test_duplicate_primary_ids_reject_entire_file(self):
        with self.assertRaisesMessage(CommandError, "Duplicate doitt_id"):
            self.import_rows([self.sample_rows[0], self.sample_rows[0]])
        self.assertFalse(Hotspot.objects.exists())

    def test_nonfinite_coordinates_are_rejected(self):
        for coordinate in ["NaN", "Infinity", "not a number"]:
            with self.subTest(coordinate=coordinate), self.assertRaises(CommandError):
                self.import_rows([dict(self.sample_rows[0], longitude=coordinate)])
        self.assertFalse(Hotspot.objects.exists())

    def test_missing_columns_and_empty_files_do_not_change_data(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("doitt_id,name\n1,Park\n")
            with self.assertRaisesMessage(CommandError, "Missing CSV columns"):
                call_command("import_hotspots", str(path), stdout=StringIO())
        with self.assertRaisesMessage(CommandError, "no hotspot rows"):
            self.import_rows([])
        self.assertFalse(Hotspot.objects.exists())


@override_settings(DEMO_MODE=False)
class HotspotReadExperienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hotspot = make_hotspot()
        cls.other = make_hotspot(53, name="Clinton Hill Library", borough="Brooklyn", provider="BPL")
        cls.inactive = make_hotspot(10, name="Inactive record", is_active=False)
        cls.author = get_user_model().objects.create_user(username="alex")

    def test_anonymous_map_renders_active_markers_and_source(self):
        response = self.client.get(reverse("hotspots:map"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["hotspot_count"], 2)
        self.assertEqual(response.context["borough_count"], 2)
        self.assertEqual(response.context["provider_count"], 2)
        self.assertEqual({item["id"] for item in response.context["map_data"]}, {1344, 53})
        self.assertContains(response, self.hotspot.source_url)

    def test_anonymous_profile_separates_sources_and_no_ratings(self):
        response = self.client.get(self.hotspot.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Official data")
        self.assertContains(response, "Community feedback")
        self.assertContains(response, "No ratings yet")
        self.assertContains(response, self.hotspot.source_url)
        self.assertIsNone(response.context["rating_summary"]["average"])
        self.assertEqual(response.context["rating_summary"]["count"], 0)

    def test_profile_includes_rating_only_entries_and_excludes_other_hotspots(self):
        for rating, body in [(2, "First visit"), (5, ""), (5, "Another visit")]:
            Review.objects.create(hotspot=self.hotspot, author=self.author, rating=rating, body=body)
        Review.objects.create(hotspot=self.other, author=self.author, rating=1, body="Another location")
        response = self.client.get(self.hotspot.get_absolute_url())
        self.assertEqual(response.context["rating_summary"], {
            "average": 4.0, "count": 3, "review_count": 2, "has_demo_reviews": False,
        })
        self.assertEqual(len(response.context["reviews"]), 2)
        self.assertNotContains(response, "Another location")

    def test_review_html_is_escaped(self):
        Review.objects.create(
            hotspot=self.hotspot, author=self.author, rating=4,
            body='<script>alert("unsafe")</script>',
        )
        response = self.client.get(self.hotspot.get_absolute_url())
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("unsafe")</script>')

    def test_inactive_and_missing_hotspots_return_404(self):
        for pk in [self.inactive.pk, 999999]:
            with self.subTest(pk=pk):
                self.assertEqual(self.client.get(reverse("hotspots:detail", args=[pk])).status_code, 404)

    def test_read_routes_reject_post_without_creating_contributions(self):
        for url in [reverse("hotspots:map"), self.hotspot.get_absolute_url(), reverse("hotspots:data")]:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {"rating": 5, "body": "new"}).status_code, 405)
        self.assertFalse(Review.objects.exists())

    def test_api_returns_current_hotspot_rating_and_official_metadata(self):
        Review.objects.create(hotspot=self.hotspot, author=self.author, rating=4, body="")
        payload = self.client.get(reverse("hotspots:data")).json()
        self.assertEqual(payload["count"], 2)
        record = next(item for item in payload["hotspots"] if item["id"] == self.hotspot.pk)
        self.assertEqual(record["average_rating"], 4.0)
        self.assertEqual(record["rating_count"], 1)
        self.assertEqual(record["review_count"], 0)
        self.assertEqual(record["profile_url"], self.hotspot.get_absolute_url())
        self.assertEqual(record["source_acquired_on"], "2026-10-14")

    def test_demo_feedback_is_hidden_outside_demo_mode(self):
        Review.objects.create(hotspot=self.hotspot, author=self.author, rating=5, body="Fictional review", is_demo=True)
        response = self.client.get(self.hotspot.get_absolute_url())
        self.assertEqual(response.context["rating_summary"]["count"], 0)
        self.assertNotContains(response, "Fictional review")
        records = self.client.get(reverse("hotspots:data")).json()["hotspots"]
        self.assertTrue(all(record["rating_count"] == 0 for record in records))
        with override_settings(DEMO_MODE=True):
            demo_response = self.client.get(self.hotspot.get_absolute_url())
            self.assertEqual(demo_response.context["rating_summary"]["count"], 1)
            self.assertTrue(demo_response.context["rating_summary"]["has_demo_reviews"])
            self.assertContains(demo_response, "Fictional review")

    def test_map_handles_empty_database(self):
        Hotspot.objects.all().delete()
        response = self.client.get(reverse("hotspots:map"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["map_data"], [])
        self.assertEqual(response.context["hotspot_count"], 0)


@override_settings(DEMO_MODE=False)
class SearchAndFilterTests(TestCase):
    """E01 US02 (#9) search and US03–US05 (#10–#12) filters, on the page and API."""

    @classmethod
    def setUpTestData(cls):
        make_hotspot(1344)  # Bryant Park, Manhattan / Midtown, Partner, Partner Site
        make_hotspot(
            53, name="Clinton Hill Library", location_description="380 Washington Ave",
            borough="Brooklyn", neighborhood_name="Clinton Hill", zip_code="11238",
            provider="BPL", access_type="Free", location_type="Library",
        )
        make_hotspot(
            70, name=None, location_description="125 Court St.",
            borough="Brooklyn", neighborhood_name="Brooklyn Heights-Cobble Hill", zip_code="11201",
            provider="Downtown Brooklyn", access_type="Free", location_type="Outdoor",
        )
        make_hotspot(
            80, name="Flushing Library", location_description="41-17 Main St",
            borough="Queens", neighborhood_name="Flushing", zip_code="11355",
            provider="QPL", access_type="Limited Free", location_type="Library",
        )
        make_hotspot(90, name="Retired Brooklyn kiosk", borough="Brooklyn", provider="BPL", is_active=False)

    def page_ids(self, **params):
        response = self.client.get(reverse("hotspots:map"), params)
        self.assertEqual(response.status_code, 200)
        return response, {item["id"] for item in response.context["map_data"]}

    def api_ids(self, **params):
        payload = self.client.get(reverse("hotspots:data"), params).json()
        self.assertEqual(payload["count"], len(payload["hotspots"]))
        return {item["id"] for item in payload["hotspots"]}

    def assert_results(self, expected, **params):
        response, ids = self.page_ids(**params)
        self.assertEqual(ids, expected)
        self.assertEqual(self.api_ids(**params), expected)
        self.assertEqual(response.context["hotspot_count"], len(expected))
        return response

    def test_no_parameters_show_every_active_hotspot(self):
        response = self.assert_results({1344, 53, 70, 80})
        self.assertFalse(response.context["is_filtered"])
        self.assertContains(response, 'id="hotspot-filters"')

    def test_search_matches_landmark_address_neighborhood_borough_and_zip(self):
        cases = {
            "Bryant Park": {1344},
            "bryant": {1344},
            "Court St": {70},
            "Clinton Hill": {53},
            "flushing": {80},
            "Queens": {80},
            "11201": {70},
            "library": {53, 80},
            "  library   main ": {80},
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assert_results(expected, q=query)

    def test_search_results_identify_location_and_link_to_profile(self):
        response, _ids = self.page_ids(q="Court St")
        record = response.context["map_data"][0]
        self.assertEqual(record["location"], "125 Court St.")
        self.assertEqual(record["profile_url"], reverse("hotspots:detail", args=[70]))
        self.assertContains(response, "125 Court St.")
        self.assertContains(response, 'value="Court St"')

    def test_search_without_matches_shows_message_not_empty_dataset_state(self):
        response = self.assert_results(set(), q="Staten Island ferry")
        self.assertContains(response, "No hotspots match your search")
        self.assertContains(response, "Staten Island ferry")
        self.assertNotContains(response, "No hotspot locations yet")
        self.assertContains(response, 'id="hotspot-filters"')

    def test_search_never_returns_inactive_records(self):
        self.assert_results(set(), q="Retired")

    def test_borough_filter_select_change_and_remove(self):
        self.assert_results({53, 70}, borough="Brooklyn")
        self.assert_results({80}, borough="Queens")
        self.assert_results({1344, 53, 70, 80}, borough="")

    def test_neighborhood_filter(self):
        self.assert_results({53}, neighborhood="Clinton Hill")
        self.assert_results({70}, neighborhood="Brooklyn Heights-Cobble Hill")
        self.assert_results(set(), borough="Queens", neighborhood="Clinton Hill")

    def test_provider_filter_select_change_and_remove(self):
        self.assert_results({53}, provider="BPL")
        self.assert_results({70}, provider="Downtown Brooklyn")
        self.assert_results({1344, 53, 70, 80}, provider="")

    def test_type_filter_uses_official_access_type(self):
        self.assert_results({53, 70}, type="Free")
        self.assert_results({80}, type="Limited Free")
        self.assert_results({1344}, type="Partner Site")
        self.assert_results({1344, 53, 70, 80}, type="")

    def test_filters_combine_with_search(self):
        self.assert_results({53}, q="library", borough="Brooklyn")
        self.assert_results({70}, borough="Brooklyn", type="Free", provider="Downtown Brooklyn")
        self.assert_results(set(), provider="QPL", type="Free")

    def test_unknown_filter_value_shows_no_match_message(self):
        response = self.assert_results(set(), provider="Not a provider")
        self.assertContains(response, "No hotspots match your search")

    def test_dropdowns_list_values_from_all_active_hotspots(self):
        response, _ids = self.page_ids(borough="Queens")
        options = response.context["filter_options"]
        self.assertEqual(options["borough"], ["Brooklyn", "Manhattan", "Queens"])
        self.assertEqual(options["provider"], ["BPL", "Downtown Brooklyn", "Partner", "QPL"])
        self.assertEqual(options["type"], ["Free", "Limited Free", "Partner Site"])
        self.assertIn({"borough": "Brooklyn", "names": ["Brooklyn Heights-Cobble Hill", "Clinton Hill"]}, options["neighborhood"])
        self.assertContains(response, '<option value="Queens" selected>')

    def test_each_active_filter_can_be_removed_on_its_own(self):
        response, _ids = self.page_ids(q="library", borough="Brooklyn")
        chips = {chip["name"]: chip["remove_url"] for chip in response.context["filter_chips"]}
        self.assertEqual(chips, {"q": "/?borough=Brooklyn", "borough": "/?q=library"})
        self.assertContains(response, "Clear all")
        _response, ids = self.page_ids(borough="Brooklyn")
        self.assertEqual(ids, {53, 70})

    def test_result_count_reports_matches_out_of_total(self):
        response, _ids = self.page_ids(borough="Brooklyn")
        self.assertEqual(response.context["total_count"], 4)
        self.assertContains(response, "<strong>2</strong> of 4 hotspots match")
        with override_settings(DEMO_MODE=True):
            self.assertContains(self.client.get(reverse("hotspots:map"), {"borough": "Brooklyn"}), "4-record sample")

    def test_api_echoes_applied_filters(self):
        payload = self.client.get(reverse("hotspots:data"), {"q": " park ", "borough": ""}).json()
        self.assertEqual(payload["filters"], {"q": "park"})
