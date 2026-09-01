---
name: weekly-wrap
description: End-of-week summary for a rep or leader - what closed, what moved, what slipped, and what's on deck Monday. Optionally drafts a Slack post to the team channel. Use when the user says "weekly wrap", "week in review", "what happened this week", or "Friday summary".
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


# Weekly Wrap

Ground → resolve scope (team only) → (ONE combined SFDC read + email/doc evidence, ALL in ONE turn) → assemble + flag → output. Dispatches serialize — the whole point here is one wide read beats several narrow ones.

## 1. Ground (hardcoded — Opportunity only)

Ground **only Opportunity** — it always exists (naming a missing object fails the whole call). Its fields reveal this org's close/loss-reason `__c` schema; don't assume names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

Note any scalar `__c` fields worth surfacing (close/loss reason, stage-context note). Standard fields and the `Account` span are reliable across orgs.

## 1b. Resolve scope (team only — skip for "my week")

- **"my week"** (default) → `scope: MINE` on every root below, no lookup needed.
- **"team"** → resolve direct reports once:
  ```
  dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
    queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { User(where: { ManagerId: { eq: \\\"<CURRENT_USER_ID>\\\" }, IsActive: { eq: true } }, first: 50) { edges { node { Id Name { value } } } } } } }\"}" })
  ```
  Capture the Ids as `<TEAM_USER_IDS>`; swap every `scope: MINE` in step 2 for `OwnerId: { in: [<TEAM_USER_IDS>] }`. If your org's team hierarchy isn't ManagerId-based, resolve the roster once from context instead of guessing.

## 2. Read — pipeline movement + calendar in ONE dispatch; evidence in the SAME turn

**One query, six aliased roots** — closed, new, touched (moved), and closing-next-week Opportunities, plus this-week and next-week meetings. No `OpportunityHistory` read: `LastModifiedDate` on still-open opps is the movement signal, so there's no second object to ground or query. Insert `<OPP_CUSTOM>` = confirmed scalar `__c { value }` fields from step 1.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { closedThisWeek: Opportunity(scope: MINE, where: { IsClosed: { eq: true }, CloseDate: { eq: { literal: THIS_WEEK } } }, first: 50) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } NextStep { value } <OPP_CUSTOM> Account { Name { value } } } } } } newThisWeek: Opportunity(scope: MINE, where: { CreatedDate: { eq: { literal: THIS_WEEK } } }, first: 50) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CreatedDate { value } NextStep { value } <OPP_CUSTOM> Account { Name { value } } } } } } touchedThisWeek: Opportunity(scope: MINE, where: { IsClosed: { eq: false }, LastModifiedDate: { eq: { literal: THIS_WEEK } } }, first: 50) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } LastModifiedDate { value } NextStep { value } <OPP_CUSTOM> Account { Name { value } } } } } } closingNextWeek: Opportunity(scope: MINE, where: { IsClosed: { eq: false }, CloseDate: { eq: { literal: NEXT_WEEK } } }, first: 50) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } NextStep { value } <OPP_CUSTOM> Account { Name { value } } } } } } meetingsThisWeek: Event(scope: MINE, where: { ActivityDate: { eq: { literal: THIS_WEEK } } }, first: 50) { edges { node { Id Subject { value } StartDateTime { value } Location { value } WhatId { value } } } } } meetingsNextWeek: Event(scope: MINE, where: { ActivityDate: { eq: { literal: NEXT_WEEK } } }, first: 50) { edges { node { Id Subject { value } StartDateTime { value } Location { value } WhatId { value } } } } } } } }\"}" })
```

**Team scope** → swap every `scope: MINE` above for `OwnerId: { in: [\"<TEAM_USER_IDS>\"] }`.

**In the SAME turn**, fire (independent, don't wait on the read above):
- **email** — customer-domain threads touched this week (count + top senders).
- **docs/Slack** — if available, anything noteworthy this week per account. Use whatever connector tools are present; skip silently if none.

## 3. Assemble + flag (record only; reconcile totals; invent nothing)

- **Closed** — from `closedThisWeek`: ✅ won / ❌ lost, with loss reason if an `__c` field surfaced it. Net = Σ won − nothing (lost isn't subtracted from won $, just reported).
- **Moved** — from `touchedThisWeek`: open opps modified this week, grouped by current stage. **No `OpportunityHistory` = no from→to transition** — report "active this week, now at [Stage]," never fabricate a stage-change arrow.
- **New** — from `newThisWeek`: account, amount, starting stage.
- **Activity** — meeting count from `meetingsThisWeek` (eyeball Subject/Location for internal-only noise, e.g. standups, and don't count those as customer activity), plus the email thread count from evidence.
- **Monday** — `meetingsNextWeek` (time, subject, account if `WhatId` resolves) + `closingNextWeek` opps + any `NextStep` text already in hand that names a date next week (scan, don't re-query).

## 4. Output — widget FIRST (the rendered UI is the default)

Call `display_widget` now with the data you collected. Do not write markdown first — call immediately. Only fall back to markdown if the tool is unavailable.

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

- [ ] No prose written before or after this call — no input narration, no transition text, no summary (only applies when display_widget is available; if unavailable, produce the text fallback section below).
- [ ] I am producing zero prose before or after this call. If I am tempted to summarize findings, I must not.

The widget template is embedded below. Call `display_widget` in **dynamic** mode with it. It is a skeleton: replace every `{{token}}` placeholder with a fully-resolved literal computed from the week's data — this echo path does no expression compilation, so no `{!…}` bindings.

```json
{
  "renderer": {
    "componentOverrides": {
      "$": {
        "type": "mosaic",
        "definition": "tile/mosaic",
        "children": [
          {
            "definition": "tile/row",
            "attributes": { "gap": "sm", "align": "center", "justify": "between", "isWrapped": true },
            "children": [
              {
                "definition": "tile/row",
                "attributes": { "gap": "sm", "align": "center" },
                "children": [
                  { "definition": "tile/icon", "attributes": { "name": "calendar", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{title}}", "variant": "page-title" } }
                ]
              }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "lg", "align": "stretch", "isWrapped": true },
            "children": [
              {
                "definition": "tile/chart",
                "attributes": {
                  "chartType": "column",
                  "caption": "{{activityCaption}}",
                  "categories": "{{activityCategories}}",
                  "series": "{{activitySeries}}",
                  "valueFormat": "number",
                  "showLegend": true
                }
              },
              {
                "definition": "tile/waterfall",
                "attributes": {
                  "caption": "{{waterfallCaption}}",
                  "valueFormat": "currency",
                  "size": "lg",
                  "start": "{{waterfallStart}}",
                  "steps": "{{waterfallSteps}}",
                  "end": "{{waterfallEnd}}"
                }
              }
            ]
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{datagridCaption}}",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                { "key": "deal", "header": "Deal", "type": "text" },
                { "key": "amount", "header": "Amount", "type": "currency", "align": "right" },
                { "key": "event", "header": "What happened", "type": "badge" },
                { "key": "note", "header": "Note", "type": "text" }
              ],
              "rows": "{{dealRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "success",
              "title": "{{calloutTitle}}",
              "description": "{{calloutDescription}}"
            },
            "children": [
              {
                "definition": "tile/row",
                "attributes": { "gap": "sm", "align": "center", "isWrapped": true },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{button1Label}}",
                      "variant": "primary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{button1Content}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{button2Label}}",
                      "variant": "secondary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{button2Content}}" } }
                    }
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

What each block shows, from data you already have:

- **Header** — an icon (calendar), page-title text (`{{title}}`, e.g. "Weekly wrap — week of Jul 20"), and a one-line caption subhead (`{{subtitle}}`) summarizing closed $, won/lost counts, pipeline added, and activity count, with a separator.
- **Two graphs in a wrapped row**:
  - **Column chart** — "Daily activity — calls, emails, and meetings" (`{{activityCaption}}`): `{{activityCategories}}` (weekdays), `{{activitySeries}}` (3 series: Calls, Emails, Meetings with daily counts), `valueFormat:"number"`, with legend.
  - **Waterfall** — "How commit moved this week" (`{{waterfallCaption}}`): `{{waterfallStart}}` (Last Mon value), `{{waterfallSteps}}` (Won/New pipe/Slipped out/Lost deltas), `{{waterfallEnd}}` (This Mon), `valueFormat:"currency"`, size lg.
- **Datagrid** (`{{dealRows}}`) — "This week's closed and moved deals" (`{{datagridCaption}}`). Columns: Deal (text), Amount (currency, right-aligned), What happened (badge), Note (text). Every row carries `_tone` (success/error/warning) and `_status` (Won/Lost/Slipped); the renderer auto-injects a leading Status column from `_status`.
- **One synthesis callout** (`variant:"success"`) — `{{calloutTitle}}` (the week's single most important read) and `{{calloutDescription}}`. It carries two real buttons: "Draft Slack post" (`{{button1Label}}` / `{{button1Content}}`, `action/sendMessage`) and "Prep Monday plan" (`{{button2Label}}` / `{{button2Content}}`, `action/sendMessage`).

**Hydration rules:**
1. Start from the embedded template above — a valid-JSON widget-definition envelope whose leaf values carry `{{token}}` placeholders.
2. Resolve every `{{token}}`. A value that is **only** a `{{token}}` (chart `categories`/`series`, waterfall `start`/`steps`/`end`, datagrid `rows`) becomes the resolved **typed** literal — numbers stay numbers, arrays stay arrays. A `{{token}}` **inside** a larger string is interpolated as text.
3. `{{activitySeries}}` is an array of series objects — each with `name` (string) and `data` (array of numbers). `{{waterfallSteps}}` is an array of step objects — each with `label` (string) and `delta` (number). `{{dealRows}}` is an array of deal objects — each with `deal` (plain string — format as the account or opportunity name (e.g. "Vertex Manufacturing"); names must be plain strings, not objects: use `Account.Name.value` from the SF response), `amount` (number), `event` (`{ value, badgeVariant }`), `note` (text), `_tone` (success/error/warning), and `_status` (Won/Lost/Slipped).
4. The result is hydrated widget definition (no `{{…}}` placeholders remain). Then call:

```
display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated renderer.json> })
```

**Binding rules:**
- Resolve every `{{token}}` to a literal before calling — numbers stay numbers (`{{waterfallStart}}.value`, each step's `delta`, each row's `amount`), arrays stay arrays (`{{activityCategories}}`, `{{activitySeries}}`, `{{waterfallSteps}}`, `{{dealRows}}`), strings stay strings.
- Chart series: each object has `name` (string) and `data` (array of numbers, one per category). Categories are weekday labels (Mon-Fri).
- Waterfall: `{{waterfallStart}}` is `{ label, value }`, `{{waterfallSteps}}` is an array of `{ label, delta }` (deltas can be positive or negative), `{{waterfallEnd}}` is `{ label }` (final value is computed).
- Datagrid rows: one per deal that closed/moved this week. `amount` is a raw number. The What happened badge (`event.badgeVariant`) reflects outcome — `"success"` (Won), `"error"` (Lost), `"warning"` (Slipped). `_status` drives the auto Status column. Rank rows by outcome (Won first, Lost second, Slipped last).
- Callout buttons: both are `action/sendMessage` with first-person `content` prompts (`{{button1Content}}`, `{{button2Content}}`, e.g. "Draft a Slack post for…"). Never leave a button decorative.
- No fabricated content — quote blank fields as blank rather than inventing them; drop deals you have no data for.


> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.
## 5. Text — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Week of [Mon date] - [Scope]

## Closed
- ✅ **[Account]** $[X] WON
- ❌ **[Account]** $[X] lost - [reason if in SFDC]
**Net: $[won total]**

## Moved (active this week, no history = no from→to)
- **[Account]** now at [Stage] ($[X])
...

## New
- **[Account]** $[X] created at [Stage]
...

## Activity
[N] customer meetings, [N] customer email threads

## Monday
- [Time] [Meeting] - [Account if resolved]
- Closing next week: [Account] $[X], [Account] $[X]
- NextStep due: [list]
```

If "post to Slack" - format the above for Slack (bold via asterisks, bullets) and create a draft to the team channel from config. User reviews and posts.
