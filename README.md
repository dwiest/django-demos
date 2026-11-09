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
Product images support S3 uploads and optional legacy HTTPS URLs; blank images get a neutral placeholder.

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

### Product photo uploads in S3

Products support multiple uploaded photos at **Manage store → Edit product →
Product photos**. Save a new product before uploading. Select several photos in
one upload, then set each photo's alt text and display order. The lowest order
number is the catalog cover; ties use upload ID. Product pages show the cover
and selectable thumbnails. Existing `image_url` values remain a fallback when
there are no uploaded photos. Photos and their details save separately from the
product/variant form.

Files are stored as private S3 objects, not database blobs. The `ProductPhoto`
table stores bucket, key, dimensions, alt text, display order, and creation time.
Uploads are decoded and re-encoded as still JPEG, PNG, or WebP images, with
orientation applied and embedded metadata removed. Limits are **10 files per
request, 10 MB per file, and 24 million pixels per image**. Neither image bytes nor signed URLs are stored in the table. The browser receives
only time-limited image links; uploads use the server runtime’s IAM credentials.

Configure the host's `settings.py`:

```python
STORE_MEDIA_BUCKET = 'rotten.world'
STORE_MEDIA_PREFIX = 'store/products'
# Set this to the bucket's actual AWS region (us-east-1 is an example).
STORE_MEDIA_REGION = 'us-east-1'
STORE_MEDIA_URL_TTL = 3600  # seconds
```

The bucket defaults to `rotten.world` and the prefix to `store/products` if
omitted. Region otherwise follows the AWS SDK configuration. Use the EC2
instance role / standard AWS credential chain; do not put access keys into
Django settings. Attach the object permissions in
[`deploy/store-media-policy.json`](deploy/store-media-policy.json) to the Django
runtime's IAM role. They grant only GetObject, PutObject, and DeleteObject under
this prefix. A bucket using a customer-managed KMS key also needs the appropriate
KMS key permissions. This change does not create or modify buckets, IAM roles,
or bucket policies.

**Keep S3 Block Public Access enabled.** Images use short-lived signed GET URLs;
refresh the page after links expire. URL signing uses path-style HTTPS addressing
for the dotted `rotten.world` bucket name. Uploads go through Django, so browser
S3 CORS configuration is not required. `MEDIA_ROOT`, `MEDIA_URL`, and
`collectstatic` do not handle these uploaded files; `collectstatic` still installs
the gallery's CSS and JavaScript.

Before deploying this revision:

1. Install the updated package and its new `boto3` and `Pillow` dependencies in
   the Django virtual environment. If installing the wheel with `--no-deps`,
   install these separately first (`python -m pip install 'boto3>=1.26' 'Pillow>=9.5'`).
2. Configure the bucket region and attach the IAM policy above.
3. Back up the database, then run `python manage.py migrate demo_store` to add
   the metadata table. The current schema-neutral deploy workflow will not apply
   this migration automatically.
4. Give the Shop administrators group the new Product photo permissions. Running
   `python manage.py seed_store` updates the group too, but also creates any
   missing sample merchandise. Alternatively grant its four Product photo
   permissions in Django admin. Existing superusers already have access.
5. Run `python manage.py collectstatic --noinput` and restart Django.

If nginx limits request bodies to its 1 MB default, raise `client_max_body_size`
for this application (for example, `105m` accommodates a batch of ten 10 MB files
plus form overhead), validate the nginx configuration, and reload it. Align any
other upstream request-size limits with the intended batch size.

Removing a photo removes its metadata and attempts S3 deletion after the database
commit. Product deletion also cleans up its photos. A failed upload rolls back
its metadata and attempts to remove previously uploaded objects in that batch.
S3 cleanup failures are logged with bucket/key so retained objects can be retried;
they do not break the page or restore deleted photo records. Lifecycle/version
retention policies remain controlled by your bucket configuration.

The isolated test command above now also covers photo uploads, gallery/cover
ordering, metadata edits, permissions and CSRF, file validation, rollback and
object cleanup, and real SDK URL signing for a dotted bucket. S3 writes/deletes
are mocked in the tests; live IAM and bucket access must be checked after deployment.
