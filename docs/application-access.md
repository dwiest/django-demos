# Application catalog and access

The Apps menu, demo landing cards, workspace cards, and filtered desktop-toys
gallery all use application_catalog.py and the current user's native Django
permissions. Home and account links remain available without a grant.
Empty categories disappear. Clickable category tabs support arrow keys,
Home/End, Escape, focus exit, and outside clicks. Without JavaScript all available
categories remain accessible.

## Installation and rollout

This release includes migration **0048_application_catalog**. The current EC2
workflow is schema-neutral (migrate --check); do not use that workflow alone for
this upgrade. Back up the database, stop the service, install the new demo package,
run python manage.py migrate and python manage.py check, then restart and verify
using a superuser. Deploy the companion host templates and middleware from
django-wiest.world as part of the same release: they now require this demo version.

Migration creates the catalog and permissions. It does not grant anything to
existing or newly registered users and does not alter their data. Active
superusers have access to every enabled application. Review and grant regular
users access before inviting them back into the applications.

In Django admin:

1. Open **Demos → Applications** to enable/disable an application globally.
2. Open a user or group and assign **Can access Bookmarks**, **Can access Pixel
   Fireworks**, or the other application permissions.
3. Add users to groups for shared bundles; use individual permissions for extra
   grants. Removing an individual grant does not override an inherited group grant.

Application access does not grant access to other users' records or bypass
existing create/change/delete checks. Staff status alone does not grant access.
Legacy REST user/group administration additionally requires staff status and the
corresponding native model view/add/change/delete permissions.
With access enforcement enabled, bookmark API calls use the authenticated user.
If BOOKMARKS_API_OWNER_ID is configured, only that same user may use the private
API. Update any separate service-account arrangement explicitly before rollout.

## Settings and enforcement

APPLICATION_ACCESS_ENABLED defaults to True. False is a deployment/testing
escape hatch bypassing catalog grants and menu filtering. Existing view
permissions still apply. Do not use it for an ordinary multiuser rollout.

DESKTOP_TOYS_BASE_URL defaults to https://staging.wiest.world/desktop-toys/.
Override it when the collection moves to a different host or directory.
Nested prefixes work and links include index.html. An empty string hides toy
launch links until their host is configured.

The host LoginRequiredMiddleware delegates to the shared grant check.
Other hosts must put
dwiest.django.demos.application_access.ApplicationAccessMiddleware after Django's
AuthenticationMiddleware. Do not add a second gate to the existing host.

Bookmark APIs (including bulk operations), inventory APIs, and the legacy REST
admin API check grants after DRF authentication. Basic authentication does not
become a browser session, and session-authenticated writes retain CSRF checks.
The news WebSocket checks its grant before accepting a connection.

The public Store storefront and its account/management checks retain their
existing behavior. Its catalog grant controls workspace discovery.
Voicemail, Messages, infrastructure consoles, and desktop toys retain the
authentication enforced by their respective hosts. Their menu grants do not
secure external URLs. Toy Basic Auth is unchanged, and direct toy URLs continue
to work for users who know those credentials.

## Adding an application

Add a stable catalog key, display metadata, URL/route, category, and namespace.
Generate a migration for its permission and seed its Application row.
Unregistered demo namespaces and applications without an enabled row remain
unavailable. Keep keys stable when moving URLs or changing authentication.

APIs must include ApplicationPermission and set application_key. The browser
middleware rejects API views missing this hook. Retain all ownership filters
and other view permissions.

## Later Cognito integration

This release does not create a user pool, migrate accounts, or issue CloudFront
credentials. A later integration can link a Django user using Cognito's issuer
and subject, then use the same grants to authorize toy launches. Grants need
not be duplicated in Cognito groups.

## Validation

    python -m django test dwiest.django.demos.test_application_access --settings=dwiest.django.demos.test_application_settings

Existing bookmark/inventory/store suites explicitly disable the gate to keep
testing original behavior; the dedicated suite enables it and tests grants,
authentication, ownership, CSRF, disabled/unknown apps, WebSocket rejection,
counts, and caching.

DOM tests consume the actual rendered menu. jsdom is only a test dependency:

    npm install --prefix /tmp/navigation-tests jsdom@31.0.1 --ignore-scripts
    python tests/render_navigation_fixture.py /tmp/navigation.html
    APPLICATION_NAVIGATION_FIXTURE=/tmp/navigation.html NODE_PATH=/tmp/navigation-tests/node_modules node --test tests/application-navigation.test.cjs
