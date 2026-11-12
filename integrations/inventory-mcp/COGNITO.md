# Cognito OAuth for Inventory MCP

This adds a dedicated confidential OAuth client to the existing
`us-east-1_AA8l2prNL` pool, using its current hosted login domain:
`https://us-east-1aa8l2prnl.auth.us-east-1.amazoncognito.com`.
It creates a resource server whose identifier equals `PUBLIC_MCP_URL`, with
`<PUBLIC_MCP_URL>/read` and `<PUBLIC_MCP_URL>/write` scopes. It does not modify existing voicemail/messaging clients, domains, or users.
Check for an existing resource server with the exact MCP URL before deployment; if one
already exists, reconcile its ownership rather than creating a duplicate.

The new flow is browser/ChatGPT -> Cognito login -> Inventory MCP -> Django API.
Django Basic Auth stays server-side. This remains a **single Django account**
integration: only explicitly allowed Cognito `sub` values can access it, and they
all operate on that configured Django account. No automatic Cognito-to-Django
user mapping is implemented. Both Inventory scopes are required for the whole
MCP connection, including reads; this version does not offer read-only OAuth grants.

## 1. Get the exact ChatGPT callback URL

In ChatGPT's custom MCP plugin configuration, enter the Inventory server URL and
choose OAuth with predefined client credentials. Copy the exact redirect URI
shown in the server's management page. Use that exact value below. Do not guess
or use wildcards. Modern callback URLs can include a connection-specific ID;
the stable `connector_platform_oauth_redirect` URL is not universally applicable.
If the client must exist before configuration can be completed, create it with
a callback URL you control, then update the stack with the exact ChatGPT callback
before attempting sign-in. A placeholder callback is not a working connection.

## 2. Create the Cognito resources from CloudShell

Run from `integrations/inventory-mcp` in a checkout of this PR, using us-east-1:

```sh
aws cognito-idp list-resource-servers --region us-east-1 \
  --user-pool-id us-east-1_AA8l2prNL \
  --query 'ResourceServers[].Identifier'

read -r -p 'Exact ChatGPT callback URL: ' INVENTORY_CALLBACK_URL
aws cloudformation deploy --region us-east-1 \
  --stack-name inventory-mcp-cognito \
  --template-file cognito-client.template.json \
  --parameter-overrides "CallbackURLs=$INVENTORY_CALLBACK_URL"

aws cloudformation describe-stacks --region us-east-1 \
  --stack-name inventory-mcp-cognito --query 'Stacks[0].Outputs'
```

Get the client secret through Cognito console -> pool -> App clients ->
`inventory-mcp-chatgpt`. Enter the client ID and secret into ChatGPT's OAuth
configuration; never put the secret in git, prompts, screenshots, or frontend code.
The CloudFormation outputs intentionally omit the secret. Cognito handles the
code exchange and refresh tokens; the MCP Lambda does not need that secret.
Authorization code with S256 PKCE is used, not implicit or client credentials.
No DCR/CIMD registration endpoint is implemented; use the predefined client.

If your pool uses managed login v2 and requires a branding configuration for a
new client, configure it in Cognito's Login pages/Managed login settings before
testing authorization. Reuse the pool's existing login design as appropriate.

## 3. Deploy the updated Lambda and configure OAuth

Build with Python 3.12, **not the EC2 Django Python 3.7 environment**:

```sh
python3.12 -m venv .venv312
.venv312/bin/pip install -r requirements.txt
.venv312/bin/python -m unittest discover -s . -v
.venv312/bin/python build.py
aws lambda update-function-code --region us-east-1 \
  --function-name inventory-mcp-lambda \
  --zip-file fileb://dist/inventory-mcp-lambda.zip
```

In Lambda -> Configuration -> Environment variables, preserve existing values
and add these. Do not replace the entire environment with a partial CLI update.

| Variable | Value |
| --- | --- |
| `AUTH_MODE` | `cognito` |
| `COGNITO_USER_POOL_ID` | `us-east-1_AA8l2prNL` |
| `COGNITO_DOMAIN` | `https://us-east-1aa8l2prnl.auth.us-east-1.amazoncognito.com` |
| `COGNITO_CLIENT_ID` | Client ID from the stack |
| `COGNITO_ALLOWED_SUBJECTS` | Your Cognito user's `sub`; comma-separated if more than one |
| `PUBLIC_MCP_URL` | `https://nqmt48bmv7.execute-api.us-east-1.amazonaws.com/api/inventory-mcp` |

Find your `sub` in the Cognito console user attributes, or:

```sh
read -r -p 'Cognito username: ' INVENTORY_COGNITO_USERNAME
aws cognito-idp admin-get-user --region us-east-1 \
  --user-pool-id us-east-1_AA8l2prNL --username "$INVENTORY_COGNITO_USERNAME" \
  --query 'UserAttributes[?Name==`sub`].Value' --output text
```

Keep `DJANGO_API_BASE_URL`, `DJANGO_API_AUTHORIZATION`, `PUBLIC_HOST`, and `MCP_PATH`
configured as before. The user pool and app client IDs are configuration, not
credentials. In `cognito` mode the old static `MCP_AUTH_TOKEN` is **not accepted**.
To roll back authentication, set `AUTH_MODE=static` and retain the existing static
token; new OAuth connections will then stop working. There is no silent fallback.

JWT validation checks signature against the pool's cached JWKS, issuer,
expiration, issued-at, token_use=access, client_id, allowed subject, both scopes,
and exact audience equal to `PUBLIC_MCP_URL`. ID tokens, other clients, and other
pool users are rejected. Access tokens must be resource-bound: the OAuth client
must send `resource=<PUBLIC_MCP_URL>` in its authorization request. Cognito's
managed OAuth login can include this in `aud`; ordinary SDK/password-login tokens
without that audience are rejected. Refresh preserves the original audience.

## 4. Add public discovery routes to the existing API Gateway

Leave route authorization `NONE` on the MCP route: Lambda performs validation and
returns the OAuth discovery challenge. A gateway authorizer that blocks first
would hide that challenge. Add **all three GET routes**, integrated with the same
Lambda using payload format 2.0 and the auto-deployed `$default` stage:

```text
GET /.well-known/oauth-protected-resource/api/inventory-mcp
GET /.well-known/oauth-protected-resource
GET /.well-known/oauth-authorization-server
```

The metadata endpoints are intentionally public; they contain no secrets or
inventory data. Ensure the function's API Gateway invoke permission covers these
GET routes (a permission restricted to POST /api/inventory-mcp will not).
If using CloudFront later, route the discovery paths to this API too, disable
caching, and set `PUBLIC_MCP_URL` to the exact externally used MCP URL.

Cognito's actual pool discovery currently omits
`code_challenge_methods_supported`. ChatGPT requires `S256`, so the Lambda
publishes a small authorization-server metadata facade at the API origin. It
advertises Cognito's supported S256 flow, existing authorize/token endpoints,
and confidential-client basic/post methods. The facade issuer is the API origin;
JWT verification separately uses the real Cognito pool issuer. It does not proxy
credentials, issue tokens, claim RFC 9207 support, or advertise DCR/CIMD.
Use the exact ChatGPT-provided callback URL for this configuration.

## 5. Verify and connect

```sh
curl -i https://nqmt48bmv7.execute-api.us-east-1.amazonaws.com/.well-known/oauth-protected-resource/api/inventory-mcp
curl -i https://nqmt48bmv7.execute-api.us-east-1.amazonaws.com/.well-known/oauth-authorization-server
curl -i -X POST https://nqmt48bmv7.execute-api.us-east-1.amazonaws.com/api/inventory-mcp
```

The metadata reads should return 200. The unauthenticated POST should return 401
with `WWW-Authenticate: Bearer resource_metadata="..."`.

Finish ChatGPT plugin setup with the predefined client ID/secret, sign in through
Cognito, and first ask it to list inventory without changing anything. Only after
that works, upload a grocery photo and ask for proposed additions, with approval
before writes. OAuth must request both Inventory scopes and resource binding.

Codex CLI can also use OAuth with a suitable registered callback/client. Its old
static-token configuration will not work once OAuth mode is enabled; retain the
static mode until you're ready to test the browser cutover.

This PR prepares resources and code. It has not created the AWS client, changed
API Gateway, or validated a live ChatGPT OAuth exchange. Those require deployment
and the exact callback URI from your ChatGPT connection.

## References

- https://developers.openai.com/plugins/build/auth
- https://docs.aws.amazon.com/cognito/latest/developerguide/using-pkce-in-authorization-code.html
- https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-define-resource-servers.html


## Fixing an existing short-identifier deployment

Cognito resource binding requires requested custom scopes to belong to the
resource being requested. The old `inventory/read` and `inventory/write` scopes
belong to `inventory`, so they cannot be requested with the full MCP URL as the
`resource`. The resource identifier, custom scope prefixes, OAuth discovery and
JWT scope checks must all agree. Do not disable audience validation.

After merging this fix:

1. Pull the current source. Update the existing `inventory-mcp-cognito` stack
   with the revised template and your existing exact callback URL. The new
   `PublicMcpUrl` parameter defaults to the current API Gateway MCP URL; override
   it if your configured `PUBLIC_MCP_URL` differs. Keep that URL identical,
   including path and trailing-slash policy.
2. Review the change set: the resource server identifier changes (replacement),
   and the existing app client receives the URL-prefixed scopes. The template
   retains the old resource server during replacement to avoid a dependency race
   while updating the client's allowed scopes. The old server can remain unused;
   remove it only after confirming no client references its scopes.
3. Rebuild/upload the Lambda ZIP to publish discovery and validate the new
   URL-prefixed scopes. Leave `PUBLIC_MCP_URL` unchanged.
4. Refresh the ChatGPT plugin's tools/metadata or recreate the connection so it
   no longer requests the old short scopes. Sign in again to obtain a new token.

For the current endpoint the required custom scopes are:

```text
https://nqmt48bmv7.execute-api.us-east-1.amazonaws.com/api/inventory-mcp/read
https://nqmt48bmv7.execute-api.us-east-1.amazonaws.com/api/inventory-mcp/write
```

The resource and JWT audience remain the MCP URL without `/read` or `/write`.
The client ID/secret should remain unchanged; this update modifies its allowed
scopes, not the client identity. Check stack outputs after deployment.
