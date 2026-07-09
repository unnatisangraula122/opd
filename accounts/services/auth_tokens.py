def issue_api_token(user):
    from accounts.models import APIToken
    import secrets
    return APIToken.objects.create(
        user=user,
        key=secrets.token_urlsafe(32),
    )


def revoke_request_token(request):
    from accounts.models import APIToken
    token = getattr(request, 'auth', None)
    if isinstance(token, APIToken):
        token.delete()
