import csv
from datetime import date, timedelta
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms.models import model_to_dict
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.roles import grant_administrator
from reviews.models import Review, ReviewVote

from .forms import HotspotEditForm, MAX_IMPORT_BYTES
from .models import Hotspot
from .tests import make_hotspot


@override_settings(DEMO_MODE=False)
class OfficialDataManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.administrator = user_model.objects.create_user(username="data-admin")
        grant_administrator(cls.administrator)
        cls.contributor = user_model.objects.create_user(username="review-author")
        cls.voter = user_model.objects.create_user(username="review-voter")
        cls.hotspot = make_hotspot()
        cls.retired = make_hotspot(20, name="Retired library", is_active=False)
        cls.review = Review.objects.create(
            hotspot=cls.hotspot, author=cls.contributor, rating=4, body="Keep this review."
        )
        cls.vote = ReviewVote.objects.create(review=cls.review, user=cls.voter)
        with (settings.BASE_DIR / "data/connectnyc_hotspots_sample.csv").open(newline="") as source:
            cls.sample_rows = list(csv.DictReader(source))

    def setUp(self):
        self.client.force_login(self.administrator)

    def upload(self, rows=None, **extra):
        stream = StringIO()
        writer = csv.DictWriter(stream, fieldnames=self.sample_rows[0].keys())
        writer.writeheader()
        writer.writerows(self.sample_rows[:1] if rows is None else rows)
        data = {
            "csv_file": SimpleUploadedFile("hotspots.csv", stream.getvalue().encode(), "text/csv"),
            "source_date": "2026-10-14",
        }
        data.update(extra)
        return self.client.post(reverse("hotspots:manage_import"), data)

    def edit_data(self, **extra):
        data = model_to_dict(self.hotspot, fields=HotspotEditForm.Meta.fields)
        data = {key: "" if value is None else value for key, value in data.items()}
        data.update(extra)
        return data

    def routes(self):
        return [
            reverse("hotspots:manage_list"), reverse("hotspots:manage_import"),
            reverse("hotspots:manage_edit", args=[self.hotspot.pk]),
            reverse("hotspots:manage_retire", args=[self.hotspot.pk]),
        ]

    def test_visitors_and_contributors_cannot_read_or_mutate_management_routes(self):
        for signed_in in (False, True):
            self.client.logout()
            if signed_in:
                self.client.force_login(self.contributor)
            for route in self.routes():
                for method in (self.client.get, self.client.post):
                    with self.subTest(signed_in=signed_in, route=route, method=method.__name__):
                        response = method(route, {"confirm": "yes"})
                        self.assertEqual(response.status_code, 403 if signed_in else 302)
                        if not signed_in:
                            self.assertTrue(response.url.startswith(reverse("accounts:login") + "?next="))
        self.hotspot.refresh_from_db()
        self.assertTrue(self.hotspot.is_active)

    def test_staff_without_administrator_role_is_denied(self):
        self.contributor.is_staff = True
        self.contributor.save(update_fields=["is_staff"])
        self.client.force_login(self.contributor)
        self.assertEqual(self.client.get(reverse("hotspots:manage_list")).status_code, 403)

    def test_all_administrator_pages_render_and_dashboard_links_to_tools(self):
        for route in self.routes():
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)
        dashboard = self.client.get(reverse("accounts:admin_home"))
        self.assertContains(dashboard, reverse("hotspots:manage_list"))
        self.assertContains(dashboard, reverse("hotspots:manage_import"))

    def test_list_filters_include_retired_records_and_find_source_id(self):
        response = self.client.get(reverse("hotspots:manage_list"))
        self.assertEqual(response.context["page_obj"].paginator.count, 2)
        self.assertEqual(response.context["active_count"], 1)
        self.assertEqual(response.context["retired_count"], 1)
        for query, expected in [({"status": "retired"}, {20}), ({"q": "1344"}, {1344}),
                                ({"status": "active", "q": "library"}, set())]:
            response = self.client.get(reverse("hotspots:manage_list"), query)
            self.assertEqual({h.pk for h in response.context["page_obj"]}, expected)

    def test_list_paginates_with_filter_query_preserved(self):
        for index in range(51):
            make_hotspot(10000 + index, name=f"Library {index:02d}")
        response = self.client.get(reverse("hotspots:manage_list"), {"q": "Library", "status": "active", "page": 2})
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["page_obj"]), 1)
        self.assertContains(response, "q=Library&amp;status=active")

    def test_upload_creates_then_updates_without_duplicate_or_lost_relationship(self):
        row = dict(self.sample_rows[0], doitt_id=str(self.hotspot.pk), name="Official update")
        response = self.upload([row, self.sample_rows[1]])
        self.assertRedirects(response, reverse("hotspots:manage_list"))
        self.upload([row, self.sample_rows[1]])
        self.assertEqual(Hotspot.objects.count(), 3)
        self.hotspot.refresh_from_db()
        self.assertEqual(self.hotspot.name, "Official update")
        self.assertEqual(self.hotspot.source_acquired_on, date(2026, 10, 14))
        self.assertTrue(Review.objects.filter(pk=self.review.pk, hotspot=self.hotspot).exists())
        self.assertTrue(ReviewVote.objects.filter(pk=self.vote.pk).exists())

    def test_invalid_later_upload_row_rolls_back_every_change(self):
        response = self.upload([
            dict(self.sample_rows[0], doitt_id=str(self.hotspot.pk), name="Do not save"),
            dict(self.sample_rows[1], latitude="91"),
        ])
        self.assertContains(response, "Invalid row 3")
        self.hotspot.refresh_from_db()
        self.assertEqual(self.hotspot.name, "Bryant Park")
        self.assertEqual(Hotspot.objects.count(), 2)

    def test_bad_upload_encoding_and_excessive_size_are_friendly_errors(self):
        cases = [
            (b"\xff\xfe\x00", "Save the CSV as UTF-8"),
            (b"x" * (MAX_IMPORT_BYTES + 1), "no larger than 5 MB"),
        ]
        for contents, message in cases:
            with self.subTest(message=message):
                response = self.upload(csv_file=SimpleUploadedFile("bad.csv", contents))
                self.assertContains(response, message)
        self.assertEqual(Hotspot.objects.count(), 2)

    def test_import_rejects_future_acquisition_date_and_empty_post(self):
        response = self.upload(source_date=(timezone.localdate() + timedelta(days=1)).isoformat())
        self.assertContains(response, "cannot be in the future")
        response = self.client.post(reverse("hotspots:manage_import"), {})
        self.assertContains(response, "This field is required.")
        self.assertEqual(Hotspot.objects.count(), 2)

    def test_edit_updates_public_data_but_preserves_identity_provenance_and_reviews(self):
        response = self.client.post(reverse("hotspots:manage_edit", args=[self.hotspot.pk]), self.edit_data(
            name="Updated Bryant Park", borough="Queens", provider="New provider",
            hotspot_id="999999", source_object_id="999999", source_ref="forged",
            source_acquired_on="2020-01-01", is_active="False",
        ))
        self.assertRedirects(response, reverse("hotspots:manage_list"))
        self.hotspot.refresh_from_db()
        self.assertEqual(self.hotspot.source_object_id, 11344)
        self.assertIsNone(self.hotspot.source_ref)
        self.assertEqual(self.hotspot.source_acquired_on, date(2026, 10, 14))
        self.assertTrue(self.hotspot.is_active)
        self.assertEqual(self.hotspot.reviews.get().pk, self.review.pk)
        self.assertEqual(Hotspot.objects.count(), 2)
        self.assertContains(self.client.get(self.hotspot.get_absolute_url()), "Updated Bryant Park")
        api = self.client.get(reverse("hotspots:data"), {"borough": "Queens"}).json()
        self.assertEqual(api["hotspots"][0]["provider"], "New provider")
        self.assertEqual(self.client.get(reverse("hotspots:data"), {"borough": "Manhattan"}).json()["count"], 0)

    def test_invalid_edit_keeps_input_without_database_changes(self):
        for changes, field in [({"latitude": "91"}, "latitude"), ({"borough": "Moon"}, "borough"),
                               ({"access_type": "Invalid"}, "access_type")]:
            with self.subTest(field=field):
                response = self.client.post(reverse("hotspots:manage_edit", args=[self.hotspot.pk]),
                                            self.edit_data(name="Unsaved name", **changes))
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
                self.assertEqual(response.context["form"]["name"].value(), "Unsaved name")
        self.hotspot.refresh_from_db()
        self.assertEqual(self.hotspot.name, "Bryant Park")

    def test_stale_edit_cannot_undo_retirement(self):
        form = HotspotEditForm(self.edit_data(name="Corrected name"), instance=self.hotspot)
        self.assertTrue(form.is_valid(), form.errors)
        Hotspot.objects.filter(pk=self.hotspot.pk).update(is_active=False)
        form.save()
        self.hotspot.refresh_from_db()
        self.assertFalse(self.hotspot.is_active)
        self.assertEqual(self.hotspot.name, "Corrected name")

    def test_removal_requires_confirmed_post(self):
        route = reverse("hotspots:manage_retire", args=[self.hotspot.pk])
        self.assertContains(self.client.get(route), "Cancel")
        self.client.post(route, {})
        self.hotspot.refresh_from_db()
        self.assertTrue(self.hotspot.is_active)
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())

    def test_retirement_hides_public_hotspot_and_filters_but_preserves_reviews_and_votes(self):
        route = reverse("hotspots:manage_retire", args=[self.hotspot.pk])
        self.assertRedirects(self.client.post(route, {"confirm": "yes"}), reverse("hotspots:manage_list"))
        self.hotspot.refresh_from_db()
        self.assertFalse(self.hotspot.is_active)
        self.assertEqual(Review.objects.get(pk=self.review.pk).body, "Keep this review.")
        self.assertTrue(ReviewVote.objects.filter(pk=self.vote.pk).exists())
        self.assertEqual(self.client.get(self.hotspot.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(reverse("hotspots:data")).json()["count"], 0)
        response = self.client.get(reverse("hotspots:map"), {"q": "Bryant"})
        self.assertEqual(response.context["hotspot_count"], 0)
        self.assertEqual(response.context["filter_options"], {})
        self.client.force_login(self.contributor)
        for name, kwargs in [("reviews:create", {"hotspot_pk": self.hotspot.pk}),
                             ("reviews:edit", {"pk": self.review.pk}),
                             ("reviews:delete", {"pk": self.review.pk}),
                             ("reviews:vote", {"pk": self.review.pk})]:
            response = self.client.post(reverse(name, kwargs=kwargs), {"rating": 5})
            self.assertEqual(response.status_code, 404)

    def test_reimport_of_removed_hotspot_does_not_restore_public_visibility(self):
        self.client.post(reverse("hotspots:manage_retire", args=[self.hotspot.pk]), {"confirm": "yes"})
        self.upload([dict(self.sample_rows[0], doitt_id=str(self.hotspot.pk))])
        self.hotspot.refresh_from_db()
        self.assertFalse(self.hotspot.is_active)
        self.assertEqual(self.client.get(self.hotspot.get_absolute_url()).status_code, 404)
        self.assertTrue(ReviewVote.objects.filter(pk=self.vote.pk).exists())

    def test_mutations_require_csrf_and_unsupported_methods_do_not_write(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.administrator)
        for route in self.routes()[1:]:
            with self.subTest(route=route):
                self.assertEqual(csrf_client.post(route, {"confirm": "yes"}).status_code, 403)
                self.assertEqual(self.client.put(route, "{}", content_type="application/json").status_code, 405)
        self.hotspot.refresh_from_db()
        self.assertTrue(self.hotspot.is_active)

    def test_unknown_hotspot_has_no_management_actions(self):
        for name in ("manage_edit", "manage_retire"):
            self.assertEqual(self.client.get(reverse(f"hotspots:{name}", args=[999999])).status_code, 404)

    def test_official_names_are_escaped_in_management_pages(self):
        self.hotspot.name = '<script>alert("x")</script>'
        self.hotspot.save(update_fields=["name"])
        response = self.client.get(reverse("hotspots:manage_list"))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, self.hotspot.name)
