from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hotspots.models import Hotspot
from reviews.models import Review


class Command(BaseCommand):
    help = "Create clearly labeled fictional reviews at Bryant Park for a local demo only."

    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError("Demo reviews require DEMO_MODE=1. No data was changed.")
        try:
            hotspot = Hotspot.objects.get(pk=1344)
        except Hotspot.DoesNotExist as exc:
            raise CommandError("Run import_hotspots first; Bryant Park (1344) is required.") from exc

        examples = [
            ("connectnyc-demo-alex", "Alex", 5,
             "I found the network easily and used it for a quick study break."),
            ("connectnyc-demo-jordan", "Jordan", 4,
             "Useful for checking messages while visiting the park."),
            ("connectnyc-demo-sam", "Sam", 3, ""),
        ]
        with transaction.atomic():
            for username, first_name, rating, body in examples:
                user, created = get_user_model().objects.get_or_create(
                    username=username, defaults={"first_name": first_name, "is_active": False}
                )
                if created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])
                Review.objects.update_or_create(
                    hotspot=hotspot, author=user, is_demo=True,
                    defaults={"rating": rating, "body": body},
                )
        self.stdout.write(self.style.SUCCESS(
            "Seeded 3 fictional demo ratings (2 written reviews) for Bryant Park. "
            "They are hidden whenever DEMO_MODE is false."
        ))
