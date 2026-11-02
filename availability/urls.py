from django.urls import path

from . import views

app_name = "availability"

urlpatterns = [
    path("hotspots/<int:hotspot_pk>/availability/", views.submit_report, name="report"),
]
