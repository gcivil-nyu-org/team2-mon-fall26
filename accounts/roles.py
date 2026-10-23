"""E02 roles: visitors, registered contributors and administrators.

Roles are built on Django's own user model and groups, so no custom user model
or migration of existing review data is needed:

- Visitor: not signed in. Can browse, search, filter and read reviews.
- Contributor: any active, signed-in account. New sign-ups also join the
  "Contributors" group so the role is visible in Django admin.
- Administrator: a superuser, or a member of the "Administrators" group.
"""
from django.contrib.auth.models import Group

CONTRIBUTORS_GROUP = "Contributors"
ADMINISTRATORS_GROUP = "Administrators"

VISITOR = "visitor"
CONTRIBUTOR = "contributor"
ADMINISTRATOR = "administrator"

ROLE_LABELS = {
    VISITOR: "Visitor",
    CONTRIBUTOR: "Contributor",
    ADMINISTRATOR: "Administrator",
}


def is_contributor(user):
    """True for any active, signed-in account (administrators included)."""
    return bool(user is not None and user.is_authenticated and user.is_active)


def is_administrator(user):
    if not is_contributor(user):
        return False
    if user.is_superuser:
        return True
    cached = getattr(user, "_connectnyc_is_administrator", None)
    if cached is None:
        prefetched = getattr(user, "_prefetched_objects_cache", {}).get("groups")
        if prefetched is not None:
            cached = any(group.name == ADMINISTRATORS_GROUP for group in prefetched)
        else:
            cached = user.groups.filter(name=ADMINISTRATORS_GROUP).exists()
        user._connectnyc_is_administrator = cached
    return cached


def role_for(user):
    if is_administrator(user):
        return ADMINISTRATOR
    if is_contributor(user):
        return CONTRIBUTOR
    return VISITOR


def add_to_group(user, group_name):
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


def grant_administrator(user):
    """Give an account administrator access, including the Django admin site."""
    add_to_group(user, CONTRIBUTORS_GROUP)
    add_to_group(user, ADMINISTRATORS_GROUP)
    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])
    user.__dict__.pop("_connectnyc_is_administrator", None)


def revoke_administrator(user):
    """Return an account to the contributor role. Superusers must be changed in Django admin."""
    group = Group.objects.filter(name=ADMINISTRATORS_GROUP).first()
    if group:
        user.groups.remove(group)
    if user.is_staff and not user.is_superuser:
        user.is_staff = False
        user.save(update_fields=["is_staff"])
    user.__dict__.pop("_connectnyc_is_administrator", None)
