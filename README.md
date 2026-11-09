# django-demos
Demonstration Django apps

<img src="https://wiest.world/images/file_demo_index_page.jpg">
<img src="https://wiest.world/images/file_demo_details_page.jpg">

## Host-site navigation

The shared demo header includes an optional
`dwiest-django-demos/components/site_navigation.html` template before the
application switcher. Its default content is empty. Host projects can override
that template in their project template directory to provide navigation to
other site areas, without copying or replacing the demo application menu.
Keep project template directories ahead of app templates in Django's loader
order. The hook does not change authentication or application routes.

## Store demo

`/django/demos/store/` provides a simple RottenWorld merchandise storefront,
product catalogs, variant selection, and a session cart. It includes a Store
card on the demo homepage and a shared navigation entry. Anonymous visitors
can browse and use the cart. No checkout, payments, orders, inventory tracking,
or fulfillment is implemented. Prices are USD; tax and shipping are not calculated.
Product images use optional HTTPS URLs; blank images get a neutral placeholder.

### One-time setup

Install this package revision, then **add the store app alongside your existing
apps** in the host project's `INSTALLED_APPS`:

```python
'dwiest.django.demos.store.apps.StoreConfig',
```

Keep the existing demos app installed for templates and static assets. Enable
Django sessions, authentication, CSRF middleware, and the request/auth template
context processors. Keep the existing `demos` URL include; it now includes the
store automatically. Back up the database before running:

```sh
python manage.py migrate demo_store
python manage.py seed_store
python manage.py collectstatic --noinput
```

`seed_store` is optional. It creates sample hats, enamel pins, and posters with
illustrative prices, plus a **Shop administrators** Django group. It does not
create accounts or overwrite existing product edits. Assign your existing
administrator account to that group using Django admin; superusers already
have access. Ordinary customers and `is_staff` alone cannot edit the store.
The management UI is `/django/demos/store/manage/`; models also appear in
Django admin. Products and catalogs start as drafts. Unpublish to remove them
from browsing; inactive variants cannot be added to a cart. Cart contents are
revalidated and priced from the database on each visit.

The store has its own `demo_store` app label and initial migration so its tables
can be created independently of the older demos. **The current EC2 deployment
script accepts only schema-neutral updates** (`migrate --check`), so this first
release needs the manual setup above before normal deployments resume. Do not
run `makemigrations` on production or use `--fake` for these new tables.

### Verification

Run the isolated Django 3.2-compatible suite:

```sh
DJANGO_SETTINGS_MODULE=dwiest.django.demos.store.test_settings \
  python -m django test dwiest.django.demos.store
```

Tests exercise the store's real database migrations, views, forms, session cart,
permission checks, CSRF protection, draft visibility, and repeatable sample setup.
Unrelated demo URL destinations are placeholders in this isolated configuration;
it does not exercise the host project's authentication flows or deployment.
