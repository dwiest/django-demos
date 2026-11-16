"""Server-side credential storage; no dependency on passwords or SECRET_KEY."""
import json
import os
from functools import lru_cache
from django.conf import settings
from django.views.decorators.debug import sensitive_variables
from ..bookmark_ai_models import BookmarkAISettings

SESSION_KEY = 'bookmarks_ai_encrypted_key'


class AIError(Exception):
    """Safe, user-facing error. Never include provider bodies or credentials."""

    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


class AIArticleAccessError(AIError):
    """Article retrieval or its required evidence failed; a site block may help."""


def configured(name, default=''):
    return getattr(settings, name, os.environ.get(name, default))


@lru_cache(maxsize=4)
@sensitive_variables()
def secret_json(secret_id):
    import boto3
    try:
        return json.loads(boto3.client('secretsmanager').get_secret_value(SecretId=secret_id)['SecretString'])
    except Exception:
        raise AIError('The AI secret could not be loaded. Check the server configuration.') from None


@sensitive_variables()
def cipher():
    try:
        from cryptography.fernet import Fernet, MultiFernet
    except ImportError:
        raise AIError('Install the bookmarks AI dependencies on the server.') from None
    values = configured('BOOKMARKS_AI_ENCRYPTION_KEYS', [])
    secret_id = configured('BOOKMARKS_AI_ENCRYPTION_SECRET_ID')
    if secret_id:
        values = secret_json(secret_id).get('keys', [])
    if isinstance(values, str):
        values = [v.strip() for v in values.split(',') if v.strip()]
    try:
        if not values:
            raise ValueError()
        return MultiFernet([Fernet(v.encode('ascii')) for v in values])
    except (ValueError, TypeError, AttributeError, UnicodeError):
        raise AIError('Configure the separate AI encryption key before storing API credentials.') from None


@sensitive_variables()
def encrypt(value):
    return cipher().encrypt(value.encode('utf-8')).decode('ascii')


@sensitive_variables()
def decrypt(value):
    encryption = cipher()
    from cryptography.fernet import InvalidToken
    try:
        return encryption.decrypt(value.encode('ascii')).decode('utf-8')
    except (InvalidToken, ValueError, UnicodeError):
        raise AIError('The saved API key cannot be decrypted. Restore the encryption key or enter your API key again.') from None


def server_session_required():
    backend = configured('SESSION_ENGINE', 'django.contrib.sessions.backends.db')
    if backend == 'django.contrib.sessions.backends.signed_cookies':
        raise AIError('Session-only API keys require server-side Django sessions.')


@sensitive_variables()
def api_key_for(request):
    if request.session.get(SESSION_KEY):
        server_session_required()
        return decrypt(request.session[SESSION_KEY])
    prefs = BookmarkAISettings.objects.filter(owner=request.user).first()
    if prefs and prefs.encrypted_api_key:
        return decrypt(prefs.encrypted_api_key)
    raise AIError('Enter an OpenAI API key in AI settings first.')


def require_demo_owner(user):
    # Replace this boundary with user-scoped MCP/OAuth credentials later.
    owner = configured('BOOKMARKS_API_OWNER_ID', None)
    if not user.is_authenticated or not owner or str(user.pk) != str(owner):
        raise AIError('AI bookmarks are currently available only to the configured demo account.')


@sensitive_variables()
def mcp_connection_for(user):
    require_demo_owner(user)
    url = configured('BOOKMARKS_AI_MCP_URL')
    token = configured('BOOKMARKS_AI_MCP_TOKEN')
    secret_id = configured('BOOKMARKS_AI_MCP_SECRET_ID')
    if secret_id:
        token = secret_json(secret_id).get('token', '')
    from urllib.parse import urlsplit
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password
    except ValueError:
        valid = False
    if not valid or not isinstance(token, str) or len(token) < 32 or any(c.isspace() for c in token):
        raise AIError('Configure the HTTPS MCP endpoint and its bearer token before using Analyze.')
    return {'type': 'mcp', 'server_label': 'bookmarks', 'server_url': url,
            'headers': {'Authorization': 'Bearer ' + token}}
