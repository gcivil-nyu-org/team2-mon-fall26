from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import HotspotFollow
from .tests import make_hotspot


class FollowHotspotTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alex")
        self.hotspot = make_hotspot()
        self.follow_url = reverse("hotspots:follow", args=[self.hotspot.pk])
        self.unfollow_url = reverse("hotspots:unfollow", args=[self.hotspot.pk])

    def test_visitor_must_sign_in_to_follow(self):
        response = self.client.post(self.follow_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertFalse(HotspotFollow.objects.exists())

    def test_signed_in_user_can_follow_hotspot(self):
        self.client.force_login(self.user)

        response = self.client.post(self.follow_url)

        self.assertRedirects(
            response,
            self.hotspot.get_absolute_url(),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            HotspotFollow.objects.filter(
                user=self.user,
                hotspot=self.hotspot,
            ).exists()
        )

    def test_following_again_does_not_create_duplicate_relationships(self):
        self.client.force_login(self.user)

        self.client.post(self.follow_url)
        self.client.post(self.follow_url)

        self.assertEqual(
            HotspotFollow.objects.filter(
                user=self.user,
                hotspot=self.hotspot,
            ).count(),
            1,
        )

    def test_signed_in_user_can_unfollow_hotspot(self):
        self.client.force_login(self.user)
        self.client.post(self.follow_url)

        response = self.client.post(self.unfollow_url)

        self.assertRedirects(
            response,
            self.hotspot.get_absolute_url(),
            fetch_redirect_response=False,
        )
        self.assertFalse(
            HotspotFollow.objects.filter(
                user=self.user,
                hotspot=self.hotspot,
            ).exists()
        )


class FollowedHotspotListTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alex")
        self.followed = make_hotspot(1344, name="Followed Park")
        self.unfollowed = make_hotspot(53, name="Other Park")
        self.inactive = make_hotspot(
            70,
            name="Retired Park",
            is_active=False,
        )
        self.followed_url = reverse("hotspots:followed")

        HotspotFollow.objects.create(
            user=self.user,
            hotspot=self.followed,
        )
        HotspotFollow.objects.create(
            user=self.user,
            hotspot=self.inactive,
        )

    def test_visitor_must_sign_in_to_view_followed_hotspots(self):
        response = self.client.get(self.followed_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_user_sees_only_active_hotspots_they_follow(self):
        self.client.force_login(self.user)

        response = self.client.get(self.followed_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Followed Park")
        self.assertNotContains(response, "Other Park")
        self.assertNotContains(response, "Retired Park")


class FollowHotspotUiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alex")
        self.hotspot = make_hotspot()

    def test_profile_shows_follow_button_when_user_is_not_following(self):
        self.client.force_login(self.user)

        response = self.client.get(self.hotspot.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Follow hotspot")
        self.assertContains(
            response,
            reverse("hotspots:follow", args=[self.hotspot.pk]),
        )

    def test_profile_shows_unfollow_button_when_user_is_following(self):
        HotspotFollow.objects.create(
            user=self.user,
            hotspot=self.hotspot,
        )
        self.client.force_login(self.user)

        response = self.client.get(self.hotspot.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unfollow hotspot")
        self.assertContains(
            response,
            reverse("hotspots:unfollow", args=[self.hotspot.pk]),
        )

    def test_signed_in_user_can_reach_followed_hotspots_from_map(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("hotspots:map"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("hotspots:followed"),
        )
        self.assertContains(response, "My followed hotspots")
