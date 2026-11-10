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

`/django/demos/store/` provides a simple independent merchandise storefront,
product catalogs, variant selection, and a session cart. It includes a Store
card on the demo homepage and a shared navigation entry. Anonymous visitors
can browse and use the cart. Guest demo checkout and order management are available. Prices are USD; payments
and USPS rates are simulated, tax is not calculated, and inventory is not tracked.
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
request, 10 MB per file, and 24 million pixels per image**. Neither image bytes nor signed URLs are stored in the table. The browser receives time-limited signed image links; uploads use the server runtime’s IAM credentials.

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

**Keep S3 Block Public Access enabled.** Storefront images
use short-lived signed GET URLs; refresh the page after links expire. URL signing uses path-style HTTPS addressing
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
   `python manage.py seed_store` updates the group too; it only creates sample
   merchandise when the product table is empty. Alternatively grant its four Product photo
   permissions in Django admin. Existing superusers already have access.
5. Run `python manage.py collectstatic --noinput` and restart Django.

If nginx limits request bodies to its 1 MB default, raise `client_max_body_size`
for this application (for example, `105m` accommodates a batch of ten 10 MB files
plus form overhead), validate the nginx configuration, and reload it. Align any
other upstream request-size limits with the intended batch size.

Removing a photo or product retains its S3 objects for historic receipts. Product
photo versions retain their immutable object locations. A failed upload rolls back
its metadata and attempts to remove previously uploaded objects in that batch.
S3 cleanup failures are logged with bucket/key; they do not break the page.
Lifecycle/version retention policies remain controlled by your bucket configuration.
See **Branded order emails and retained image versions** below.

The isolated test command above now also covers photo uploads, gallery/cover
ordering, metadata edits, permissions and CSRF, file validation, rollback and
object cleanup, and real SDK URL signing for a dotted bucket. S3 writes/deletes
are mocked in the tests; live IAM and bucket access must be checked after deployment.

### Independent storefront branding

Store pages use their own header and footer, without the host-site navigation,
demo switcher, or host footer. The default brand is **Oddment Supply**. Your
existing products, catalog names, and uploaded photos are not renamed or changed.
The demo homepage still links into the store.

After installing this update, back up the database and run:

```sh
python manage.py migrate demo_store
python manage.py seed_store
python manage.py collectstatic --noinput
```

Migration 0003 creates a singleton `StoreBranding` settings table. The seed command
refreshes the Shop administrators group's permissions, including
`change_storebranding`; it now seeds sample Oddment Supply merchandise only when
the product table is empty, preserving populated catalogs. Superusers already
have access. The schema-neutral deployment script does not run this migration.

Use **Store settings** in the store header (`/django/demos/store/manage/branding/`)
to edit the name, tagline, introduction, header image and alt text, footer heading,
footer copy, footer image and alt text, contact email, optional HTTPS footer link,
and copyright line. Text is escaped; HTML is not accepted. Blank copyright text
uses the current year and configured store name. The images use the same
validation and private S3 delivery as product photos, under
`store/products/branding/`, so the existing media IAM policy already covers them.
Replacing or removing artwork retains the old S3 object for historical emails. No image bytes are stored in the database.

Catalog cards show clickable round photo thumbnails when a product has multiple
photos with **Display order = 0**. These are photo previews by default. An optional Purchase option mapping in
photo settings makes a photo select its explicitly linked variant. Use each photo's alt text
to label its color or view. The first uploaded photo among those tied at zero is
the initial cover. If no photo is marked zero, only the first ordered photo is
shown on the card. Product pages retain their full photo galleries regardless
of order. There is no automatic rotation.


### Demo checkout and order management

The cart now leads to **Checkout**: contact/address → shipping and payment selection
→ review totals → submit → Wurm thank-you and numbered receipt. Existing store
artwork is reused on the thank-you screen. No Stripe SDK, wallet connection, card
collection, payment charge, USPS purchase, or real shipment occurs.

**Store settings** defaults to coupon `DISCOUNT` for 5% off the merchandise subtotal
before shipping. Codes are case-insensitive; percentages support 0–100. Change the
code/percentage there or clear the code to disable it. Totals use decimal cents
and round discounts half-up. Review is required again if the cart, prices, coupon,
shipping, or contact details change. Repeated submissions reuse the same order.

Shipping is US-only and offers illustrative flat estimates: Ground Advantage
$6.95, Priority Mail $10.95, and Priority Mail Express $29.95. These are demo
figures, not USPS quotes. The payment section previews USD card and USDC wallet
flows, with a demo acknowledgment required and an explicitly simulated payment
reference saved. No card numbers or wallet secrets are accepted. Tax is shown as
not calculated, rather than claiming tax exemption.

`StoreOrder` stores totals, coupon terms, email, simulated payment acknowledgment,
status, tracking number and placement/update/fulfillment/cancellation times.
`StoreOrderItem` snapshots product name, variant, SKU, unit price and quantity;
subsequent catalog edits do not rewrite orders. Each order owns a separate
`ShippingAddress` snapshot with an optional user association for later registration.
Guest receipts require the placing browser's session; order numbers alone do not
grant access. Email contains order details so the customer retains a receipt.

Use **Manage store → Orders** (or the header's Orders link) to search/filter orders,
change quantities, remove items, edit shipping addresses, send customer messages,
mark processing, cancel or fulfill. At least one item must remain. Fulfillment
requires a tracking number. Fulfilled/cancelled orders keep their timestamps and
cannot be reopened or edited, but customer messages remain available. These are
whole-order operations; partial shipments, refunds, and adding new products to
existing orders are future work. Changes create an actor/timestamp audit event
and email notification. Item edits retain the original unit price and coupon
percentage and recalculate the total without charging a difference.

Notifications use Django's configured email backend after database commit. Set
`DEFAULT_FROM_EMAIL` and your SMTP/SES mail backend in the host settings. Without
a working backend, orders still save: the order history shows delivery failures
and a **Retry email** action. A backend acknowledgment records acceptance, not
proof of inbox delivery. Console/locmem backends do not deliver customer emails.
No customer mail is sent just by installing this revision.

Before deployment, back up the database and run in the host environment:

```sh
python manage.py migrate demo_store
python manage.py seed_store
python manage.py collectstatic --noinput
```

Migration `0004_checkout_orders` adds the tables and coupon settings. The seed
command grants order permissions to the existing Shop administrators group and
preserves populated catalogs. Superusers already have access. The existing
schema-neutral deployment workflow cannot apply the migration automatically.
Order writes in Django admin redirect to the audited store management screen.

Validation:

```sh
DJANGO_SETTINGS_MODULE=dwiest.django.demos.store.test_settings python -m django test dwiest.django.demos.store
DJANGO_SETTINGS_MODULE=dwiest.django.demos.store.test_settings python -m django makemigrations demo_store --check --dry-run
```

Before accepting real sales, add verified Stripe payment/webhook handling,
refunds, live shipping rates and label purchase, address verification, tax
calculation, inventory rules, and returns/privacy policies. Registration and
account-based order history can build on the existing optional user links.


### Catalog quick add and order email corrections

Catalog cards include **Add to cart**. A product with one active variant adds one
unit directly; products with several variants require a selection showing the
variant name and price. Photo previews remain independent of purchase options.
Adding returns to the current published catalog (or All products), shows a
confirmation, and updates the cart count. Products without active variants have
no add button. The existing POST/CSRF, publication, variant ownership, active
variant, server price, and quantity checks still apply.

In **Orders → open an order → Customer email**, enter a corrected address and
choose **Update email & notify customer**. This separate action does not require
changing shipping or status and works on fulfilled/cancelled orders too. The
change records the administrator and old/new addresses in order history and
sends an update to the corrected recipient. Failed notifications can then be
retried using **Retry email**; retries read the current order email. Previously
successful notifications are not resent. Email correction does not change any
linked user's account email. This update needs no database migration.


### Email branding and compact purchase controls

**Store settings → Email header / Email footer** configure plain-text content
for order confirmations, customer messages, and status updates. Blank header
uses the store name; blank footer is omitted. Emails now include an HTML version
with a matching plain-text fallback. HTML entered in settings or customer/order
content is escaped in the HTML email. Sender credentials and DEFAULT_FROM_EMAIL
remain host settings. No images or raw HTML are accepted in these text fields.

Catalog purchase options and a smaller Add to cart button share one compact row.
Explicit variant choices are remembered within the browser tab across catalog
and product pages, where that variant is still available. Form validation errors
retain the submitted selection. With JavaScript/storage unavailable, normal
server-side cart validation and form submission continue to work.

**Manage store → Edit product → Product photos → Purchase option (optional)**
links a photo to a variant of the same product. A mapped photo selects that
variant in the purchase dropdown. Changing the dropdown shows the first matching
photo when one is available. Catalog matching uses the featured photos shown on
the card; product pages use the full gallery. Unmapped photos remain previews;
existing photos are not assigned automatically. This prevents buying one color
while believing that previewing a different color selected it.

Back up the host database, install this revision, then run:

```sh
python manage.py migrate demo_store
python manage.py collectstatic --noinput
```

Migration `0005_email_branding_photo_variants` adds email header/footer text and
the optional photo-to-variant relation. Restart Django afterwards. The normal
schema-neutral deployment workflow will not apply this migration automatically.
Existing notifications are not resent by migration or settings changes. New
notifications and retries use current branding.

### Branded order emails and retained image versions

Order emails have separate header/footer artwork uploads in **Store settings**,
plus plain-text header/footer copy, a footer heading, storefront/help links, and
image alt text. They include 56px product images, selected options, quantities,
full totals, address and status. Confirmation, shipment and cancellation headings
are distinct; HTML is escaped and a plain-text alternative is always sent.
Upload the approved email graphics to the email fields rather than the website
fields. Suggested footer heading: `Good stuff. Questionable influences.` Set the
contact email to a monitored mailbox and supply real storefront/help URLs; blank
links are omitted. Text and contact details remain readable when images are blocked.

Configure a **permanent unsigned HTTPS media base URL** in the host Django settings:

```python
STORE_MEDIA_BUCKET = 'rotten.world'
STORE_MEDIA_PUBLIC_BASE_URL = 'https://YOUR-MEDIA-DISTRIBUTION.cloudfront.net'
```

The base URL maps to the bucket root: an object at `store/products/1/abc.png`
must be reachable at `<base>/store/products/1/abc.png`. An optional base path is
supported if the distribution is configured accordingly. Do not append a made-up
`/store/images` folder: the complete stored key is appended unchanged, including
`store/products/`. A direct S3 URL will not grant access to a private bucket. Use CloudFront with an
S3 REST origin and Origin Access Control (OAC), granting that distribution
`s3:GetObject` on `arn:aws:s3:::rotten.world/store/products/*` while keeping S3
Block Public Access enabled. Images are publicly viewable through CloudFront;
never use signed CloudFront URLs, cookies, authentication, or expiring S3 URLs for
email. Use an existing distribution only if that prefix routes directly to the
media origin. Check an uploaded object's URL without AWS credentials before
sending test receipts. The app does not provision a distribution or change bucket
access policies automatically.

Without this setting, the storefront retains its existing signed-URL behavior,
and **emails deliberately omit images** rather than send links that will expire.
This setting applies only to email; storefront product and site branding images
always keep their signed S3 URLs. Only objects in the
configured media bucket are eligible. Existing third-party `Product.image_url`
images are not used in emails: upload them into the managed S3 gallery first.

Each product photo has numbered versions. Use **Replace image / version history**
in the product editor to upload a replacement or restore a prior version.
Replacement creates a fresh UUID object key; restoring records a new version
referencing the retained original bytes. Photo alt text, display order and variant
assignment remain editable independently. Removing a photo or product removes it
from the catalog but retains its S3 objects and version records. Replacing or
removing branding artwork also retains the old objects. Only unsuccessful uploads
that never committed are cleaned up.

Orders snapshot the chosen variant's image location at checkout, falling back to
a generic product photo, never to another variant's photo. Later catalog edits,
image replacements and product deletion do not change that receipt image. The
migration records version 1 for existing photos and fills existing order image
snapshots using currently available matching photos; it cannot recover images
already deleted or reconstruct past variant selections beyond stored order data.
Already-delivered emails are not rewritten.

Application image history complements **S3 bucket versioning**, which protects
against accidental overwrites. Inspect it with:

```sh
python manage.py configure_store_media_versioning
# Explicit, one-time administrative operation:
python manage.py configure_store_media_versioning --enable
```

The command uses `STORE_MEDIA_BUCKET` and needs `s3:GetBucketVersioning`; enabling
also needs `s3:PutBucketVersioning` on `arn:aws:s3:::rotten.world`. Use an
administrative role for the one-time change rather than broadening the application
role. Versioning applies to the entire bucket, adds storage costs and does not
retroactively recover deleted content. Avoid lifecycle expiration or manual removal
of media referenced by receipts, including noncurrent versions you wish to retain.
Immutable object keys, rather than S3 version IDs in URLs, keep old emails stable.

Deploy this change with `python manage.py migrate` (migration 0006), configure and
verify the public media URL, upload email artwork, and send a new test order.

### Thank-you page artwork and email S3 paths

Migration `0007_thank_you_artwork` adds **Thank-you page image** and alt text to
Store settings. This upload is independent of website and email artwork; until
set, the receipt retains its website footer/header fallback. The image is shown
in a shallow 110–160px frame, aligned to the bottom to retain Wurm and the soil.
Use wide artwork with its subject near the bottom. Continue exploring is centered
beneath the receipt as a gold outline button with a visible keyboard focus state.
Replaced thank-you artwork is retained in S3 like other branding assets.

Email URL building now canonicalizes recognized direct S3 endpoints to the bucket
root before appending the exact stored key. For example,
`s3://rotten.world/store/products/branding/895ef1d1247c46f895428e24192f4c9f.png`
becomes
`https://s3.amazonaws.com/rotten.world/store/products/branding/895ef1d1247c46f895428e24192f4c9f.png`,
without an inserted `/store/images` directory. Regional endpoints are preserved;
virtual-host S3 endpoints use path-style addresses for dotted bucket names.
Custom CDN base paths are kept as configured because they may represent origin
mappings. This URL correction does not make a private bucket public: use the
unsigned CloudFront OAC media origin described above for private S3 objects.
Already-sent messages keep their original URLs; send a fresh test notification
once the deployment and media origin settings are corrected.

### Store-specific thank-you copy

Migration `0008_configurable_thank_you_copy` removes hard-coded Rotten.World/Wurm
wording from the shared order confirmation page. **Store settings** now includes:

| Setting | Generic default | Suggested Rotten.World value |
| --- | --- | --- |
| Thank you heading | Thank you for your order! | Wurm thanks you for your order! |
| Thank you message | Your order has been received. | “You've got excellent taste. For a surface dweller.” |
| Thank you button label | Continue shopping | Continue exploring |

The message supports plain-text line breaks and can be left empty to hide it.
Blank headings/button labels saved through Store settings use the generic defaults.
All text is escaped. Dedicated thank-you artwork remains independently configurable;
website artwork fallbacks use their configured alt text rather than mascot wording.
Existing stores receive generic copy on migration; set the branded values explicitly
for Rotten.World after deploying. Order details and the simulation notice remain
system-generated so store copy cannot obscure the current demo payment behavior.

### Guest order lookup

The storefront’s **Find my order** link accepts an order number and checkout email.
Matching requests send a signed link valid for 24 hours; the link opens a read-only
order page in any browser without registration. Changing an order’s email
invalidates its existing links. Request responses never confirm whether an order
exists. Lookup emails use the store’s email header/footer text.

Set Store settings → email shop URL to the public HTTPS storefront URL so email
links use the correct public origin behind a proxy. Otherwise the request origin
is used, requiring correct Django host/proxy configuration. Keep order lookup
routes out of CDN caches (responses also send private/no-store headers), and
avoid recording their full token URLs in access logs. Use a shared Django cache
backend in deployments with multiple workers: the email and IP request limits
(3 per recipient and 10 per source per hour) use Django’s configured cache and
are only per-process with the default local-memory backend. Source limits use
REMOTE_ADDR, so configure the trusted proxy to supply the actual client address.
No database migrations are required.

### Customer accounts

The store uses the host site's existing Django authentication URLs (`login`,
`registration`, `registration_resend`, `password_reset`, and `change_password`).
Registration and initial email verification remain owned by `django-users`.
Configure `LOGIN_URL` to the host login route and deploy with `manage.py migrate`
to apply store migration `0009_customeraddress`.

The storefront links to account settings and paginated order history. History
shows orders linked to the authenticated user; guest orders continue to use the
email lookup flow and are not claimed by matching an email address. Saved
addresses can be added, edited, deleted, and selected at checkout. Checkout
creates a separate shipping snapshot so address book edits cannot alter orders.
Email changes require the current password, a one-hour confirmation link sent
to the new address, and a confirmation POST while signed in to the same account.
For email-based usernames, confirmation also changes the login username.


### Store inventory and fulfillment

Run migrations before deploying the inventory views. Existing variants default to
print on demand with zero physical stock; existing orders are marked untracked
and never change stock balances retroactively.

In **Manage store → Edit product**, choose fulfillment per variant: print on demand,
stock only, or stock first with print-on-demand overflow. Check **Coming soon** to
keep an active product option visible while disabling purchases (including direct
POSTs and previously populated carts). Clear **Active** to hide an option instead.
Set stock dispatch and POD production/dispatch estimates there; carrier transit is
additional. Mixed orders may ship separately.

Use **Manage store → Inventory** to receive stock or enter signed adjustments with
an audit reason. The screen shows on hand, reserved, and available quantities plus
paginated movement history. Adjustments cannot remove stock reserved for orders.
Open orders reserve stock at submission, shipment consumes physical stock, and
cancellation releases reservations. Quantity edits and removed lines update those
allocations transactionally; duplicate submissions and messages on completed orders
do not move stock again. Stock-only quantities are checked on add/update and at
checkout, with conditional database updates preventing over-allocation.

Order management shows shelf and POD quantities and the delivery estimate captured
at purchase; customer order views and emails retain that estimate. POD supplier
ordering and separate shipment tracking remain manual. The demo still collects no
payment. Demo orders exercise inventory just like orders would in production.

Stock adjustments require `demo_store.change_productvariant`; existing product and
order permissions continue to control their management screens. Variants with stock
history cannot be deleted; deactivate them to retain the ledger. Product management
forms update only editable attributes, never stale inventory counters.
