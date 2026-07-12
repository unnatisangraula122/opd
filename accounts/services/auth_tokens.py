def issue_api_token(user):
    """Issue a bearer token and record patient portal login."""
    from django.utils import timezone

    from accounts.models import APIToken
    import secrets

    token = APIToken.objects.create(
        user=user,
        key=secrets.token_urlsafe(32),
    )
    # Portal login marker — used to distinguish "new" patients who have never
    # entered the patient portal from returning portal users.
    if getattr(user, 'role', None) == 'patient':
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
    return token


def revoke_request_token(request):
    from accounts.models import APIToken
    token = getattr(request, 'auth', None)
    if isinstance(token, APIToken):
        token.delete()
