from django.contrib.auth.models import User

ASSIGNABLE_ROLES = ("underwriter", "telecallers", "superadmin")


def assignable_users_queryset():
    return (
        User.objects.filter(
            is_active=True,
            user_profile__role__in=ASSIGNABLE_ROLES,
        )
        .select_related("user_profile")
        .order_by("first_name", "username")
    )


def is_assignable_user(user_id) -> bool:
    if not user_id:
        return True
    return assignable_users_queryset().filter(pk=user_id).exists()
