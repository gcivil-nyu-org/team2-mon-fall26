from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.roles import grant_administrator, revoke_administrator


class Command(BaseCommand):
    help = "Grant (or with --revoke, remove) administrator access for an existing account."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--revoke", action="store_true", help="Return the account to the contributor role.")

    def handle(self, *args, username, revoke, **options):
        try:
            user = get_user_model().objects.get(username__iexact=username)
        except get_user_model().DoesNotExist as exc:
            raise CommandError(f'No account named "{username}". No changes were made.') from exc
        if revoke and user.is_superuser:
            raise CommandError(f'"{user.username}" is a superuser; change superuser status in Django admin.')
        with transaction.atomic():
            (revoke_administrator if revoke else grant_administrator)(user)
        state = "is now a contributor" if revoke else "is now an administrator"
        self.stdout.write(self.style.SUCCESS(f"{user.username} {state}."))
