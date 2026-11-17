# AI-assisted bookmarks

The bookmark editor supports **Analyze -> review/edit -> approve -> save in Django**.
The OpenAI agent retrieves the article using Responses API web search, reads the
existing bookmark/tags through remote MCP, and returns a structured proposal.
Analysis exposes only four explicit read tools. No bookmark or tag is written
until the user submits the review page. Approved values and tags are saved locally
in one database transaction, with no further OpenAI, MCP, or REST calls. Normal
manual bookmark saves still work when AI is unconfigured; the application never
falls back to a shared OpenAI key.

## Deploy the companion MCP change first

The companion `dwiest/wiest-aws-serverless` change is under `apps/bookmarks-mcp`.
It adds bearer authentication to the recovered Lambda and includes manual-update
and new-SAM-deployment instructions. Use its `InboundAuthSecretArn` (or the secret
created for the existing Lambda) in the Django configuration below. The current
MCP owner remains `BOOKMARKS_API_OWNER_ID`; AI access is restricted to that same
logged-in Django account. `mcp_connection_for()` is the replacement boundary for
future user-scoped OAuth. The REST API's existing ownership/auth is unchanged.

The live read check previously returned invalid JSON from Django. The companion
change adds diagnostics, but its URL/auth/configuration still needs verification.
Confirm authenticated `list_tags` works before running the live AI workflow.

## Dependencies and migration

The code retains Python 3.7/Django 3.2 compatibility by calling the Responses HTTP
API directly, without requiring a modern OpenAI SDK. Install the optional extra:

```sh
python -m pip install '.[bookmarks-ai]'
python manage.py showmigrations demos
python manage.py migrate demos
python manage.py collectstatic --noinput
```

`0009_bookmark_ai` creates only AI preferences and review-record tables. It does
not rewrite Bookmark/Tag data or repair historical migration/schema differences.
The workflow tests use the current legacy schema; the migration test separately
executes the real migration chain, checks existing bookmark data, and reverses
only the AI migrations. Do not generate unrelated schema changes for this feature.

`0010_bookmark_ai_blocked_domains` adds an empty per-user site blacklist to the
existing AI preferences. Run `python manage.py migrate demos` before restarting
with the updated package; existing API credentials and instructions are retained.
`0011_bookmark_ai_attempt` adds a separate latest-attempt table keyed by account
and URL, without modifying legacy Bookmark/Tag tables.

## Configure after resources exist

Settings may be supplied as Django settings or environment variables. No real
credentials or deployment URLs are committed. Required for live operation:

| Setting | Value |
| --- | --- |
| `BOOKMARKS_API_OWNER_ID` | Existing configured owner's Django numeric ID |
| `BOOKMARKS_AI_MCP_URL` | Final HTTPS MCP endpoint, including `/api/bookmarks-mcp` |
| `BOOKMARKS_AI_MCP_SECRET_ID` | Secrets Manager ARN with the MCP `token` JSON field |
| `BOOKMARKS_AI_ENCRYPTION_SECRET_ID` | Separate Secrets Manager ARN with a `keys` JSON array |
| `BOOKMARKS_AI_MODEL` | An enabled reasoning model supporting web search `open_page`, remote MCP, and structured output |
| `SESSION_ENGINE` | A server-side Django session backend, such as the default database backend |

Optional `BOOKMARKS_AI_MODELS` is a Django list or comma-separated environment
variable of selectable model IDs. An empty list means users use the configured
default. No model ID is assumed; choose one available to the user's API account.
`BOOKMARKS_AI_TIMEOUT` defaults to 120 seconds **per OpenAI request**. Analyze is
a synchronous server request; set application-server, HAProxy, and any CDN
timeouts accordingly. For larger analysis workloads, move orchestration to a job
queue with polling. Approval is a local database save and does not need a usable
OpenAI key, encryption secret, selected model, or MCP connection. It retains the
configured demo-owner restriction.

The EC2 role needs `secretsmanager:GetSecretValue` for the two exact secret ARNs,
plus KMS decrypt permission if customer-managed KMS keys protect them. No AWS
access keys belong in application code. Django caches secret values per process;
restart workers after changing either secret. The Lambda's inbound-token cache
has a separate 60-second lifetime.

For local configuration, `BOOKMARKS_AI_MCP_TOKEN` and
`BOOKMARKS_AI_ENCRYPTION_KEYS` can supply the values directly. Secret-ID settings
take precedence. Do not reuse the MCP token, Django `SECRET_KEY`, a login password,
or the user's OpenAI API key as the encryption key.

## Encryption secret and rotation

Generate a Fernet key once using `cryptography.fernet.Fernet.generate_key()` and
store its ASCII value in the separate secret:

```json
{"keys":["REPLACE_WITH_A_GENERATED_FERNET_KEY"]}
```

Saved API keys are authenticated ciphertext in `BookmarkAISettings`. Session-only
keys are also encrypted and placed in a **server-side** session, with browser-close
session expiry; signed-cookie sessions are rejected for this option. Both modes
therefore need the encryption secret. The browser receives neither ciphertext
nor a saved key through settings HTML. Login-password changes/resets are unrelated
to encryption and do not require re-encryption. Losing all applicable encryption
keys means users must enter their API credentials again.

To rotate:

1. Publish `{"keys":["NEW_KEY", "OLD_KEY"]}` and restart all application workers.
2. Run `python manage.py rotate_bookmark_ai_keys --dry-run`.
3. Run `python manage.py rotate_bookmark_ai_keys` to re-encrypt saved credentials
   transactionally using the first key. Failure rolls back the saved-key changes.
4. Keep old keys until sessions encrypted with them have expired or been removed.
   Session ciphertext is not rewritten by the management command. Run the normal
   `clearsessions` maintenance command to remove expired database sessions.
5. Retire old keys and restart workers. Preserve keys needed for any backups you
   intend to restore, or accept that restored credentials will need re-entry.

Changing a Secrets Manager value alone does not rotate ciphertext in Django.

## User workflow

1. Sign in as the configured demo owner and open **Bookmarks -> AI settings**.
2. Enter a personal OpenAI API key; session-only is the default, or choose Save
   encrypted. Test connection checks OpenAI credentials without generating text;
   tool/model access is checked by the live analysis. Set personal instructions.
3. Open Add or Edit bookmark, enter an HTTP(S) URL, optionally enter task-specific
   instructions by opening **Custom analysis instructions (optional)**, and click **Analyze**. Page/task/tool content cannot authorize
   writes. Failed article access, MCP errors, or invalid metadata produce a clear
   error and leave the original form/data intact.
4. Review the current form and proposed fields side by side. Check which values
   to use, edit any proposed values, and review the final tag names. A removed
   name removes that assignment; a new name authorizes creating that tag. Read
   status and visibility preserve the editor's selections, displayed on review.
5. Approve to save in Django, or cancel without changes. Proposals expire in
   30 minutes and belong only to the initiating account.

## User-managed site blacklist

Open **Bookmarks -> AI settings -> AI site blacklist** to add, edit, or remove
domains. Enter one domain per line, or paste full article URLs. Saving this list
does not require AI credentials and does not change API keys, instructions, or
the selected model. Leave the list empty to show no site warnings. New installations
and existing accounts start with an empty list; retrieval failures never add
sites automatically.

When article retrieval or its required verification fails, the editor offers
**Add this site to blacklist**, naming the domain and its subdomains. Clicking
it updates your list locally, without another analysis call or saving the
bookmark. All editor fields, tag choices, and analysis instructions remain on
the page. The action is bound to your account and the failed URL for 30 minutes;
changing the URL or using an expired action requires another failure page or
editing the list in AI settings. Repeated clicks do not duplicate the rule.
Credential, model, and configuration errors do not offer this convenience action.

Entries are normalized to lowercase ASCII/IDNA domains, deduplicated, and stripped
of a leading `www.` and trailing DNS dot. Paths, query strings, fragments, and
valid ports in pasted URLs do not affect matching. Wildcards and URLs containing
login credentials are rejected. Up to 100 domains may be saved.

Each entry matches that exact domain and its subdomains: `example.com` warns for
`www.example.com` and `news.example.com`, but not `notexample.com` or
`example.com.other.test`. An entry for `news.example.com` does not warn for
`example.com`. Rules belong to the logged-in account and use the existing AI
demo-owner access restriction.

The blacklist is advisory: the editor shows a warning for a listed host and
still permits an explicit Analyze request. The warning updates as the URL is
edited and is also shown server-side when an attempt is submitted. A successful
attempt still produces a normal review. Manual bookmark saves and approval of
existing proposals continue to work. The list does not filter redirects or
other sources used during research.

## Last attempted analysis

The bookmark editor shows the last attempted analysis for its current URL as a
local date/time and elapsed time. Each actual model-request attempt updates one
`BookmarkAIAttempt` row for the account/URL immediately before the provider call,
so retrieval failures, provider errors, and timeouts retain the timestamp. A
missing key, invalid URL, or incomplete model/MCP configuration does not record
an attempt because no model request was made. Saving a bookmark, approving a
proposal, and adding a site to the blacklist do not update the attempt time.

Attempts are tracked by URL, including new unsaved bookmark drafts, without
creating or changing a Bookmark row. Changing a bookmark URL shows the history
for the new URL; another user's timestamps are never shown. The displayed time
is hidden while the editor contains a different URL. Attempt records retain only
the owner, URL, and latest timestamp; they contain no credentials, article text,
or provider responses. They persist independently of expiring review records
and are deleted with the account. Existing attempts cannot be backfilled.

Review records retain snapshots, proposals, sources, and approved values; older
records can also contain an MCP operation journal. They contain no API keys or
MCP tokens. Schedule
`python manage.py cleanup_bookmark_ai` to remove records seven days after expiry,
or use `--days N` to select retention. Use normal production `DEBUG=False` and do
not enable request-body/Authorization logging for credential-entry endpoints.

## Approval and failure behavior

### Article retrieval diagnostics and latency

Retrieval errors show the model's `failure_reason` as **OpenAI-reported**, along
with a separate description of the page-open evidence. A model reporting that
it could not read an article is distinct from a model claiming success whose
response contains no matching completed `open_page`. Diagnostics distinguish
missing actions, failed/incomplete actions, omitted URLs, and URL mismatches.
The existing verification requirement remains in place; diagnostics do not
accept unverified metadata or automatically add sites to the blacklist.

Hosted web search does not supply publisher HTTP response headers/status in its
documented output. A model mentioning robots rules, access policy, or HTTP 402
is a reported explanation, not an independently verified HTTP result. The UI
states when those details are unavailable; it does not infer x402 support from
a model-reported 402. OpenAI API HTTP errors (for example, 429) are labeled
separately from publisher responses, without exposing the provider error body.

Failure pages include the measured OpenAI request duration and returned web/MCP
tool-call counts when available. The duration includes network transit, model
processing, hosted tool discovery, and tool calls; it is not a measurement of
the article server's response time. Counts are not individual tool timings.
The app waits for the full, non-streamed response before displaying failure,
so an immediate website rejection can still take several seconds to surface.
No artificial 15-second delay or application-level analysis retry is configured.

Application instructions now ask for one article retrieval attempt first and
an immediate structured failure when the article cannot be read, before any
bookmark/tag MCP reads, alternate-page research, or retries. This is guidance to
the model, not a guaranteed early-exit deadline: hosted tool setup/model
processing can still take time. Successful analysis still requires the existing
read checks and article evidence. No additional API request or direct publisher
fetch is added by diagnostics.

Reported explanations are bounded to 600 characters, credential-redacted, and
HTML-escaped. Raw provider bodies, tool output, request headers, and secrets are
not shown or logged. Diagnostics are shown on the failure response and do not
create new database fields or retain provider responses. Deploy the updated
package and restart Django; no new migration or Lambda rebuild is required.

The review POST merges only the selected fields with the original editor draft,
validates the final values, and uses the same bookmark ModelForm as manual saves.
It reuses the owner's existing tags case-insensitively, creates approved missing
tags, and saves the bookmark and owned tag assignments directly. Read status and
visibility retain the draft selections. Unchanged fields, including legacy
publication timestamps, are preserved on existing bookmarks.

An atomic pending-to-applying transition, bookmark/tag writes, and applied status
all share one database transaction. Repeated submissions cannot apply a committed
review twice. Edits lock the existing bookmark where the database supports row
locking and check its persisted field/version/tag snapshot; stale proposals and
duplicate URLs are rejected. Any failure rolls back tag creation, assignments,
bookmark changes, and review consumption together. A failed save remains pending
and can be retried while unexpired; an applied review cannot be replayed. Existing
applying/uncertain records from the previous MCP save flow remain non-replayable
because their remote writes may have completed. No schema migration is required
to deploy this save-path change.

Only Analyze invokes OpenAI (with `store=false`) and remote MCP read tools.
Bookmark content, instructions, tags, and tool arguments used during analysis
are sent to the user's OpenAI API account. The app supplies the configured MCP
bearer header independently of the user's OpenAI key. Saving an approved proposal
has no OpenAI or MCP usage charges; it does not send edited review values back
to the model. Analysis latency and API usage are unaffected by this save change.

## Verification

```sh
python -m pip install 'Django>=3.2,<3.3' 'djangorestframework>=3.14,<3.15' 'cryptography>=3.4.8' django-appconf qrcode boto3
python -m django test dwiest.django.demos.bookmarks.test_ai dwiest.django.demos.bookmarks.test_ai_migrations --settings=dwiest.django.demos.test_bookmarks_ai_settings -v 2
```

These tests use mocked OpenAI/MCP network responses and exercise the real Django
views, ownership, CSRF, encrypted settings/session storage, review/edit/cancel,
stale/expired/repeated requests, local approval without AI credentials/network,
transaction rollback and retry, tag ownership/reuse, user-managed blacklist
normalization/matching/ownership, advisory warnings with permitted retries, persisted attempt times, and the
actual additive migrations. CI covers Python 3.7 and 3.12 with Django 3.2.
CI also runs the 11 existing Inventory/umbrella migration regression tests. AI
models live in `bookmark_ai_models.py` at the umbrella-app level so registering
them does not eagerly load the legacy Bookmarks forms/views or their models.
A live test requires your deployment values and personal API key; no live writes
or API charges are part of the automated suite.

Official API references: [remote MCP and approvals](https://developers.openai.com/api/docs/guides/tools-connectors-mcp),
[web search and page access](https://developers.openai.com/api/docs/guides/tools-web-search).

## PR 3: stored retrieval and job-service analysis

The optional job-service mode supports **saved bookmarks**. Open AI settings,
enable **Use job service**, and save retrieval settings. It defaults off so the
existing direct OpenAI/MCP path keeps working. The service uses its deployed
OpenAI key/model and `bookmark.enrichment.v1` instructions; direct AI keys, model
selection and personal/custom instructions do not override that contract.
Automatic enrichment/approval for newly created bookmarks is a later change.

### Deployment order and IAM

1. Deploy the companion URL-reuse change in `dwiest/wiest-aws-serverless` first.
   Keep existing dispatcher-stream recovery configuration if present. Configure
   `JOB_SERVICE_APPLICATION_ROLE_ARN` with the **Django execution role's IAM ARN**,
   not the GitHub deployment role, and keep the application ID stable.
   Set `JOB_SERVICE_AI_MODEL` and `JOB_SERVICE_AI_SECRET_ARN` for analysis.
2. Attach an identity policy to that Django role allowing `execute-api:Invoke`
   on the stack output `ServiceInvokeResource`. The service also checks the
   configured role. No AWS keys are placed in Django settings or the browser.
3. Install the updated Django package, run `python manage.py migrate demos`
   and `python manage.py collectstatic --noinput`, and restart web workers.
   Migration `0012_bookmark_enrichment` adds one workflow table and three settings
   fields only. It does not alter/remove legacy Bookmark or Tag tables.
4. Configure the server settings/environment below, then enable the account's
   retrieval setting. Saving enabled settings synchronizes its retention preference
   before saving local preferences; an inaccessible service produces an error.
5. Schedule the reconciliation command below to advance jobs while browsers close.

| Django setting/environment | Value |
| --- | --- |
| `BOOKMARKS_JOB_SERVICE_URL` | Stack `ServiceApiUrl`, HTTPS and ending in `/service` |
| `BOOKMARKS_JOB_SERVICE_REGION` | Stack region; falls back to `AWS_REGION`, then `us-east-1` |
| `BOOKMARKS_API_OWNER_ID` | Existing demo owner's numeric Django user ID |

The client signs requests with the server's standard boto3 AWS credential chain,
including EC2 instance-role credentials. `X-User-Reference` is derived from the
logged-in user's numeric primary key, never a browser-supplied owner. Preserve
these IDs, the service application ID and endpoint to retain access to saved jobs.
Django service jobs are separate from the Cognito browser history, even when both
accounts use the same email. The existing demo-owner restriction remains in force.
Requests reject redirects, and attempts pin their original endpoint so changing
configuration cannot submit an existing workflow to another service accidentally.

### Workflow and duplicate handling

On an existing bookmark, **Download page** saves/reuses a retrieval capture without
an AI call. Open its saved attempt and choose **Analyze saved content** when ready; it pins
that exact capture rather than retrieving the URL again. Retry analysis also
keeps the selected capture.
**Analyze** chains retrieval and analysis automatically and opens a saved proposal
for review. The user still selects, edits and explicitly approves fields/tags;
no remote job can write a bookmark. A manually changed bookmark fails the existing
stale-review check rather than being overwritten.

Django saves workflow state, source/job IDs, retrieval diagnostics and the proposal
and provenance; page text/raw bytes remain in the service. Refreshing or opening
from another signed-in browser resumes the same workflow. The editor links to its
five most recent attempts. Reopening a proposal does not make another AI call;
a pending expired review is renewed, or recreated from its saved proposal after
review-record cleanup. Approval itself remains a local database transaction.

Ordinary same-user URL submissions reuse suitable captures, including unavailable
content, across idempotency keys. Equivalent host casing, default ports, fragments
and empty paths are normalized; query strings and path semantics are preserved.
The raw-response option is part of capture identity. Adding a URL already in your
bookmarks opens your own existing record without overwriting fields; the legacy
global raw-URL uniqueness constraint is unchanged. Canonical lookup walks an
owner's URLs at current demo volume; large collections will need a stored index.

Uncertain network submissions retain stable idempotency keys. A database lease
prevents the browser and reconciliation command from advancing the same attempt
concurrently. Analysis keys include capture ID, named configuration and existing
tag names, so an unchanged analysis can be reused. **Retry download** asks for a
fresh capture (reusing a matching in-flight job); **Retry analysis** explicitly uses
a new AI operation/key and may incur provider charges. Repeated POSTs from the
same retry screen reuse the new local attempt. Worker failure, content denial and
provider failure remain visible with diagnostics; unavailable content stops the
chain before analysis. Failed analysis is never silently repeated as a new AI call.

### Advance work without an open browser

Run once per minute as the same configured application user/environment, using
the application's virtualenv and absolute manage.py path, for example:

```sh
python manage.py advance_bookmark_enrichment --limit 100
```

Each pass advances one stage per due attempt; subsequent passes poll completion.
The browser also advances every three seconds through CSRF-protected POSTs. GETs
only display state. Transient network/429/5xx failures retain state and back off
for 30 seconds; expired leases recover interrupted commands. Scheduling is an
operational deployment step, not installed automatically by this Python package.

### Retention

Each account starts with 365 days, can choose 1–36500 days, or **Keep indefinitely**.
This applies to future service jobs in its application-user namespace. Existing
captures retain their policy, and reused captures keep their original retention;
referenced sources remain protected by their retained analyses. Changing a local
setting with job mode disabled is synchronized when it is enabled again.

These settings govern remote artifacts, not local bookmark/workflow snapshots.
Existing `cleanup_bookmark_ai` review-record cleanup can still run; workflow
records retain the approved-review inputs/proposal needed for history. Remote
artifact deletion does not delete bookmarks. The service's deletion/preview API
remains available to trusted application callers; a Django artifact-management
screen and bulk history browsing are later UI work. Do not use a matching Cognito
email to infer ownership of application-created artifacts.

## Troubleshooting saved retrieval and analysis

Inspect persisted state without making AWS or job-service requests:

```sh
python manage.py advance_bookmark_enrichment --attempt ATTEMPT_UUID --status-only
python manage.py advance_bookmark_enrichment --attempt ATTEMPT_UUID
```

The command prints job IDs, last observed remote status, errors, lease and retry
times. If nothing is due it explains that terminal records, live leases and future
retry times are skipped. A 90-second local progress-check lease is separate from
the remote Lambda lease and 360-second SQS visibility timeout. Browser polling
also claims the local lease. The progress page now updates IDs and these times
while polling; no page reload is required to see newly submitted job IDs.

After correcting local credentials/configuration, Check existing analysis resumes
polling the existing analysis ID without a new provider call. If the remote job
failed, it reports that failure again. Retry analysis explicitly requests a new
analysis against the exact saved capture and can incur charges. It is available
for readable captures even when a configuration error prevented initial submission
and no analysis ID exists yet. Duplicate retry POSTs reuse the new local operation.
Service error messages/codes/diagnostics are preserved in the workflow and page.

Verify AWS identity from inside manage.py shell, not only the AWS CLI. Django
startup or systemd environment can select a different AWS_PROFILE. Cron must use
the same server settings and role as the web process. Never print credentials or
API key values while diagnosing configuration.

Search AnalysisWorkerFunction logs by analysis ID. Handled terminal failures now
log safe metadata distinguishing secret access/format, provider HTTP/transport/
output and result-storage failures even when Lambda Errors is zero. Two not-visible
SQS messages means received messages, not two active Lambda calls; console polling
also hides messages. Check the analysis queue versus its DLQ before retrying.

This update needs collectstatic and a web restart; no database migration is added.
Historical failed jobs retain their original diagnostics; new worker executions
produce the richer error metadata. Deploy the companion service change to persist
the bucket-scoped ListBucket permission and enable those diagnostics. No existing
jobs are automatically replayed and uncertain provider calls remain protected.


## PR 4 draft: new bookmarks and local history

**Migration prerequisite:** this draft adds additive preference migration 0013, but
must not be deployed to the existing server until its missing historical migration
files and applied merge through 0045 are restored and the graph is joined. Do not
run makemigrations --merge on each install, remove applied migrations, or fake the
new preferences. The server's original migration archive is needed to resolve
this prerequisite; migration names and dependencies must remain intact.

For new bookmarks in job-service mode, Download content saves a capture after the
bookmark is saved. AI enrichment implies downloading and explicitly authorizes
automatic application for that creation operation. It fills blank title,
description and publication date, adds suggestions to existing tags, and preserves
URL, read/visibility status, entered fields and tags. Both defaults start off and
can be set per account in AI settings. Individual form toggles override defaults;
ordinary manual saves, direct-AI mode, API creates and edits do not implicitly
authorize this path. Duplicate owned URLs open the existing record without
creating work or applying suggestions.

Saving and the durable attempt are committed together without external calls.
The existing reconciliation command or open progress page advances it. If the
bookmark is edited while work runs, its proposal is retained for explicit review
against the current state. Invalid or unapplicable proposals also require review.
Automatic approval uses the same transactional, owner-scoped local save as manual
approval. Applied attempts are terminal, and replayed checks cannot apply twice.
Retrying a failed analysis uses the existing manual review flow; no provider call
is automatically repeated after an uncertain result.

Job history shows 25 attempts per page, with optional bookmark filtering and
failure categories. The editor links to all attempts; bookmark listings show the
latest local workflow outcome. Individual finished attempts can be removed, or
Clear failed attempts previews up to 100 eligible failures. Confirmation is a
signed, owner-bound 15-minute snapshot. Newly created or changed attempts are not
silently included. GET requests never delete anything, and CSRF is required.
Active leases and pending proposals are protected. Removal deletes only local
attempt records, never remote artifacts, bookmark rows, or proposal records.

Failed local history defaults to 30 days, adjustable from 1 to 36500 or indefinite.
Schedule the following once daily alongside existing maintenance:

```sh
python manage.py cleanup_bookmark_enrichment
```

It uses each account's preference and removes eligible failures based on last
update time. Successful captures, applied history and pending proposals are not
aged out by this policy. Remote artifact retention remains separate (365 days by
default). To inspect local work without changing it, use the existing
advance_bookmark_enrichment --attempt UUID --status-only command.

Remote jobs retain their one-hour processing deadlines. A local workflow also has
a three-hour end-to-end deadline, including submissions that never obtained a
remote ID. It is enforced when the browser or reconciler next advances the record;
without a running reconciler, closed-browser states do not change by themselves.
BOOKMARKS_ENRICHMENT_TIMEOUT_SECONDS can configure that local deadline. Timing out
locally does not cancel remote work or delete content. Preserve the reconciliation
schedule, collect static files and restart after the migration prerequisite is met.


Per-request instructions are restored for job-service analysis. The editor's
Custom analysis instructions box passes up to 4,000 characters as authenticated
user guidance; retries against a saved capture preserve it. Instructions also
participate in local and remote idempotency and effective prompt hashing. They
cannot change the schema, enable browsing/tools or override source grounding and
source-title preservation. Direct-AI account credentials/model settings remain
separate. Deploy the companion service instructions PR before enabling this form.
