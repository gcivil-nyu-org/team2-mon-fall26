from .roles import ROLE_LABELS, is_administrator, role_for


def roles(request):
    user = getattr(request, "user", None)
    role = role_for(user)
    return {
        "user_role": role,
        "user_role_label": ROLE_LABELS[role],
        "user_is_administrator": is_administrator(user),
    }
