# Setup Guide

## 1. (Optional) Personalize for your team

The plugin works out of the box — skills ground field names, stages, and picklists on your org's live schema, so no configuration is required to start. For external knowledge the org can't infer (ICP, qualification framework, voice/tone, competitors, channels, thresholds), skills either infer from your org's own data or ask you once. You can provide this context via your own Claude instructions, or let skills ask as they need it.

## 2. Salesforce org prerequisites (one-time, admin)

The plugin connects via Salesforce's hosted sObject MCP servers. There are two to choose from:

- **sObject (read-write)** (the default in `.mcp.json`) - SOQL reads plus create/update (no delete). Powers everything, including the guided-write skills. Field-level security and validation rules still apply to every write, and write skills always propose-and-confirm before writing.
- **sObject Reads** - query/describe only. Every analysis skill works; the write skills (`update-opportunity`, `log-activity`, `schedule-meeting` logging, opportunity creation in `expansion-whitespace`) fall back to paste-ready checklists.

Pick one as an org decision; switching later is a one-line URL change (step 3). The exact server names available depend on your org's edition - check Salesforce's hosted MCP server list if a URL 404s. Before anyone can click Connect, a Salesforce admin needs to do two things in Setup:

**Enable the MCP service**
- Setup > search "MCP" > toggle on **Enable MCP Service**

**Create an External Client App**
- Setup > Apps > External Client Apps > New
- Callback URL: `https://claude.ai/api/mcp/auth_callback`
- OAuth scopes: `Access MCP Platform API (mcp_api)` and `Perform requests at any time (refresh_token)`
- Security: enable PKCE, enable JWT-based access tokens
- Permitted Users: All users may self-authorize
- Save, then **Manage Consumer Details** and copy the **Consumer Key**

Full reference: [Salesforce Hosted MCP Servers - Configure Claude](https://developer.salesforce.com/docs/platform/hosted-mcp-servers/guide/claude.html)

## 3. Configure the Salesforce connector

Open `.mcp.json` and replace `[PASTE-CONSUMER-KEY-FROM-YOUR-EXTERNAL-CLIENT-APP]` with the Consumer Key from step 2. Then connect **salesforce** and complete the OAuth flow - via the Connectors panel in Cowork, or `/mcp` in Claude Code.

The default (read-write) server exposes the query/describe tools the analysis skills need plus create/update for the guided-write skills. Set the client's tool permissions so write tools are **ask** (approve each write) - reads can stay allowed.

- **Read-write (default in `.mcp.json`):** `https://api.salesforce.com/platform/mcp/v1/sobject-all`
- **Read-only deployment:** `https://api.salesforce.com/platform/mcp/v1/platform/sobject-reads` - write skills automatically fall back to checklists.
- **Sandbox/scratch org:** insert `sandbox/` after `mcp/v1/` (e.g. `.../mcp/v1/sandbox/platform/sobject-reads`).
- Server names and path shapes vary slightly by server and edition - if a URL returns 404, confirm the exact path in Salesforce's hosted MCP server docs rather than guessing.
- **Different MCP server:** swap the URL for yours - skills use plain SOQL and generic create/update language rather than hard-coded tool names, so any Salesforce MCP server with query and record-write tools works (including a custom or future unified server). Write skills need create/update tools or they fall back to checklists.

## 4. Connect Calendar, Drive, and Slack

These are declared in `.mcp.json` and appear alongside Salesforce (Connectors panel in Cowork, `/mcp` in Claude Code). Click Install on each and complete OAuth.

If you see "A server with this URL already exists" - that connector is already enabled on your account from the top-level Connectors settings. You can skip it; the plugin will use the existing connection.

## 5. Verify connectors

Each skill checks for its required tools at runtime, but you can verify up front:

| Connector | Quick test |
|---|---|
| Salesforce | Ask: "query my open opportunities from Salesforce" |
| Google Drive | Ask: "find recent Google Docs with 'transcript' in the title" |
| Slack | Ask: "search Slack for messages in #general" |

If any fail, re-authenticate that MCP server before proceeding.

## 6. Read vs write posture

Analysis skills never write. The skills that can write (`update-opportunity`, `log-activity`, `schedule-meeting`'s Event logging, plus opportunity creation offered by `expansion-whitespace` and contact creation offered by `stakeholder-map`) only do so on a write-capable connector, and only this way:

1. The skill reads the current record and shows a before/after of exactly the fields that would change
2. Nothing is written until you explicitly confirm
3. Only the confirmed fields are written, one record at a time
4. The skill re-queries the record and reports what was actually saved, with a link

Your Salesforce profile, permission sets, field-level security, and validation rules are enforced by Salesforce on every write - the plugin can never do more than the signed-in user could do in the UI.

## 7. Google Drive transcript convention

`call-prep` and `call-follow-up` look for meeting transcripts in Drive. They search for:

- Files with "Transcript" or "Meeting notes" in the title
- Google Docs in folders named after accounts
- Recent Docs shared with you that mention the account name

If your org stores transcripts differently, tell the skill where to look (e.g. "transcripts are in the 'Sales Calls' shared drive").

## 8. Slack channel mapping

Skills ask which Slack channel to use when they need one, and you can point them per-run. If you'd rather set it once, you can provide channel mappings in your own Claude instructions listing where:

- Deal updates get posted (so `call-follow-up` knows where to draft the internal summary)
- Lead handoffs happen (so `lead-triage` knows where to route)
- Wins get announced

## 9. First run

Try the daily briefing:

```
/headless-360-for-sales:daily-briefing
```

You should get today's calendar with SFDC context per meeting, opps closing in the next 14 days, and a count of unread customer emails. If any section is empty or errors, that connector needs attention.

## Customizing individual skills

Every skill file has `[CUSTOMIZE]` markers for org-specific tuning - scoring weights, output format, additional fields to pull. Edit the SKILL.md directly; changes take effect on next invocation.
