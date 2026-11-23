""" "Near me": sort hotspots by distance from the visitor's location."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .sorting import distance_miles, parse_near
from .tests import make_hotspot

# Times Square, roughly between the three test hotspots.
TIMES_SQUARE = "40.7580,-73.9855"


class DistanceTests(TestCase):
    def test_parse_near_accepts_coordinates_only(self):
        self.assertEqual(parse_near("40.758,-73.9855"), (40.758, -73.9855))
        for bad in ("", "abc", "40.7", "91,0", "0,181", "1,2,3", None):
            with self.subTest(bad=bad):
                self.assertIsNone(parse_near(bad))

    def test_haversine_distance(self):
        # Bryant Park to the Manhattan end of the Brooklyn Bridge is about 3.3 miles.
        miles = distance_miles((40.7536, -73.9832), "40.7061", "-73.9969")
        self.assertAlmostEqual(miles, 3.35, delta=0.15)
        self.assertEqual(distance_miles((40.7, -73.9), "40.7", "-73.9"), 0)


class NearMeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Far, near and middle, deliberately not in distance order.
        cls.far = make_hotspot(
            10,
            name="Coney Island",
            latitude=Decimal("40.5755"),
            longitude=Decimal("-73.9707"),
            borough="Brooklyn",
        )
        cls.near = make_hotspot(
            20,
            name="Bryant Park",
            latitude=Decimal("40.7536"),
            longitude=Decimal("-73.9832"),
        )
        cls.middle = make_hotspot(
            30,
            name="Union Square",
            latitude=Decimal("40.7359"),
            longitude=Decimal("-73.9911"),
        )

    def ids(self, response):
        return [item["id"] for item in response.context["map_data"]]

    def test_nearest_sort_orders_page_and_api_by_distance(self):
        params = {"sort": "nearest", "near": TIMES_SQUARE}
        page = self.client.get(reverse("hotspots:map"), params)
        self.assertEqual(self.ids(page), [20, 30, 10])
        api = self.client.get(reverse("hotspots:data"), params).json()
        self.assertEqual([item["id"] for item in api["hotspots"]], [20, 30, 10])
        distances = [item["distance_miles"] for item in api["hotspots"]]
        self.assertEqual(distances, sorted(distances))
        self.assertLess(distances[0], 0.5)
        self.assertEqual(api["filters"]["near"], "40.7580,-73.9855")

    def test_location_is_not_a_filter_and_is_shown_on_the_page(self):
        page = self.client.get(
            reverse("hotspots:map"), {"sort": "nearest", "near": TIMES_SQUARE}
        )
        self.assertFalse(page.context["is_filtered"])
        self.assertEqual(page.context["hotspot_count"], 3)
        self.assertContains(page, "Showing distances from your location, nearest first")
        self.assertContains(page, f'data-near="{TIMES_SQUARE}"')
        self.assertContains(page, " mi · ")
        self.assertContains(page, 'href="/">Stop using my location')

    def test_stop_using_location_keeps_other_filters(self):
        page = self.client.get(
            reverse("hotspots:map"),
            {"borough": "Manhattan", "sort": "nearest", "near": TIMES_SQUARE},
        )
        self.assertEqual(self.ids(page), [20, 30])
        self.assertEqual(page.context["clear_location_url"], "/?borough=Manhattan")

    def test_location_is_rounded(self):
        api = self.client.get(
            reverse("hotspots:data"),
            {"sort": "nearest", "near": "40.758012345,-73.985512345"},
        ).json()
        self.assertEqual(api["filters"]["near"], "40.7580,-73.9855")

    def test_nearest_without_location_keeps_default_order_and_explains(self):
        page = self.client.get(reverse("hotspots:map"), {"sort": "nearest"})
        self.assertEqual(self.ids(page), [10, 20, 30])
        self.assertContains(page, "allow location access to sort hotspots by distance")
        self.assertIsNone(page.context["map_data"][0]["distance_miles"])

    def test_invalid_location_is_ignored(self):
        page = self.client.get(
            reverse("hotspots:map"), {"sort": "nearest", "near": "not-a-place"}
        )
        self.assertEqual(self.ids(page), [10, 20, 30])
        self.assertNotIn("near", page.context["filters"])

    def test_distances_shown_with_another_sort(self):
        api = self.client.get(
            reverse("hotspots:data"), {"sort": "rating", "near": TIMES_SQUARE}
        ).json()
        self.assertTrue(
            all(item["distance_miles"] is not None for item in api["hotspots"])
        )

    def test_near_me_button_and_sort_option_are_offered(self):
        page = self.client.get(reverse("hotspots:map"))
        self.assertContains(page, "data-near-me")
        self.assertContains(page, '<option value="nearest"')
        self.assertContains(page, 'name="near" value=""')
