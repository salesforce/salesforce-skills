# Salesforce for Sales

The Salesforce sales suite for Grok Bot and Cursor: pipeline, deals, accounts, prospecting, and
daily productivity, grounded live on your org's schema through the Salesforce Headless 360 MCP
server.

Every call runs as the signed-in Salesforce user, so field-level security, object permissions,
and sharing rules apply as they do in Salesforce.

## Admin setup

Setup takes a Salesforce admin and a Cursor team admin. It is done once per team; after that,
each user signs in to Salesforce on first use.

### 1. Activate Headless 360 (Salesforce admin)

In Salesforce Setup, open **MCP Servers** and activate **Headless 360**. The org needs API
version 67.0 or later.

### 2. Create an External Client App (Salesforce admin)

In Setup, open **External Client App Manager** and select **New External Client App**.

- **Distribution State:** Local.
- **Enable OAuth:** on.
- **Callback URLs**, one per line:

  ```
  https://www.cursor.com/agents/mcp/oauth/callback
  https://www.cursor.com/bot/mcp/oauth/callback
  grokbot://mcp/oauth/callback
  http://localhost:8787/callback
  ```

  Salesforce rejects `http://127.0.0.1` callbacks, so leave that one out.
- **OAuth Scopes:** `Access the Salesforce API Platform (mcp_api)` and
  `Perform requests at any time (refresh_token, offline_access)`.
- **Security:** turn on **Require Proof Key for Code Exchange (PKCE)** and
  **Require secret for Web Server Flow**.
- **Issue JSON Web Token (JWT)-based access tokens for named users:** on.
- **Flow Enablement:** leave every option off.

Save, then on the app's **Policies** tab:

- **Permitted Users:** All users may self-authorize (or admin-approved users, with the right
  profiles or permission sets assigned).
- **IP Relaxation:** Relax IP restrictions.
- **Refresh Token Policy:** keep refresh tokens valid until revoked, or set an idle expiration
  if your org requires one.

On the **Settings** tab, open **Consumer Key and Secret** and copy both. A new app can take up to
30 minutes before Salesforce accepts its Consumer Key.

### 3. Configure the plugin (Cursor team admin)

In the Cursor dashboard, open the team marketplace, select **Salesforce for Sales**, and select
**Configure**. Fill in:

| Field | Value |
| --- | --- |
| Salesforce MCP server URL | Production and Developer orgs: `https://api.salesforce.com/platform/mcp/v1/platform/headless-360` (the default). Sandbox and scratch orgs: `https://api.salesforce.com/platform/mcp/v1/sandbox/platform/headless-360`. |
| Salesforce Consumer Key | The Consumer Key from step 2. |
| Salesforce Consumer Secret | The Consumer Secret from step 2. |

Users then sign in to Salesforce the first time a skill calls the server.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `invalid_client_id` at sign-in | The External Client App is new. Wait up to 30 minutes, then retry. Otherwise check the Consumer Key and that the URL matches the org type (sandbox orgs use the sandbox URL). |
| `redirect_uri_mismatch` | A callback URL is missing from the External Client App. Add all four from step 2. |
| `invalid_client` or a secret error | The Consumer Secret is wrong or missing, or **Require secret for Web Server Flow** is off. |
| "JWT Token is required" | Turn on JWT-based access tokens for named users in the External Client App. |
| Signed in, but tools fail with a permission error | Headless 360 is not activated, or the user lacks API access. Check step 1 and the user's profile or permission sets. |
| `OAUTH_APP_BLOCKED` or "user is not admin approved" | Set **Permitted Users** to self-authorize, or assign the user a profile or permission set approved for the app. |

The setup follows the pattern of Cursor's own
[Salesforce Headless 360 plugin](https://github.com/cursor/plugins/tree/main/third_party/salesforce-headless-360).
