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
