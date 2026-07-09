from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from accounts.models import APIToken


class BearerTokenAuthentication(BaseAuthentication):
    """Authenticate API requests via Authorization: Bearer <token> (per-tab tokens)."""

    keyword = 'Bearer'

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None

        key = parts[1].strip()
        if not key:
            raise AuthenticationFailed('Invalid token')

        try:
            token = APIToken.objects.select_related('user').get(key=key)
        except APIToken.DoesNotExist:
            raise AuthenticationFailed('Invalid or expired token')

        return (token.user, token)
