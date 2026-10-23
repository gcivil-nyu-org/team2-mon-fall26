from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("accounts/signup/", views.SignUpView.as_view(), name="signup"),
    path("accounts/login/", views.AccountLoginView.as_view(), name="login"),
    path("accounts/logout/", views.AccountLogoutView.as_view(), name="logout"),
    path("manage/", views.admin_home, name="admin_home"),
]
