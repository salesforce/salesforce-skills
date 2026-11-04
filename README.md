# Salesforce for Sales — Gemini Enterprise Plugin

The full Salesforce sales suite for Gemini Enterprise: pipeline, deals, accounts, prospecting, and daily productivity, grounded live on your org's schema through the Salesforce Headless 360 MCP server.

**Version:** 1.0.0-beta.3.1 · **License:** Apache-2.0 · **Author:** Salesforce, Inc.

The plugin provides ready-to-use skills for account executives and sales leaders. It works out of the box and can be adapted to your team's sales process. Read-only analysis respects each user's Salesforce permissions.

## What you get

An account executive starts with **daily-briefing** to see today's meetings with Salesforce account context, opportunities closing soon, warnings about stale activity, and unread customer emails. Before a call, **call-prep** produces a one-page brief covering attendees, account history, recent call notes, and suggested questions. After the call, **call-follow-up** turns a transcript into a customer email draft and an internal recap.

A sales leader uses **team-pipeline** to see a team pipeline summary, the opportunities most likely to affect the quarter, recommended actions, and focused coaching questions for each account executive.

## Package contents

| Path | Purpose |
|------|---------|
| `plugin.json` | Plugin manifest |
| `mcp.json` | MCP server configuration (`salesforce-h360` → Salesforce Headless 360) |
| `skills/` | One folder per skill, each with a `SKILL.md` |
| `LICENSE` | Apache-2.0 license |

## Setup

### Admin setup

1. Activate the Salesforce MCP Server in Setup.
2. Create a permission set for the users who should have access (optional but recommended).
3. Create and configure the External Client App (ECA) that connects Gemini Enterprise to your org through OAuth.
4. Connect Gemini Enterprise to the Salesforce MCP server defined in `mcp.json`.
5. Set tool restrictions to keep the beta read-only, if desired.
6. Roll out the plugin to your users.

### End user setup

1. Make sure the plugin is enabled for you.
2. Sign in to the Salesforce connector.

### Optional connectors

Salesforce is the only connector declared in `mcp.json`. Email, calendar, Slack, and document sources are optional: connect them separately when you want that extra context. Core Salesforce workflows continue with the Salesforce data available to the signed-in user, whichever optional connectors are connected.

## Skills

Ask in plain language, or name a skill when you want a specific workflow.

| Area | Skills |
|------|--------|
| **Daily productivity** | daily-briefing, calendar-events, inbox-sweep, schedule-meeting, weekly-wrap, find-internal-answer, voice-profile |
| **Accounts** | account-context, account-plan, account-tiering, customer-health, expansion-whitespace, stakeholder-map, executive-movement |
| **Prospecting & leads** | research-prospect, lead-triage, draft-outreach, assign-target-to-sdr, event-invite-list |
| **Calls & activity** | call-prep, call-follow-up, summarize-conversation-transcript, query-activity-history, log-activity, customer-voice |
| **Deals** | deal-review, deal-advance-gap, deal-signals, close-plan, handle-objection, renewal-radar, win-loss-review |
| **Pipeline & forecast** | pipeline-review, team-pipeline, forecast-narrative, deal-slip-scenario, rep-context, salesforce-hygiene-check |
| **Presentation** | using-display-widget |

See each skill's `SKILL.md` under [`skills/`](./skills) for details.

Salesforce write actions (for example log-activity, schedule-meeting, assign-target-to-sdr) need a write-capable connection. With a read-only connection, read workflows remain available, and write-dependent skills give manual guidance where supported.

## Design principles

* **Use existing access; write only after approval.** Read-only skills do not create or modify Salesforce records.
* **Draft before sending.** Outreach and follow-up emails are created as drafts for review rather than sent automatically.
* **Stay grounded in records.** Skills link the Salesforce records they discuss and preserve queried values.
* **Work with your Salesforce configuration.** Skills use the schema, field names, stages, and permissions available in your org.
* **Continue when optional context is unavailable.** If a transcript or optional service is unavailable, the skill asks for the missing input or proceeds with the available Salesforce context and flags the limitation.

## Contributing & security

See [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [SECURITY.md](SECURITY.md).
