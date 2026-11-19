# Whisper: media library and transcription

Whisper is a separate Django application at `/django/demos/whisper/`. The file library
supports owner-scoped audio/video uploads, file details and history, display names,
original-file downloads, retention, and deletion. Phase 2 adds explicit queued local transcription and transcript review. It does
not call OpenAI; API-key settings and analysis remain phase 3. The existing EC2
Whisper installation runs the daemon; no AMI/container image is required.

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
not that bytes actually decode as valid media. The phase 2 worker validates and
bounds media decoding before invoking Whisper. No processing is triggered by uploading or verification.

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

## Phase 2: queue and review transcriptions

Deploy the companion backend update first, preserving the existing stack and its
application ID/role/origin. It adds a Jobs table, SQS queues, stream dispatch and
job maintenance; uploaded phase 1 media remains usable. Configure/start the
existing EC2 Whisper host using `apps/whisper/worker/README.md` in the serverless
repository. The supplied service is a Python daemon plus systemd unit; it invokes
the installed Whisper executable, so no new engine installation or image is
required. The host needs a Python 3.9+ environment for boto3/shared worker code;
Whisper may remain in a separate existing virtualenv.

Install this Django update, collect static files and restart web workers. There
is no new Django migration for phase 2. Existing WHISPER_SERVICE_URL/REGION and
Can access Whisper grants apply. Keep backend deployment first: the new UI calls
job routes absent from phase 1. The existing Django invoke policy covers those
paths if it uses the backend's ServiceInvokeResource output.

Open a ready recording and choose **Transcribe**. Set the model (base by default),
language (blank means detect), task (original-language transcription or translation
to English), optional word timestamps, temperature, beam size, previous-text
context and optional vocabulary/initial context. Whisper context is vocabulary
support, not the later AI analysis instructions. Translation rejects turbo and
English-only models. Retention defaults to 365 days after the job finishes, or
choose indefinite. Host configuration controls CPU/CUDA, model cache and runtime
limits; users cannot submit arbitrary executable paths/flags.

Choose **Queue transcription**. The job persists after the browser closes. Its
page polls while active and shows stage, timestamps, attempts and the eventual
transcript or safe failure reason. Jobs lists account history; file details links
to that recording's history. All routes use the same account/app-grant enforcement
as uploads. Each job preserves its exact source object version and normalized
options, independently of later file renames or other transcription runs.

A repeated POST using the same hidden operation key and options reuses its job.
Uncertain network submissions preserve that key and the form. **Run another
transcription** opens a fresh form/key and deliberately creates a new run. New
options with an already-used key are rejected rather than silently modifying an
existing job. Expected engine failures require an explicit new run; infrastructure
failures can retry automatically within bounded attempts.

Completed jobs show a safely escaped text preview and TXT/JSON/SRT/VTT/TSV
downloads. Previews are limited to 200000 bytes with an explicit notice; downloads
contain complete outputs. Links expire in five minutes; refresh to renew. Whisper
output is automatic and should be checked against the source. No analysis or
transcript editing/version replacement is performed in this phase.

**Cancel job** shows a confirmation page. Queued work cancels immediately; running
work stops at its next worker heartbeat. Offline-worker cancellation is settled
by backend maintenance after lease expiry. **Delete job** also requires a POST
confirmation and only accepts terminal jobs. It removes all attempt outputs and
then releases the source dependency. A source recording cannot be deleted while
any retained completed/failed/cancelled/active job references it. That source stays
readable beyond nominal retention until those jobs are cleaned up. This prevents
deleting audio needed by queued jobs or by retained transcript provenance.

## Phase 2 verification

```sh
python -m django test dwiest.django.demos.whisper.tests \
  dwiest.django.demos.whisper.test_jobs \
  dwiest.django.demos.test_application_access \
  --settings=dwiest.django.demos.test_application_settings -v 2
node --test tests/whisper-upload.test.cjs tests/whisper-jobs.test.cjs
```

Tests cover forms/options, stable submission keys, history and owner-scoped
transport, grants/CSRF, polling, safe transcript rendering, downloads and cancel/
delete confirmations. The companion backend suite exercises real local queue/
storage simulations and subprocess lifecycle, with a simulated Whisper engine;
a real FFmpeg decode is checked where the tools are installed. Live AWS IAM/CORS,
actual Whisper model output, and GPU/CPU behavior require the worker README's
smoke test on your instance. Nothing is deployed automatically by these tests.

## Next phase

Phase 3 adds per-user OpenAI keys in Parameter Store SecureString, model and saved
instructions, per-job instructions, versioned transcript analysis, and review/edit/
approve screens. The worker resolves credentials from authenticated ownership;
queue messages contain references only. This can provide the credential lookup
pattern for the existing Jobs application to adopt later.
