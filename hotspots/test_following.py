from urllib.parse import parse_qs, urlsplit

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

    def assert_expired_session_can_retry_after_login(self, action_url, initially_following):
        password = "Local-regression-password-924!"
        self.user.set_password(password)
        self.user.save(update_fields=["password"])
        if initially_following:
            HotspotFollow.objects.create(user=self.user, hotspot=self.hotspot)
        self.client.force_login(self.user)
        self.client.get(self.hotspot.get_absolute_url())
        self.client.logout()

        response = self.client.post(action_url)
        self.assertEqual(response.status_code, 302)
        login_url = response["Location"]
        self.assertEqual(urlsplit(login_url).path, reverse("accounts:login"))
        self.assertEqual(
            parse_qs(urlsplit(login_url).query)["next"],
            [self.hotspot.get_absolute_url()],
        )
        self.assertEqual(HotspotFollow.objects.exists(), initially_following)

        response = self.client.post(
            login_url,
            {"username": self.user.username, "password": password},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request["PATH_INFO"], self.hotspot.get_absolute_url())
        self.assertEqual(HotspotFollow.objects.exists(), initially_following)

        response = self.client.post(action_url)
        self.assertRedirects(response, self.hotspot.get_absolute_url())
        self.assertEqual(HotspotFollow.objects.exists(), not initially_following)

    def test_expired_session_follow_returns_to_profile_after_login(self):
        self.assert_expired_session_can_retry_after_login(self.follow_url, initially_following=False)

    def test_expired_session_unfollow_returns_to_profile_after_login(self):
        self.assert_expired_session_can_retry_after_login(self.unfollow_url, initially_following=True)

    def test_get_never_changes_follow_relationship(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.follow_url).status_code, 405)
        self.assertFalse(HotspotFollow.objects.exists())
        HotspotFollow.objects.create(user=self.user, hotspot=self.hotspot)
        self.assertEqual(self.client.get(self.unfollow_url).status_code, 405)
        self.assertTrue(HotspotFollow.objects.exists())

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
