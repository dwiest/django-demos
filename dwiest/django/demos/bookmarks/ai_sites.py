"""User-managed domain rules; matching never fetches a URL or calls a model."""
import re
from urllib.parse import urlsplit
from .ai_credentials import AIError


def normalize_site(value):
    """Accept a domain or HTTP(S) URL and return a normalized DNS hostname."""
    value = value.strip()
    if not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Enter a domain or an HTTP(S) URL.')
    try:
        parsed = urlsplit(value if '://' in value else 'https://' + value)
        if parsed.scheme.lower() not in ('http', 'https') or parsed.username is not None or parsed.password is not None:
            raise ValueError()
        # Reject malformed ports even though valid ports do not affect matching.
        parsed.port
        host = (parsed.hostname or '').rstrip('.').encode('idna').decode('ascii').lower()
    except (ValueError, UnicodeError):
        raise ValueError('Enter a domain or an HTTP(S) URL without login credentials.') from None
    if host.startswith('www.'):
        host = host[4:]
    labels = host.split('.')
    if len(host) > 253 or len(labels) < 2 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels):
        raise ValueError('Enter a valid domain, such as example.com.')
    return host


def check_site_allowed(url, blocked_domains):
    if not blocked_domains:
        return
    try:
        host = normalize_site(url)
    except ValueError:
        # The blacklist accepts DNS names; don't change the editor's URL rules
        # for other valid hosts, such as IPv6 literals.
        return
    for domain in blocked_domains:
        if host == domain or host.endswith('.' + domain):
            raise AIError('AI analysis for {} is blocked by your site blacklist. Remove it in AI settings to analyze this site. No AI request was made.'.format(domain))
