---
name: daily-briefing
description: Morning rundown for a sales rep - today's meetings with account context, opportunities closing soon, and unread customer emails. ALWAYS trigger immediately (no confirmation) when the user asks "what does my day look like", "daily briefing", "prep me for today", "morning rundown", or runs /daily. This is a time-sensitive morning routine skill combining meetings + pipeline + inbox. Do NOT use for a schedule-only or calendar-only request ("what's on my calendar", "show my meetings", "this week's schedule") - that's calendar-events.
model: claude-sonnet-4-6
effort: medium
---
<!-- global-rules-bootstrap -->
# Global Rules

- **Execute silently between tool calls.** Do not output planning, progress, transition, waiting, or tool-result narration between calls. Execute tool calls silently and proceed directly to the next call. Parallelize independent tasks by batching tool calls into one turn whenever possible. Before the final output, speak only when the skill explicitly requires user input, approval, an exact notice, or material error/blocked reporting. Do not invent checkpoints.
- **Keep the final output concise.** Return only the requested result or deliverable. Omit process recaps, tool-call details, redundant preambles or conclusions, and data already shown in a widget.
- **⛔ WIDGET OUTPUT ONLY after data assembly.** Once all queries return, output only this skill's exact required pre-widget notice, then immediately call `display_widget` — no summaries, other transitions, or narration. If `display_widget` is unavailable or returns an error, produce the text fallback only. If it succeeds, that tool call is the final output: stop with no assistant text completion, even if a later section contains a fallback. The exceptions above do not apply after success.
- **Ground dynamic or custom relationship and field names before relying on them.** Fixed standard fields that this skill explicitly marks as requiring no grounding need no extra grounding call. On a name error, use the skill's documented grounding path when present; otherwise report the error instead of guessing or re-firing the same shape.
- **Cite every value exactly as queried**; never fabricate; distinguish a blank value from a value that was not queried. Link each Salesforce record inline: `https://[instanceUrl]/lightning/r/[SObjectType]/[Id]/view`.
- **Show human labels, never API/field literals.** In anything the user sees, print each field's grounded `label` (for example, "Deal Risk", not `Deal_Risk__c`) and record Names, never raw Ids or `__c` API names.
- **Empty `MINE` scope → fail fast, then ask which scope.** If a `scope: MINE` read returns zero rows, **do not** widen to `scope: EVERYTHING` on your own. Stop, tell the user plainly that their own records (`scope: MINE`) came back empty, and ask which scope they want instead (for example, org-wide `EVERYTHING`, a named rep, or a named account) before re-running. Never invent records, and never silently fall back to org-wide.
- **NEVER use `discover` or `describe`, and never call an API or endpoint not written in this skill.** Every Salesforce URL you need is in the skill. Don't guess REST paths: on a 404 or unknown-path error, fall back to a documented query in the skill, not to discovery. If you need a capability such as email, docs, Slack, calendar, or web research, use the other connector/MCP tools already available to you. Endpoint guessing and discovery add needless round-trips. Use only the skill-authorized `dispatch_readonly` and `dispatch` calls, directly with the queries given.
- **NEVER assume the MCP connector status is accurate without checking first**; MCP connector status often incorrectly reports that it is not connected or needs to re auth. ALWAYS check this on your own before surfacing to the user for action. ALWAYS attempt to reconnect on your own before interrupting the flow to ask the user to do it. Do it yourself.
# Rules:

- Parallelize everything independent. This is a morning routine — speed matters; fire the running-user lookup, calendar, closing-soon, and inbox in ONE turn.

# Daily Briefing

Ground → (calendar + closing-soon + inbox, ALL in ONE turn) → match meetings to accounts (one batched turn) → flag → output. This is today's rundown, not a pipeline review — closing-soon is a small bounded set, so pull concrete rows, don't aggregate.

## 1. Ground (hardcoded — Opportunity only; fire with the step-2 batch)

Ground **only Opportunity** — it always exists (naming a missing object fails the whole call). Reveals this org's stage/next-step/activity `__c` names so the closing-soon read can surface them; don't assume names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label } } } }\"}" })
```

Step 1 is the authority on names — use exact strings, never guess. **Response can be large** on customized orgs — if it truncates and auto-saves to a temp file, don't shell to that file (it's outside the bash mount) and don't read it whole; read it back directly and filter to `__c` fields whose `label` matches your keywords. Grounding is best-effort (customs are additive); standard fields (`Amount`, `CloseDate`, `StageName`, `NextStep`, `LastActivityDate`) and `Account`/`Owner` spans are reliable across orgs.

## 2. Read — running user + calendar + closing-soon + past-due + inbox, ISSUE ALL IN ONE TURN

Five independent reads (plus step 1) — batch them in a single turn. Insert `<OPP_CUSTOM>` = confirmed `__c { value }` fields.

**2a. Today's calendar** — today's meetings for the running user. There is **no `/connect/calendar/...` REST resource on this server** — read the calendar from the `Event` object via GraphQL (below), or a dedicated calendar connector tool if one is present. Do NOT guess a REST path or reach for `discover` on a 404; the query here is the path.

**Shape gotcha — `Event.What`/`Event.Who` are polymorphic** (`Event_What` / `Event_Who` unions) and expose **no `Name` span**: `What { Name { value } }` throws a schema error. Pull the raw `WhatId` / `WhoId` scalars instead. `WhatId` is your best account link — a `001…` Id is an Account, `006…` an Opportunity — resolve it directly in step 3 (no domain-guessing for those). Get attendee email domains from the `Description`/`Location` text, or an `EventRelation` child if you need invitees.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Event(scope: MINE, where: { ActivityDate: { eq: { literal: TODAY } } }, first: 50, orderBy: { StartDateTime: { order: ASC } }) { edges { node { Id Subject { value } StartDateTime { value } EndDateTime { value } Location { value } WhatId { value } WhoId { value } Description { value } } } } } } }\"}" })
```

`scope: MINE` returns events **you own** (organize). Meetings where you're only an invitee live under `EventRelation` and may not appear here — an empty calendar usually means that or a genuinely clear day, not a failure; say which. Extract each event's external-attendee email domains and its `WhatId`; those are the input to step 3.

**2b. Closing soon** — the rep's open opps closing in the next 14 days. A small filtered set — pull concrete rows (`first: 50`), not an aggregate.

**Date filters take a `DateInput` object, never a bare string** (`gte: \"…\"` fails `WrongType … must be an object type`). Three forms, each nested under a comparison op (`gte`/`lte`/`eq`); multiple ops on one field are AND'd automatically (no `and: [...]` wrapper):
- **relative window** (preferred here — no client-side date math): `{ range: { next_n_days: 14 } }` / `{ range: { last_n_days: 30 } }`. Keys come in `last_n_*` / `next_n_*` / `n_*_ago` families over `days|weeks|months|quarters|years` (e.g. `last_n_months: 3`, `n_days_ago: 2`).
- **relative period**: `{ literal: LAST_QUARTER }` (or `THIS_QUARTER`, `TODAY`, …).
- **exact date**: `{ value: \"YYYY-MM-DD\" }`.

So "closing in the next 14 days" = `CloseDate: { gte: { literal: TODAY }, lte: { range: { next_n_days: 14 } } }`:
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(scope: MINE, where: { IsClosed: { eq: false }, CloseDate: { gte: { literal: TODAY }, lte: { range: { next_n_days: 14 } } } }, first: 50, orderBy: { CloseDate: { order: ASC } }) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } NextStep { value } LastActivityDate { value } <OPP_CUSTOM> Account { Name { value } } } } } } } }\"}" })
```
(To widen the window, change `next_n_days`; for a named period the user gives, swap to the exact-date form `{ value: \"YYYY-MM-DD\" }` on both bounds.)

**2c. Past due** — the rep's open opps with close date in the past (still not closed). Pull concrete rows (`first: 50`) for the `pastDueRows` widget datagrid:
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(scope: MINE, where: { IsClosed: { eq: false }, CloseDate: { lt: { literal: TODAY } } }, first: 50, orderBy: { CloseDate: { order: ASC } }) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } NextStep { value } LastActivityDate { value } <OPP_CUSTOM> Account { Name { value } } } } } } } }\"}" })
```

**2d. Inbox signal** — unread email from the last 48h whose sender domain matches an account you own (email tool). Sender, subject, domain only — don't read bodies (that's `inbox-sweep`).

**2e. Running user** — who's the briefing for, their name, and timezone. The running-user record needs **no Id** — `currentUser` always resolves to the signed-in user. It requires **v66.0** specifically (the GraphQL endpoint otherwise pins v65.0 — bump the version in the URL for this one call):
```
dispatch_readonly(method: "GET", url: "/services/data/v66.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { currentUser { Id Name { value } Email { value } TimeZoneSidKey { value } } } }\"}" })
```
Use `Name` for the briefing title/date header; `TimeZoneSidKey` to render "today" and last-touch ages in the rep's zone (2b/2c's windows are resolved server-side, so no client date math); `Email` domain as a fallback when matching your own account inbox in 2d.

## 3. Meeting context — ONE batched turn (depends on 2a's domains)

Resolve every meeting's account in **one** query (not per-meeting), OR-ing two kinds of match together: (a) any `WhatId` from 2a that is an Account (`001…`) → `Id: { eq }`, or an Opportunity (`006…`) → its `AccountId`; (b) the external-attendee domains → `Website` `like`. Prefer the direct `WhatId` link when present — it's exact; fall back to domain match only for meetings with no usable `WhatId`.
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { or: [ { Id: { in: [\\\"<WhatId account 001…>\\\"] } }, { Website: { like: \\\"%domain1%\\\" } }, { Website: { like: \\\"%domain2%\\\" } } ] }, first: 25) { edges { node { Id Name { value } Website { value } LastActivityDate { value } Opportunities(where: { IsClosed: { eq: false } }, first: 5, orderBy: { Amount: { order: DESC } }) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } } } } } } } } } }\"}" })
```
In the same turn, per matched account: **docs** search (most recent transcript/notes/plan — title + one-line) and **"you owe them"** email search (sent-mail promises to those attendees — "I'll send/get you/intro" — still unfulfilled). No account match → `(no CRM match — net new or personal)`.

## 4. Flag (record only; cite; invent nothing)

- **Closing soon** — flag blank `NextStep` or stale (`LastActivityDate` 7d+).
- **Inbox** — count customer-domain unreads; list the top 3 by matched-opp `Amount`.
- **Per meeting** — time · title · attendees · account · open-opp stage+$ · last touch · one-line "why it matters" · **you owe** (or "nothing outstanding") · **walk in asking** (the one thing to get, given stage + context).

## 5. Output — widget FIRST (the rendered UI is the default)

## ⛔ SILENCE RULE — STRICTLY ENFORCED

The only bytes you may write after data assembly are the `display_widget` tool call and its arguments. Nothing else.

When you have all the data, say exactly: "Displaying the visualization now (this may take a minute)." This is the only permitted sentence between data gathering and calling `display_widget`. Then immediately call `display_widget` — no further narration.

NO text output of any kind before or after `display_widget` — no data summaries, no computation notes, no transition sentences, no "assembling widget..." narration, no bullet lists of what you found. Violating this rule is an output error, not a style preference.

**Fallback trigger: ONLY produce the text fallback if `display_widget` raised an exception or returned `isError: true`. A successful tool call with any widget definition in the response = widget mode. A user message saying "no output" or "nothing rendered" does NOT override this — it means the widget rendered in the chat and they may not have seen it.**

If `display_widget` returned a non-error result AND the user says there was no visible output, respond with one sentence only: "The widget rendered in the chat — please scroll up if you don't see it." Do not produce the text fallback.

**If `display_widget` succeeded: NO MORE OUTPUT. Stop. Do not summarize findings, recap the session, or add any closing text.**

❌ WRONG: `"I found 12 deals totaling $4.2M. Here's the overview: [widget] The key risk is..."`
✅ RIGHT: `[widget]`

### Self-verification (before calling display_widget)

- [ ] Every `{{token}}` replaced with a resolved literal — no `{{…}}`, no `{!…}`.
- [ ] The datagrid `rows` are typed: `amount`/`trend` are numbers/number arrays, not strings; risky rows carry `_tone`, healthy rows don't.
- [ ] Every button's `onClick` is `action/sendMessage` with a real first-person `content` prompt — no decorative buttons.
- [ ] No pie/bar/meter/heatmap/waterfall tiles — the sparkline column in the opportunity datagrid is the only inline visual.
- [ ] The #1-move callout leads; the stat strip and flags support it.
- [ ] The Step 6 markdown is produced only when `display_widget` is unavailable (the terminal fallback) — not alongside a rendered widget.
- [ ] No prose written before or after this call — no input narration, no transition text, no summary (only applies when display_widget is available; if unavailable, produce the text fallback section below).
- [ ] I am producing zero prose before or after this call. If I am tempted to summarize findings, I must not.

If `display_widget` is available (Cowork/desktop/web), the widget IS the output; produce the text section below only as the fallback when `display_widget` is unavailable (e.g. a terminal). The widget template is embedded below — a widget-definition envelope whose leaf values carry {{token}} placeholders. Resolve every {{token}} to a literal (no {{…}}/{!…} left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a {{token}} becomes the typed literal — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string is interpolated as text.

Tokens: `dateEyebrow briefingTitle` (header) · `topMove topMoveDetail topMoveDraftMsg` (the #1 move callout with its primary action button) · `kpiEventsLine kpiEventsSub kpiPipelineLine kpiPipelineSub kpiGapsLine kpiGapsSub kpiFollowupsLine kpiFollowupsSub` (four-up stat strip — each `*Line` is the whole `"<n> <unit>"` headline, e.g. `"7 meetings"`, `"$495K"`, `"2 opps"`) · `flag1Title flag1Sub flag1Msg flag2Title flag2Sub flag2Msg flag3Title flag3Sub flag3Msg flag4Title flag4Sub` (attention flags with sendMessage buttons, except flag4) · `meetingsHeading meeting1Time meeting1Title meeting1Ask meeting2Time meeting2Title meeting2Ask meeting3Line meeting4Line` (`meetingsHeading` is the section title incl. count e.g. `"Today's meetings — 4, 2 external"`; two detailed meetings render as walk-in-asking callouts — put the `"$45K · closes today"`-style tag inline in `meetingNTitle`; the two compact meetings are a single `meetingNLine` string each) · `oweHeading owe1Title owe1Meta owe1Msg owe2Title owe2Meta owe2Msg inboxClear` (`oweHeading` incl. count; open-promise cards; inbox-clear caption when empty) · `oppsSummary closingLabel gridColumns closingRows pastDueLabel pastDueRows` (accordion with two datagrids sharing one `gridColumns` schema; each is preceded by its `*Label` incl. count+$; each row object is `{ name (plain string — format as "<Account> — <Opp Name>", e.g. "Okta — Support Uplift"; concatenate `Account.Name.value` and `Opportunity.Name.value` from the SF response — plain strings, not objects), stage, trend, close (plain string — human-readable relative date, e.g. "Today", "Jul 31 · tomorrow", "Jul 15 · 15d past"; NOT ISO YYYY-MM-DD), amount, next, _tone }` where `amount`/`trend` are numbers/number[], risky rows carry `_tone:"error"`/`"warning"`; `gridColumns` is the typed column array — keep the `trend` sparkline column). Omit any block whose data you lack; drop the column if no activity history; do not send empty arrays or leave stray {{tokens}}.

```json
{
  "renderer": {
    "componentOverrides": {
      "$": {
        "type": "mosaic",
        "definition": "tile/mosaic",
        "children": [
          {
            "definition": "tile/column",
            "attributes": { "gap": "sm" },
            "children": [
              { "definition": "tile/text", "attributes": { "text": "{{dateEyebrow}}", "variant": "eyebrow" } },
              { "definition": "tile/text", "attributes": { "text": "{{briefingTitle}}", "variant": "page-title" } }
            ]
          },

          { "definition": "tile/separator" },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "recommended",
              "eyebrow": "YOUR #1 MOVE TODAY",
              "title": "{{topMove}}",
              "description": "{{topMoveDetail}}"
            },
            "children": [
              {
                "definition": "tile/button",
                "attributes": {
                  "label": "Draft next step",
                  "variant": "primary",
                  "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{topMoveDraftMsg}}" } }
                }
              }
            ]
          },

          {
            "definition": "tile/row",
            "attributes": { "gap": "md", "align": "stretch", "isWrapped": true },
            "children": [
              {
                "definition": "tile/column",
                "attributes": { "gap": "none" },
                "children": [
                  { "definition": "tile/text", "attributes": { "text": "{{kpiEventsLine}}", "variant": "h4" } },
                  { "definition": "tile/text", "attributes": { "text": "{{kpiEventsSub}}", "variant": "caption", "color": "muted" } }
                ]
              },
              {
                "definition": "tile/column",
                "attributes": { "gap": "none" },
                "children": [
                  { "definition": "tile/text", "attributes": { "text": "{{kpiPipelineLine}}", "variant": "h4" } },
                  { "definition": "tile/text", "attributes": { "text": "{{kpiPipelineSub}}", "variant": "caption", "color": "muted" } }
                ]
              },
              {
                "definition": "tile/column",
                "attributes": { "gap": "none" },
                "children": [
                  { "definition": "tile/text", "attributes": { "text": "{{kpiGapsLine}}", "variant": "h4", "color": "error" } },
                  { "definition": "tile/text", "attributes": { "text": "{{kpiGapsSub}}", "variant": "caption", "color": "muted" } }
                ]
              },
              {
                "definition": "tile/column",
                "attributes": { "gap": "none" },
                "children": [
                  { "definition": "tile/text", "attributes": { "text": "{{kpiFollowupsLine}}", "variant": "h4" } },
                  { "definition": "tile/text", "attributes": { "text": "{{kpiFollowupsSub}}", "variant": "caption", "color": "muted" } }
                ]
              }
            ]
          },

          { "definition": "tile/separator" },

          { "definition": "tile/text", "attributes": { "text": "Needs your attention", "variant": "section-title" } },
          {
            "definition": "tile/column",
            "attributes": { "gap": "sm" },
            "children": [
              {
                "definition": "tile/callout",
                "attributes": { "variant": "error", "title": "{{flag1Title}}", "description": "{{flag1Sub}}" },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "Draft next step",
                      "variant": "secondary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{flag1Msg}}" } }
                    }
                  }
                ]
              },
              {
                "definition": "tile/callout",
                "attributes": { "variant": "error", "title": "{{flag2Title}}", "description": "{{flag2Sub}}" },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "Draft CFO ask",
                      "variant": "secondary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{flag2Msg}}" } }
                    }
                  }
                ]
              },
              {
                "definition": "tile/callout",
                "attributes": { "variant": "warning", "title": "{{flag3Title}}", "description": "{{flag3Sub}}" },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "Nudge signer",
                      "variant": "secondary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{flag3Msg}}" } }
                    }
                  }
                ]
              },
              {
                "definition": "tile/callout",
                "attributes": { "variant": "warning", "title": "{{flag4Title}}", "description": "{{flag4Sub}}" }
              }
            ]
          },

          { "definition": "tile/separator" },

          { "definition": "tile/text", "attributes": { "text": "{{meetingsHeading}}", "variant": "section-title" } },
          {
            "definition": "tile/column",
            "attributes": { "gap": "sm" },
            "children": [
              {
                "definition": "tile/callout",
                "attributes": { "variant": "recommended", "eyebrow": "{{meeting1Time}} · WALK IN ASKING", "title": "{{meeting1Title}}", "description": "{{meeting1Ask}}" }
              },
              {
                "definition": "tile/callout",
                "attributes": { "variant": "recommended", "eyebrow": "{{meeting2Time}} · WALK IN ASKING", "title": "{{meeting2Title}}", "description": "{{meeting2Ask}}" }
              },
              { "definition": "tile/text", "attributes": { "text": "{{meeting3Line}}", "variant": "body" } },
              { "definition": "tile/text", "attributes": { "text": "{{meeting4Line}}", "variant": "body" } }
            ]
          },

          { "definition": "tile/separator" },

          { "definition": "tile/text", "attributes": { "text": "{{oweHeading}}", "variant": "section-title" } },
          {
            "definition": "tile/column",
            "attributes": { "gap": "sm" },
            "children": [
              {
                "definition": "tile/callout",
                "attributes": { "title": "{{owe1Title}}", "description": "{{owe1Meta}}" },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "Draft email",
                      "variant": "secondary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{owe1Msg}}" } }
                    }
                  }
                ]
              },
              {
                "definition": "tile/callout",
                "attributes": { "title": "{{owe2Title}}", "description": "{{owe2Meta}}" },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "Draft CFO ask",
                      "variant": "secondary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{owe2Msg}}" } }
                    }
                  }
                ]
              },
              { "definition": "tile/text", "attributes": { "text": "{{inboxClear}}", "variant": "caption", "color": "muted" } }
            ]
          },

          { "definition": "tile/separator" },

          {
            "definition": "tile/accordion",
            "children": [
              {
                "definition": "tile/accordionitem",
                "attributes": { "title": "Opportunities", "subtitle": "{{oppsSummary}}", "iconName": "briefcase", "isExpanded": true },
                "children": [
                  { "definition": "tile/text", "attributes": { "text": "{{closingLabel}}", "variant": "body", "weight": "semibold" } },
                  {
                    "definition": "tile/datagrid",
                    "attributes": { "appearance": "striped", "size": "sm", "columns": "{{gridColumns}}", "rows": "{{closingRows}}" }
                  },
                  { "definition": "tile/text", "attributes": { "text": "{{pastDueLabel}}", "variant": "body", "weight": "semibold" } },
                  {
                    "definition": "tile/datagrid",
                    "attributes": { "appearance": "striped", "size": "sm", "columns": "{{gridColumns}}", "rows": "{{pastDueRows}}" }
                  }
                ]
              }
            ]
          }
        ]
      }
    }
  }
}
```


> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.
## 6. Text — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Daily Briefing — [Date]

## Today's Meetings ([N])
[Time] **[Title]** — [Attendees]
  Account: [Name] · Opp: [Stage] $[Amount] closes [Date] · Last touch: [N]d ago[ · context from doc]
  You owe: [unfulfilled promise, or "nothing outstanding"]
  → Walk in asking: [the one thing]
…

## Closing in 14 Days ([N] opps, $[total])
- **[Account]** — [Stage] $[Amount] closes [Date] · Next: [NextStep or "⚠ BLANK"] · Last activity: [N]d[ "⚠ 7+d stale"]
…

## Inbox ([N] unread from customers)
- [Sender] @ [Account] — "[Subject]" (opp $[Amount])
…  Run `inbox-sweep` to triage and draft replies.
```
