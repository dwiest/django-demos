# File Manager: S3 files and DynamoDB metadata

File Manager now follows Whisper's register → direct browser upload → verify flow.
Django checks the signed-in user's File Manager grant, reserves storage quota in
DynamoDB, and issues a short-lived S3 POST form. File bytes travel directly from
the browser to the private S3 bucket. Progress, retry after interrupted requests,
and verification after a page reload are supported. JavaScript is required for
uploads. SQL is used for authentication and application grants, but no longer for
File Manager metadata, quota configuration, or usage totals.

This is an independent bucket/table, with no dependency on Whisper's service,
retention policies, media validation, API Gateway, or worker. Django uses the EC2
instance role for S3 and DynamoDB control operations. No static AWS keys are needed.
Existing details/open/download/delete URLs and legacy file paths still work after
import. Anonymous access is no longer supported.

## Provision and configure

Deploy from this repository (replace the role and exact browser origin):

```sh
aws cloudformation deploy \
  --stack-name file-manager \
  --template-file deploy/file-manager.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    DjangoRoleName=YOUR_EXISTING_EC2_ROLE \
    DjangoOrigin=https://apps.wiest.world

aws cloudformation describe-stacks --stack-name file-manager \
  --query 'Stacks[0].Outputs'
```

Use the actual browser origin (for example `https://staging.wiest.world` if that's
where Django is served), without a path or trailing slash. The template provisions:

- A private, encrypted, versioned S3 bucket with exact-origin upload CORS and HTTPS-only access.
- An on-demand DynamoDB table with point-in-time recovery and deletion protection.
- An inline policy attached to the supplied EC2 role for this table and bucket prefix.

Both data resources are retained if the stack is removed. Creating the stack and
attaching its role policy requires CloudFormation/IAM deployment permissions. If
instance-role permissions are managed elsewhere, incorporate the policy there.
Existing restrictive VPC endpoint policies must also permit the new resources;
DynamoDB and S3 gateway endpoints must be available from the EC2 subnet if it has
no internet egress. The user's browser must reach the regional S3 upload endpoint.

Add the stack outputs to Django settings or its service environment:

```python
FILE_MANAGER_BUCKET = 'OUTPUT_BUCKET_NAME'
FILE_MANAGER_TABLE = 'OUTPUT_TABLE_NAME'
FILE_MANAGER_REGION = 'us-east-1'
```

On a newly versioned bucket, allow S3's documented versioning propagation period
(up to 15 minutes) before the first upload. Restart Django after configuring it.
Run `collectstatic` as part of deployment. No new Django schema migration is required.
The legacy SQL tables must remain present for the import command.

## Quotas and storage behavior

Default limits are 100 files, 1 GiB per upload, and 5 GiB total per user. Override
with `FILE_MANAGER_MAX_FILES`, `FILE_MANAGER_MAX_FILESIZE`, and
`FILE_MANAGER_MAX_TOTAL_FILESIZE` in settings or environment. Values of zero or
less remove that quota, subject to the fixed 1 GiB browser-upload cap.

A DynamoDB item with `pk=CONFIG`, `sk=QUOTA` and numeric `max_files`,
`max_filesize`, `max_total_filesize` attributes overrides the defaults. Legacy
quota row 1 can be copied by the migration command's `--copy-quota` option.
The old SQL FileQuota and FileSummary rows are no longer read by the application.

Each user's partition is `USER#<Django user ID>`; its `USAGE` item stores reserved
file count and bytes. `FILE#<file ID>` items store names, description, type, size,
creation time, upload state, and the verified S3 object version. Registration uses
a transaction to reserve quota and create metadata together. Retries reuse the
same operation key; conflicting payloads are rejected. Never recycle Django user
IDs when restoring or moving accounts: ownership is tied to these IDs.

Pending uploads reserve quota for one hour. Verification checks the stored size,
registration metadata, and non-null S3 VersionId. Completed downloads always name
that exact object version, so replaying a still-valid upload form cannot replace
a ready file. Downloads use signed URLs valid for 60 seconds; an already issued
URL may remain usable until it expires after deletion. Ready files have no automatic
retention expiry. Names/descriptions can be edited without moving the S3 object.

The old per-file versioning checkbox only stored a boolean; it did not implement
version history. It is replaced with a storage protection indicator. S3 versioning
is always required. The UI does not expose a revision-history browser. Imported
MD5/SHA256 values are preserved; new browser uploads show “Not calculated” for
those legacy hashes. Verification does not scan for malware or establish that
bytes match the declared MIME type. Unsafe inline types, including HTML/SVG, are
served as attachments with `application/octet-stream`.

## Import existing files

First back up the SQL database and local upload directory. During a maintenance
window, pause File Manager access and the cleanup job while importing. Install
the new package on the instance, configure AWS resources, and run:

```sh
python manage.py migrate_file_manager --source-dir /path/to/current/uploads
python manage.py migrate_file_manager --source-dir /path/to/current/uploads --copy-quota --apply
```

Without `--apply`, all local files are checked against their SQL sizes and existing
checksums and no AWS writes occur. Missing/corrupt files stop the preflight before
any copying begins. If unowned records exist, pass `--anonymous-owner USER_ID` to
assign them to an existing Django user; there is no shared anonymous partition.

The import preserves original file paths/IDs, ownership, names, descriptions,
sizes, MIME types, timestamps, and hashes. Usage totals are rebuilt through the
same transactional reservation mechanism; old FileSummary totals are ignored.
Existing files are imported even if they put the user above the new quota, and
new uploads remain blocked until enough space is freed.

The command is resumable: already imported files are skipped and incomplete
imports can be rerun. It never deletes SQL rows or local files. Keep those backups
until listing, opening, downloading, editing and deleting representative imported
files have been checked. Once writes move to AWS, rolling back the application
alone will not bring new uploads back to local storage.

## Required cleanup job

Run the following hourly using the Django virtual environment and the same
settings/environment/instance role as the web process:

```sh
python manage.py cleanup_file_manager --apply
```

Without `--apply`, it reports candidates without changing them. It releases quota
for expired uploads and removes every S3 version/delete marker of deleted files
once all upload grants have expired (plus a one-minute margin). It keeps small
DynamoDB tombstones so stale idempotency keys cannot recreate deleted uploads.
Deletion immediately hides the entry; physical cleanup may therefore take a little
over an hour plus the job interval. Successful purges are skipped on later runs.
Do not enable DynamoDB TTL on file records: that would bypass quota accounting
and S3 cleanup. Do not add automatic noncurrent-version expiration to this bucket,
since a verified download can intentionally reference a noncurrent version.

The command currently scans the metadata table. This is appropriate for a demo;
a larger installation should use a cleanup index/queue rather than a full scan.
Usage totals represent registered source sizes, not physical S3 billed bytes:
retries and retained versions may temporarily consume extra storage.

## Validation

```sh
python -m pip install 'moto[s3,dynamodb]>=5,<6'
python -m django test dwiest.django.demos.file.tests \
  --settings=dwiest.django.demos.test_application_settings
node --test tests/file-upload.test.cjs
```

The tests exercise mocked AWS resources, transactions, owner isolation, grants,
CSRF, retries, size/version validation, signed downloads, cleanup, and legacy import.
After deployment, smoke-test a real browser upload from the configured origin:
AWS IAM, endpoint policies, and S3 CORS require that real-environment check.
