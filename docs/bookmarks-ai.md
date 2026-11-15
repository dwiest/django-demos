# AI-assisted bookmarks

The bookmark editor now supports **Analyze -> review/edit -> approve -> MCP**.
The OpenAI agent retrieves the article using Responses API web search, reads the
existing bookmark/tags through remote MCP, and returns a structured proposal.
Analysis exposes only four explicit read tools. No bookmark or tag is written
until the user submits the review page. Normal manual bookmark saves still work
when AI is unconfigured; the application never falls back to a shared OpenAI key.

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
only the new migration. Do not generate unrelated schema changes for this feature.

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
`BOOKMARKS_AI_TIMEOUT` defaults to 120 seconds **per OpenAI request**. Analyze and
Apply are synchronous server requests; set Gunicorn/uWSGI, HAProxy, and any CDN
timeouts accordingly. Applying several new tags can involve multiple requests;
worker termination leaves a proposal non-replayable rather than retrying writes.
For larger workloads, move orchestration to a job queue with polling.

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
   instructions, and click **Analyze**. Page/task/tool content cannot authorize
   writes. Failed article access, MCP errors, or invalid metadata produce a clear
   error and leave the original form/data intact.
4. Review the current form and proposed fields side by side. Check which values
   to use, edit any proposed values, and review the final tag names. A removed
   name removes that assignment; a new name authorizes creating that tag. Read
   status and visibility preserve the editor's selections, displayed on review.
5. Approve to save through MCP, or cancel without changes. Proposals expire in
   30 minutes and belong only to the initiating account.

Review records retain snapshots, proposals, sources, approved values, and a short
operation journal; they contain no API keys or MCP tokens. Schedule
`python manage.py cleanup_bookmark_ai` to remove records seven days after expiry,
or use `--days N` to select retention. Use normal production `DEBUG=False` and do
not enable request-body/Authorization logging for credential-entry endpoints.

## Approval and failure behavior

Apply builds a fixed operation from the final user-approved fields. The agent
prepares one MCP call at a time with native approval required. Django checks the
server, tool, and **complete arguments** against the approved operation before
sending an `mcp_approval_response`. Execution disables further tool selection;
unexpected calls or additional approvals are never automatically accepted.
Personal/task instructions are not included in this execution phase.

New bookmarks use `create_bookmark` with approved tag names (including creation
of missing tags inside the backend create operation). Existing bookmarks reuse
owned tag IDs, create approved new tags through MCP if needed, then call
`update_bookmark` with only changed fields. Django verifies the resulting saved
record against the approved values. It never performs a direct ORM bookmark/tag
write on the AI path.

An atomic pending-to-applying transition prevents resubmitting the **same** review.
Edits check persisted bookmark/version/tag snapshots before execution. MCP/REST
operations are separate transactions: other clients can still race an update,
and a tag can be created before a subsequent bookmark call fails. Timeouts or
ambiguous results mark the proposal uncertain and prevent replay. The UI shows
confirmed operations and asks the user to check saved data before starting over.
After a worker crash, an applying record also cannot be resubmitted. This first
version does not offer distributed transactions or unattended retries.

Write preparation/approval uses stored Responses IDs (`store=true`); analysis
uses `store=false`. Bookmark content, instructions, tags, and tool arguments are
sent to the user's OpenAI API account. The app sends the configured MCP bearer
header on each remote-MCP request, independently of the user's OpenAI key.

## Verification

```sh
python -m pip install 'Django>=3.2,<3.3' 'djangorestframework>=3.14,<3.15' 'cryptography>=3.4.8' django-appconf qrcode boto3
python -m django test dwiest.django.demos.bookmarks.test_ai dwiest.django.demos.bookmarks.test_ai_migrations --settings=dwiest.django.demos.test_bookmarks_ai_settings -v 2
```

These tests use mocked OpenAI/MCP network responses and exercise the real Django
views, ownership, CSRF, encrypted settings/session storage, review/edit/cancel,
stale/expired/repeated requests, native argument-checked approval, partial writes,
and the actual additive migration. CI covers Python 3.7 and 3.12 with Django 3.2.
A live test requires your deployment values and personal API key; no live writes
or API charges are part of the automated suite.

Official API references: [remote MCP and approvals](https://developers.openai.com/api/docs/guides/tools-connectors-mcp),
[web search and page access](https://developers.openai.com/api/docs/guides/tools-web-search).
