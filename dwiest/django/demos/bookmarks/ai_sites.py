"""User-managed domain rules; matching never fetches a URL or calls a model."""
import re
from urllib.parse import urlsplit
from django.core import signing
from .ai_credentials import AIError, require_demo_owner
from ..bookmark_ai_models import BookmarkAISettings

BLACKLIST_OFFER_SALT = 'bookmarks.ai.failed-site'


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


def blacklisted_site(url, blocked_domains):
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
            return domain


def failed_site_offer(user, url):
    """Bind a failure-page button to its user and original submitted URL."""
    try:
        domain = normalize_site(url)
    except ValueError:
        return None
    data = {'owner': str(user.pk), 'url': url.strip(), 'domain': domain}
    return {'domain': domain, 'token': signing.dumps(data, salt=BLACKLIST_OFFER_SALT)}


def block_failed_site(user, url, token):
    require_demo_owner(user)
    try:
        data = signing.loads(token, salt=BLACKLIST_OFFER_SALT, max_age=1800)
        if data['owner'] != str(user.pk) or data['url'] != url.strip() or data['domain'] != normalize_site(url):
            raise ValueError()
    except (signing.BadSignature, ValueError, KeyError, TypeError, AttributeError):
        raise AIError('This blacklist action expired or the article URL changed. Analyze again or edit the site blacklist in AI settings. No bookmark changes were saved.') from None
    domain = data['domain']
    prefs, _ = BookmarkAISettings.objects.get_or_create(owner=user)
    current = prefs.blocked_domains
    if any(domain == entry or domain.endswith('.' + entry) for entry in current):
        return domain
    if len(current) >= 100:
        raise AIError('Your site blacklist already contains 100 sites. Remove an entry in AI settings before adding this site.')
    # A concurrent settings edit must not be replaced by an older list.
    if not BookmarkAISettings.objects.filter(pk=prefs.pk, blocked_domains=current).update(blocked_domains=current + [domain]):
        raise AIError('Your site blacklist changed in another request. Update it in AI settings.')
    return domain
