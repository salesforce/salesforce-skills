# Sales Team Plugin

A general-purpose Claude plugin for sales teams - use it in Claude Cowork, Claude Code, or anywhere Claude supports plugins. It runs on the tools your team already uses - Salesforce, Google Drive, and Slack. No new systems to learn. Ask in plain English, get account context, call prep, pipeline reviews, and drafted outreach grounded in your own CRM data.

This is the external edition of the sales toolkit Anthropic's own sales team runs every day, generalized for any B2B sales org. It ships as a foundational layer that works out of the box, and it's built to take further custom work - your company profile lives in config, every skill has `[CUSTOMIZE]` markers, and teams typically extend it with role-specific skills (startup sellers, enterprise, customer success, sales leaders) on top of this base.

## What you get

A rep opens their laptop and types `/salesforce-for-sales:daily-briefing` - they get today's meetings with the SFDC account context for each one, the opps closing in two weeks with stale-flag warnings, and which customer emails are waiting. Before a call they type `/salesforce-for-sales:call-prep` and get a one-page brief: who's in the room, what happened on the last call (pulled from the Drive transcript), and what to ask. After the call, `call-follow-up` turns the transcript into a email draft to the customer and a Slack summary for the team.

A leader types `/salesforce-for-sales:team-pipeline` and gets the rollup, the deals that decide the quarter (each with a concrete "do this"), and Monday questions per rep grounded in their actual opps - not generic coaching prompts.

Everything reads from your Salesforce freely. Writes are opt-in and gated: if your admin connects the read-write Salesforce server, `update-opportunity` and `log-activity` can apply stage changes, close-date moves, and activity logs - always proposed first, written only after you confirm, verified with a record link. On a read-only connector, the same suggestions come back as a checklist you apply yourself.

## Quick start

**1. Install**
```
/plugin marketplace add <this-repo>
/plugin install sales
```

**2. Connect Salesforce**

The plugin talks to Salesforce through the Headless 360 MCP server - reads via `dispatch_readonly`, guided create/update via `dispatch`. A Salesforce admin first enables the MCP Service and creates the `Headless_360` External Client App (one-time - see [SETUP.md](SETUP.md)). Paste that app's Consumer Key into `.mcp.json`, then click Connect. Calendar, Drive, and Slack connect the same way - the Connectors panel in Cowork, or `/mcp` in Claude Code - just OAuth each one.

**3. Try it**

```
/salesforce-for-sales:daily-briefing
```

Full setup walkthrough in [SETUP.md](SETUP.md).

## Skills

### Daily flow (reps)

| Skill | What it does |
|---|---|
| `daily-briefing` | Morning rundown: today's meetings with account context, opps closing soon, unread customer emails |
| `call-prep` | Pre-call brief: attendees, account history, prior call notes from Drive, suggested questions |
| `call-follow-up` | Turn a Meet transcript into a customer follow-up draft and an internal Slack summary |
| `inbox-sweep` | Batch-process unread customer emails - classify, prioritize, draft replies |

### Account work (reps)

| Skill | What it does |
|---|---|
| `account-context` | 360 view of an account across SFDC, email, Drive, and Slack |
| `research-prospect` | Company and contact research from web sources, scored against your ICP |
| `stakeholder-map` | Who the players are - roles, influence, sentiment, who's missing, and your access path to them |
| `draft-outreach` | Personalized cold or warm outreach drafted into email |
| `lead-triage` | Score and route an inbound lead against your ICP and qualification framework |
| `account-tiering` | Tier your book by ICP fit and engagement to prioritize where to spend time |
| `account-plan` | View or create an AccountPlan record in SFDC - fetches and renders the existing plan, or gathers strategic context and creates a new one |

### Pipeline (reps)

| Skill | What it does |
|---|---|
| `deal-review` | Deep-dive on one opp: signal-adjusted health score, qualification gaps, next actions |
| `deal-advance-gap` | Forward-looking gap check: exactly what's missing to advance one deal, and the shortest path to it |
| `pipeline-review` | Stage-by-stage health: coverage, aging, at-risk deals |
| `forecast-narrative` | Commit / best-case / pipeline narrative for your forecast call, with optional forecast-category corrections |
| `deal-slip-scenario` | "What if this deal slips?" - quota impact, coverage change, and the substitute pipeline needed |
| `deal-signals` | Proactive sweep of the book: quiet deals, slips, champion changes, renewal windows, competitor mentions - built to run on a schedule |
| `sfdc-hygiene-check` | Audit your opps for missing fields and stale dates - outputs a fix checklist |
| `weekly-wrap` | Friday summary: closed, moved, slipped, Monday lookahead - drafts to team Slack |

### Negotiate & close (reps)

| Skill | What it does |
|---|---|
| `close-plan` | Business case in the customer's terms plus the mutual action plan dated back from signature |
| `handle-objection` | Work a live objection or competitive threat - grounded in your own win/loss history and customer quotes |

### Retain & grow (reps / AMs)

| Skill | What it does |
|---|---|
| `renewal-radar` | Upcoming renewals with timing, risk, and uplift potential - flags the risky ones while there's still time |
| `expansion-whitespace` | Owned vs. possible per account - evidence-backed expansion plays, ranked |
| `customer-health` | Health check and QBR prep: relationship, engagement trend, value delivered, risks |

### Acting on it (guided writes)

| Skill | What it does |
|---|---|
| `update-opportunity` | Push stage, move close date, set next steps or forecast category - proposed first, written only after you confirm, verified with a link |
| `log-activity` | Log a call, meeting, or email exchange as a completed Task on the right account/opp/contact - drafted from your notes or a transcript, confirmed before writing |
| `schedule-meeting` | Find a time, draft or send the invite, and log the Event in Salesforce |
| `calendar-events` | Pull Event records from Salesforce for a time range - see meeting history, identify gaps, export for analysis |
| `query-activity-history` | Query Task and Event history with flexible filters - activity volume, contact coverage, historical analysis |
| `assign-target-to-sdr` | Hand a Contact or Lead to an Agentforce Lead Nurturing agent (formerly SDR) for qualification and email outreach - lists active agents, confirms the pairing, then invokes the standard action |

Salesforce writes require the read-write server (the default in `.mcp.json` - see [SETUP.md](SETUP.md)); on a read-only connector the SFDC write step falls back to a paste-ready checklist (`schedule-meeting`'s calendar and email steps work either way).

### Knowledge

| Skill | What it does |
|---|---|
| `find-internal-answer` | Find the policy, approver, latest doc, or the teammate who's done it before - from your team's Drive, Slack, and email, with the source linked |

### Leader

| Skill | What it does |
|---|---|
| `team-pipeline` | Per-rep scoreboard, the deals that decide the quarter (each with a "do this"), Monday questions per rep |
| `rep-context` | Catch-up on one rep before a 1:1 - pipeline, activity, where they need help |
| `customer-voice` | Pull verbatim customer quotes on a topic from Drive transcripts and email - receipts for your next exec conversation |
| `win-loss-review` | Find patterns across closed opps - where losses die, what wins have in common |

### Setup

| Skill | What it does |
|---|---|
| `voice-profile` | Mine your email sent folder to learn your writing style, save to config so all drafts match it |

### Agents (for deeper work)

| Agent | Use it for |
|---|---|
| `account-researcher` | Thorough multi-source research before a strategic account engagement |
| `deal-analyzer` | Adversarial second opinion on whether a deal is real |
| `pipeline-doctor` | Diagnose why pipeline is stalling - finds the systemic pattern, not just the stale list |

## How it uses your tools

| Connector | Used for |
|---|---|
| **Salesforce** | Accounts, contacts, opportunities, leads, activities via the Headless 360 MCP server - reads through `dispatch_readonly`, guided create/update through `dispatch`. For a read-only deployment, disable the `dispatch` write tool and the write skills become checklists. Every write is proposed, confirmed, and verified - and your org's field-level security still applies underneath. |
| **Gmail** | Search customer threads, read correspondence, create reply drafts (never sends) |
| **calendar** | Today's meetings, attendees, descriptions |
| **Google Drive** | Meet transcripts, account plans, proposals |
| **Slack** | Internal account chatter, deal-desk threads, draft team summaries |

## Design principles

- **Reads freely, writes only with your approval.** Analysis skills never touch your CRM. The skills that can write propose the exact change, write only what you confirm, and verify with a record link - and they only work at all if your admin connected the write-capable server. Your Salesforce permissions and field-level security are always the floor.
- **Drafts, not sends.** Outreach and follow-ups land in email drafts. You review and send.
- **Grounded in records.** Every built skill receives the shared grounding and record rules, so outputs link the records they discuss and quote values exactly as queried.
- **Works out of the box, personalization optional.** Skills ground field names and stages on your org's live schema, so nothing needs configuring to start. For external knowledge (ICP, qualification framework, voice/tone, competitors, channels, thresholds), skills infer from your org's own data or ask you once. You can provide this context via your own Claude instructions.
- **Degrades gracefully.** Missing a transcript? Skill prompts for a paste. Read-only connector? Write skills become checklists. No SFDC match? Proceeds with web research and notes the gap.

## Customizing

Every skill file has `[CUSTOMIZE]` markers for org-specific tuning - scoring weights, thresholds, output format, extra fields to pull. Edit the SKILL.md directly and changes take effect on next run. See [SETUP.md](SETUP.md) for the full guide.

Treat this plugin as the foundation, not the ceiling. The pattern that works: every seller starts from this shared base, then the expert in each function (startup sales, enterprise, customer success, sales leadership) builds a role-specific plugin on top of it - new skills, different scoring, their own output formats. New hires install the plugin on day one and inherit the team's workflows; the custom work is where it gets shaped to how your org actually sells.
