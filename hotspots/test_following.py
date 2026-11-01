from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Hotspot, HotspotFollow
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