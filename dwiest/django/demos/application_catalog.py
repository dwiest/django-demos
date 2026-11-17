"""Stable application identities shared by menus and authorization.

URLs are deployment details; keys/permissions must survive a host or auth change.
"""
from dataclasses import dataclass
from urllib.parse import urljoin

from django.conf import settings
from django.urls import NoReverseMatch, reverse


@dataclass(frozen=True)
class Application:
    key: str
    title: str
    category: str = 'applications'
    namespace: str = ''
    route: str = ''
    url: str = ''
    section: str = ''
    description: str = ''
    listed: bool = True
    enforce: bool = True
    staff_required: bool = False
    view_names: tuple = ()

    @property
    def codename(self):
        return 'access_' + self.key

    @property
    def permission(self):
        return 'demos.' + self.codename

    def destination(self):
        if self.category == 'toys':
            base = getattr(settings, 'DESKTOP_TOYS_BASE_URL', '/desktop-toys/')
            return urljoin(base.rstrip('/') + '/', self.url) if base else ''
        if self.route:
            try:
                return reverse(self.route)
            except NoReverseMatch:
                return ''
        return self.url


APPLICATIONS = (
    Application('bookmarks', 'Bookmarks', namespace='bookmarks', route='demos:bookmarks:home'),
    Application('invoicer', 'Invoicer', namespace='invoicer', route='demos:invoicer:home'),
    Application('journal', 'Journal', namespace='journal', route='demos:journal:home'),
    Application('qrcode', 'QR Code', namespace='qrcode', route='demos:qrcode:home'),
    Application('otp', 'Time-Based OTP', namespace='otp', route='demos:otp:home'),
    Application('expenses', 'Expenses', namespace='expenses', route='demos:expenses:home'),
    Application('inventory', 'Inventory', namespace='inventory', route='demos:inventory:home'),
    Application('file', 'File Manager', namespace='file', route='demos:file:index'),
    Application('news', 'WebSockets', namespace='news', route='demos:news:home'),
    Application('selenium', 'Selenium', namespace='selenium', route='demos:selenium:home'),
    # Public shopping and existing store-management permissions stay independent.
    Application('store', 'Store', namespace='store', route='demos:store:home', enforce=False),
    Application('grecaptcha', 'Google reCAPTCHA', namespace='grecaptcha', route='demos:grecaptcha:home', listed=False),
    Application('restapi', 'Legacy REST administration', namespace='restapi', listed=False, staff_required=True),
    Application('toy_spinning_sticks', 'Spinning Sticks', 'toys', url='spinning-sticks/index.html', section='Ambient', description='Linked rods and luminous, evolving trails.', enforce=False),
    Application('toy_tidal', 'Tidal · Wave Tank', 'toys', url='tidal/index.html', section='Ambient', description='A gently rocking tank with waves, colors, and floating toys.', enforce=False),
    Application('toy_plinko', 'Plinko', 'toys', url='plinko/index.html', section='Ambient', description='Glowing balls, bouncing pins, and colorful landing effects.', enforce=False),
    Application('toy_fireworks', 'Pixel Fireworks', 'toys', url='fireworks/index.html', section='Ambient', description='Pixel bursts, glowing trails, and sky writing.', enforce=False),
    Application('toy_beam_riders', 'Beam Riders', 'toys', url='beam-riders/index.html', section='Arcade', description='Neon lightcycles and last-rider-standing races.', enforce=False),
    Application('toy_centipede', 'Centipede', 'toys', url='centipede/index.html', section='Arcade', description='A pixel garden with splitting centipedes and colorful explosions.', enforce=False),
    Application('toy_defender', 'Defender', 'toys', url='defender/index.html', section='Arcade', description='Patrol a scrolling planet and rescue its inhabitants.', enforce=False),
    Application('toy_frogger', 'Frogger', 'toys', url='frogger/index.html', section='Arcade', description='Cross pixel traffic, river rides, and a railway.', enforce=False),
    Application('toy_galaga', 'Galaga', 'toys', url='galaga/index.html', section='Arcade', description='Diving attackers, captured fighters, and double fire.', enforce=False),
    Application('toy_missile_command', 'Missile Command', 'toys', url='missile-command/index.html', section='Arcade', description='Defend pixel cities with colorful chain reactions.', enforce=False),
    Application('toy_ms_pac_man', 'Ms. Pac-Man', 'toys', url='ms-pac-man/index.html', section='Arcade', description='A glowing maze with ghost chases and bonus fruit.', enforce=False),
    Application('toy_rally_x', 'Rally-X', 'toys', url='rally-x/index.html', section='Arcade', description='Collect flags, evade pursuers, and watch the radar.', enforce=False),
    Application('toy_space_invaders', 'Space Invaders', 'toys', url='space-invaders/index.html', section='Arcade', description='Marching formations, bunkers, and mystery saucers.', enforce=False),
    Application('local_services', 'Local services', 'services', url='/django/home/#services', view_names=('captcha', 'web3', 'quicknode', 'ws', 'ws2')),
    Application('environment_status', 'Environment status', 'services', url='/django/status/', view_names=('status',)),
    Application('voicemail', 'Voicemail', 'services', url='https://wiest.world/voicemail/', enforce=False),
    Application('messages', 'Messages', 'services', url='https://wiest.world/messages/', enforce=False),
)
BY_KEY = {app.key: app for app in APPLICATIONS}
BY_NAMESPACE = {app.namespace: app for app in APPLICATIONS if app.namespace}
CATEGORIES = (('applications', 'Applications'), ('toys', 'Desktop toys'), ('services', 'Services'))


def application_for_match(match):
    if match is None:
        return None
    namespaces = getattr(match, 'namespaces', ())
    if 'demos' in namespaces:
        index = namespaces.index('demos')
        if len(namespaces) > index + 1:
            return BY_NAMESPACE.get(namespaces[index + 1])
    for app in APPLICATIONS:
        if getattr(match, 'view_name', '') in app.view_names:
            return app
    return None
