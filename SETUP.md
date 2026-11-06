# Setup: Salesforce, MCP Apps, and optional connectors

Salesforce reads use Headless 360 `dispatch_readonly`. Widget-bearing skills also use
`display_widget` for widget-first output and keep a text fallback.

## Declared MCP servers

`mcp.json` declares these hosted endpoints:

| Server | URL | Purpose |
|---|---|---|
| `salesforce-h360` | `https://api.salesforce.com/platform/mcp/v1/platform/headless-360` | Salesforce reads and MCP Apps widgets |
| `slack` | `https://mcp.slack.com/mcp` | Optional internal context and draft Slack content |

Whether a client loads a bundled `mcp.json` is host-specific. Amazon Quick connector mapping,
plugin loading, and MCP Apps rendering are not verified by this package. Do not treat the
package declaration as proof of Quick support.

## Headless 360 tools

| Tool | Role in the skills |
|---|---|
| `dispatch_readonly` | Required for the documented Salesforce GraphQL, SOQL, and UI API reads. |
| `display_widget` | Required for widget-first output on a compatible MCP Apps host. |
| `discover`, `describe` | Not used by the normal skill workflows; the skill rules tell the agent not to call them. |
| `dispatch` | General REST tool that can mutate data. Write skills (`account-plan`, `assign-target-to-sdr`, `log-activity`, `schedule-meeting`, `update-opportunity`) call it once each, only after the user's explicit yes; `summarize-conversation-transcript` calls the read-only `getConversationTranscript` action through it. With only `dispatch_readonly`, `log-activity` and `schedule-meeting` return paste-ready text, `update-opportunity` gives a manual checklist, and `assign-target-to-sdr` stops. |

Real authorization belongs at the Salesforce permission and tool layer and in the client. For a
read-only deployment, use least privilege and disable the tools the deployment does not need. Do
not disable `display_widget` if you expect widget-first behavior. A client-side read-only policy
might disable `dispatch` while allowing `dispatch_readonly` and `display_widget`; exact controls
depend on the client and org policy.

A host with a differently named Salesforce read connector must map the same URL and query
contract to that connector.

## Salesforce OAuth setup

1. Activate the Salesforce MCP Server in Setup.
2. Create a permission set for the intended users.
3. Create an External Client App (ECA).
4. Add the `mcp_api` scope and require PKCE.
5. Connect the client and apply least-privilege tool and record permissions.

The package cannot contain a Consumer Key or secret. A client that does not support dynamic
registration must be configured separately with the ECA Consumer Key. For Kiro, define the
server in workspace or user MCP settings and set `oauth.clientId`. Use a public PKCE client and
register the exact `http://localhost:<port>/...` redirect URI the client sends.

## MCP Apps renderer compatibility

Headless 360 advertises `ui://widget/salesforce-widget-renderer` and returns each submitted
widget in both `structuredContent.widgetDefinition` and `_meta["salesforce/uiMetadata"]`.

Host sandbox behavior matters. A renderer sandbox on a separate origin with
`allow-scripts allow-same-origin` completes the handshake and renders; the official basic host
and MCP Inspector use an opaque-origin path that leaves this renderer at `Loading…`. If a client
cannot mount the renderer, the skill uses its text fallback.

## Slack, email, calendar, and documents

Slack is the only optional non-Salesforce server declared in `mcp.json`. Email, calendar, and
document tools must be configured separately when a host supports them. Draft workflows remain
draft-only until a user approves the exact message and destination. A missing optional connector
leads to the skill's fallback behavior, not fabricated evidence.
