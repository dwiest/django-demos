# Whisper: phase 1 media library

Whisper is a separate Django application at `/django/demos/whisper/`. Phase 1
supports owner-scoped audio/video uploads, file details and history, display names,
original-file downloads, retention, and deletion. It does not transcribe files or
call OpenAI. There is no worker, API-key screen, AMI, or container requirement yet.

## Deploy the companion AWS application first

Use `apps/whisper/template.yaml` and its README in `dwiest/wiest-aws-serverless`.
This is an independent stack; the existing URL/AI Job Service is unchanged.
Configure its `ServiceRoleArn` with the Django execution role, not the GitHub
provisioning role. Set `AppOrigin` to the exact HTTPS browser origin that serves
Django, without a path or trailing slash. This origin controls S3 upload CORS.

Attach `execute-api:Invoke` on the stack's `ServiceInvokeResource` output to the
Django role. The stack also verifies the caller role identity. No AWS access keys
are stored in Django settings or sent to the browser. The service uses the same
SigV4 and server-derived X-User-Reference pattern as Bookmarks; it does not share
Bookmarks credentials or its demo-owner restriction.

Configure these Django settings or environment variables:

| Setting | Value |
| --- | --- |
| `WHISPER_SERVICE_URL` | Stack `ServiceApiUrl`, HTTPS and ending `/service` |
| `WHISPER_SERVICE_REGION` | Stack region; defaults to `us-east-1` |

Then install the updated package, run `python manage.py migrate demos`, run
`python manage.py collectstatic --noinput`, and restart Django. Existing boto3
support is sufficient; no extra optional AI dependency is needed.

Migration `0050_whisper_application` adds the Whisper application catalog entry
and its native access permission. It does not modify existing files/bookmarks or
grant access to existing users automatically. In Django admin, ensure application
`whisper` is enabled and grant **Can access Whisper** to the appropriate user or
group. Superusers follow the same global application enable/disable control.
The application appears in the Apps menu and homepage for permitted accounts.

## Upload and recovery

Choose one MP3, WAV, M4A, FLAC, OGG, OPUS, AAC, MP4, MOV, WEBM, or MKV file, up to
1 GiB. Optionally choose a display name and retention (365 days by default, or
indefinite). The browser sends metadata through Django and media bytes directly
to private S3. The backend constrains the signed POST to the registered size and
media type. It verifies object metadata and copies one exact version into the
permanent area before publishing a ready record.

An upload registration lasts one hour; individual signed upload forms last at
most fifteen minutes. Retry upload reuses its operation key and skips resending
bytes when upload succeeded but verification failed. If the registration expires,
retry starts a new registration. After a page reload, an uploaded-but-unverified
file can be opened from Files and completed with **Verify upload**. Interrupted
partial uploads must be restarted from Upload file. Expired registrations and
abandoned objects are removed by cleanup/lifecycle rules.

The phase 1 checks establish registered size/type/metadata and a stable S3 version,
not that bytes actually decode as valid media. A future worker must validate and
bound media decoding. No processing is triggered by uploading or verification.

Retention starts when upload verification succeeds. Changing days remains relative
to that completion date; shortening it can expire a file immediately. Expired files
cannot be downloaded and are eligible for scheduled cleanup. Delete first shows a
confirmation page; POST makes the file unavailable immediately. Actual removal of
all versions happens on the hourly AWS schedule, with repeated cleanup until old
upload forms/in-flight completions have expired. Small idempotency tombstones remain.
Previously issued download links are bearer links valid for up to five minutes.

## Verification

```sh
python -m pip install 'Django>=3.2,<3.3' 'djangorestframework>=3.14,<3.15' \
  'cryptography>=3.4.8' django-appconf qrcode boto3 'channels>=3,<4'
python -m django test dwiest.django.demos.whisper.tests \
  dwiest.django.demos.test_application_access \
  --settings=dwiest.django.demos.test_application_settings -v 2
node --test tests/whisper-upload.test.cjs
python -m django makemigrations demos --check --dry-run \
  --settings=dwiest.django.demos.test_application_settings
```

Tests mock the service transport; companion AWS tests exercise storage with Moto.
They do not establish live AWS IAM/CORS behavior. Before considering deployment
complete, upload a small real recording, verify/download it, rename it, check
another user's access, and request deletion. Review the cleanup log and confirm
stored versions disappear after the cleanup grace period. AWS notes that newly
enabled S3 versioning can take up to 15 minutes to propagate; allow that before
initial upload writes on a new stack.

## Subsequent phases

Phase 2 adds versioned transcription jobs, SQS dispatch, job review, and a daemon
on the user's already-configured Whisper EC2 instance. The worker renews its SQS
visibility and DynamoDB lease; no image build is required initially. It reads the
source object version stored in the file record. File deletion must be extended
with atomic dependency checks before accepting transcription jobs.

Phase 3 adds per-user OpenAI keys in Parameter Store SecureString, model and saved
instructions, per-job instructions, versioned transcript analysis, and review/edit/
approve screens. The worker resolves credentials from authenticated ownership;
queue messages contain references only. This phase can provide the credential
lookup pattern for the existing Jobs application to adopt later.
