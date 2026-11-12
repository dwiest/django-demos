"""Cognito access-token validation and MCP protected-resource discovery."""
from functools import lru_cache
import os
import re
from urllib.parse import urlsplit

import jwt

def required_scopes(resource):
    return (resource + '/read', resource + '/write')


class AuthError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


def configuration():
    pool = os.environ.get('COGNITO_USER_POOL_ID', '')
    resource = os.environ.get('PUBLIC_MCP_URL', '')
    client = os.environ.get('COGNITO_CLIENT_ID', '')
    subjects = {s.strip() for s in os.environ.get('COGNITO_ALLOWED_SUBJECTS', '').split(',') if s.strip()}
    parsed = urlsplit(resource)
    if (not re.fullmatch(r'us-east-1_[A-Za-z0-9]+', pool) or not client or not subjects
            or parsed.scheme != 'https' or not parsed.netloc or parsed.query or parsed.fragment
            or parsed.username or parsed.password or resource.endswith('/')):
        raise AuthError(503, 'cognito_auth_not_configured')
    issuer = 'https://cognito-idp.us-east-1.amazonaws.com/' + pool
    return issuer, resource, client, subjects


def metadata_path(resource):
    return '/.well-known/oauth-protected-resource' + urlsplit(resource).path


def discovery():
    issuer, resource, _, _ = configuration()
    parsed = urlsplit(resource)
    origin = f'{parsed.scheme}://{parsed.netloc}'
    return {'resource': resource, 'authorization_servers': [origin],
            'scopes_supported': list(required_scopes(resource)), 'bearer_methods_supported': ['header']}


def challenge(code=None):
    _, resource, _, _ = configuration()
    parsed = urlsplit(resource)
    metadata_url = f'{parsed.scheme}://{parsed.netloc}' + metadata_path(resource)
    value = f'Bearer resource_metadata="{metadata_url}", scope="{" ".join(required_scopes(resource))}"'
    if code:
        value += f', error="{code}"'
    return {'WWW-Authenticate': value}


@lru_cache(maxsize=4)
def key_client(issuer):
    return jwt.PyJWKClient(issuer + '/.well-known/jwks.json', lifespan=300, timeout=5)


def verify(authorization):
    issuer, resource, client, subjects = configuration()
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not token or len(token) > 16384:
        raise AuthError(401, 'invalid_token')
    try:
        key = key_client(issuer).get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=['RS256'], issuer=issuer, audience=resource,
                            options={'require': ['exp', 'iat', 'iss', 'aud', 'sub', 'client_id', 'token_use']})
    except jwt.PyJWKClientConnectionError:
        raise AuthError(503, 'cognito_keys_unavailable') from None
    except (jwt.PyJWTError, ValueError, TypeError):
        raise AuthError(401, 'invalid_token') from None
    if claims.get('token_use') != 'access' or claims.get('client_id') != client:
        raise AuthError(401, 'invalid_token')
    if claims.get('sub') not in subjects:
        raise AuthError(403, 'user_not_authorized')
    scope = claims.get('scope')
    if not isinstance(scope, str) or not set(required_scopes(resource)).issubset(scope.split()):
        raise AuthError(403, 'insufficient_scope')
    return claims


def authorization_metadata():
    issuer, resource, _, _ = configuration()
    domain = os.environ.get('COGNITO_DOMAIN', '').rstrip('/')
    if not re.fullmatch(r'https://[a-z0-9-]+\.auth\.us-east-1\.amazoncognito\.com', domain):
        raise AuthError(503, 'cognito_domain_not_configured')
    parsed = urlsplit(resource)
    origin = f'{parsed.scheme}://{parsed.netloc}'
    # Metadata facade delegates OAuth to Cognito, whose discovery omits S256.
    # It does not claim RFC 9207 issuer-response support or client registration.
    return {'issuer': origin, 'authorization_endpoint': domain + '/oauth2/authorize',
            'token_endpoint': domain + '/oauth2/token',
            'jwks_uri': issuer + '/.well-known/jwks.json',
            'response_types_supported': ['code'],
            'grant_types_supported': ['authorization_code', 'refresh_token'],
            'code_challenge_methods_supported': ['S256'],
            'token_endpoint_auth_methods_supported': ['client_secret_basic', 'client_secret_post'],
            'scopes_supported': ['openid', 'email', 'profile', *required_scopes(resource)]}

