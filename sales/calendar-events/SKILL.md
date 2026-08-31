---
name: calendar-events
description: Calendar-only view - display schedule, event, or meeting data for a date range visually. Use for schedule-only requests when the user asks "what's on my calendar", "show my meetings", "what do I have today/tomorrow/this week", "what was on my calendar last week", "display this week's schedule", or wants to see their schedule. Do NOT use when the user wants a broader daily briefing that also folds in pipeline, account, or inbox priorities (that's daily-briefing). Returns events in either an interactive HTML widget (Cowork/desktop/web) or clean markdown (Claude Code).
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

- **Pick View vs Create from the verb before doing anything.** View = show/get/pull up/view/see. Create = create/build/set up/draft/make. Ambiguous → ask which; **never fall through a view request into creating a record.**
- On the create path, flag anything you can't source with `[needs validation]`.
- **`Status` is always `"Not Started"` on creation.** Never create a plan in any other status; lifecycle changes are out of scope.

# Calendar Events

Resolve timezone → compute range (no call) → read Events → render. All dates/times in the user's **local** timezone, not UTC.

## 1. Resolve timezone

Standard field, no grounding needed:

```
dispatch_readonly(method: "GET", url: "/services/data/v66.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { currentUser { TimeZoneSidKey { value } } } }\"}" })
```

Derive the current UTC offset from the IANA zone (e.g. `America/Los_Angeles` → `-07:00` or `-08:00`), accounting for DST at the dates in question — use the actual current date from context as the reference. Unresolvable → fall back to UTC (`+00:00`), note it in the output.

## 2. Date range (prompt-only — no dispatch)

Anchor to the resolved local timezone:
- **today** → today 00:00–23:59 · **tomorrow** → tomorrow 00:00–23:59
- **this/next/last week** → Mon–Sun of that week · **this month** → 1st–last day
- **specific date** → that date 00:00–23:59 · **explicit range** → as given

Always ISO-8601 with the offset from Step 1 (e.g. `2026-08-04T00:00:00-07:00`).

## 3. Read Events

`scope: MINE` already filters to the current user — no Id lookup needed. `%START%`/`%END%` = Step 2's ISO boundaries. `Who`/`What` are polymorphic unions on Event (stable, not org-specific) — span via inline fragments, never bare:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Event(scope: MINE, where: { StartDateTime: { gte: \\\"%START%\\\", lt: \\\"%END%\\\" } }, orderBy: { StartDateTime: { order: ASC } }, first: 100) { edges { node { Id Subject { value } StartDateTime { value displayValue } EndDateTime { value displayValue } Description { value } Location { value } IsAllDayEvent { value } Who { ... on Contact { Name { value } } ... on Lead { Name { value } } } What { ... on Account { Name { value } } ... on Opportunity { Name { value } } } } } } } } } }\"}" })
```

Empty `edges` → say "No events found for [range]", don't retry with a broader window unasked.

## 4. Render — widget first

Call `display_widget` immediately after assembling the event list. Do not write markdown first — only fall back to the Step 5 markdown when the tool is unavailable (e.g. Claude Code, where raw HTML would just show up as `<div>` text).

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

- [ ] Every `{{token}}` placeholder replaced with a resolved literal — no `{{…}}` left, no `{!…}` expressions in the widget definition.
- [ ] No graphs (heatmap/piechart/chart/meter/waterfall count = 0).
- [ ] Datagrid `value` is a raw number (deal-linked) or `{ value: 0, display: "—" }` (internal).
- [ ] Datagrid rows with urgent prep state carry `_tone:"error"` + `_status:"Prep now"`.
- [ ] Callout buttons wired to sendMessage (primary) and openLink (secondary).
- [ ] The Step 5 markdown is produced only when `display_widget` is unavailable (the terminal fallback) — not alongside a rendered widget.
- [ ] No prose written before or after this call — no input narration, no transition text, no summary (only applies when display_widget is available; if unavailable, produce the text fallback section below).
- [ ] I am producing zero prose before or after this call. If I am tempted to summarize findings, I must not.

The widget template is embedded below. Call `display_widget` in **dynamic** mode with it. It is a skeleton: replace every `{{token}}` with a fully-resolved literal computed from the events you gathered — this echo path does no expression compilation, so no `{!…}` bindings.

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
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{datagridCaption}}",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                { "key": "time", "header": "Time", "type": "text" },
                { "key": "title", "header": "Meeting", "type": "text" },
                { "key": "deal", "header": "Deal", "type": "text" },
                { "key": "value", "header": "Value", "type": "currency", "align": "right" },
                { "key": "prep", "header": "Prep", "type": "badge" }
              ],
              "rows": "{{datagridRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "{{calloutVariant}}",
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
                      "label": "{{primaryButtonLabel}}",
                      "variant": "primary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{primaryButtonMsg}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "View in Salesforce",
                      "variant": "secondary",
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{salesforceUrl}}" } }
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

- **Header** — an icon + page-title text (`{{title}}`, e.g. "Today — Thursday, Jul 24"), with a one-line caption subhead (`{{subtitle}}` = "[N] meetings · [N] deal-linked · [N] external · first at [time], last ends [time]") and a separator.
- **Schedule datagrid** (`{{datagridCaption}}`, `{{datagridRows}}`) — one row per meeting in order. Columns: Time (text), Meeting (text), Deal (text), Value (currency), Prep (badge). Rows carry `_tone` (error/warning/success) and `_status` (Prep now/Draft/Ready/At risk) for prep state. Non-deal meetings show "—" for deal and a currency cell with `{ value: 0, display: "—" }`.
- **One synthesis callout** (`variant` = `{{calloutVariant}}`, typically "error") — `{{calloutTitle}}` and `{{calloutDescription}}` (the single meeting that needs prep before you walk in, why, and the move). It carries two buttons: a primary with `{{primaryButtonLabel}}` and `{{primaryButtonMsg}}` (`action/sendMessage`), and a secondary "View in Salesforce" with `{{salesforceUrl}}` (`action/openLink`).

**Hydration rules:**
1. Start from the embedded template above — a valid-JSON widget-definition envelope whose leaf values carry `{{token}}` placeholders.
2. Resolve every `{{token}}`. A value that is **only** a `{{token}}` (datagrid `rows`) becomes the resolved **typed** literal — numbers stay numbers, arrays stay arrays. A `{{token}}` **inside** a larger string is interpolated as text.
3. `{{datagridRows}}` is an array of row objects with `time` (text), `title` (text), `deal` (text, "—" for internal), `value` (number, or `{ value: 0, display: "—" }` for internal), `prep` (`{ value, badgeVariant }`), `_tone` (error/warning/success), `_status` (Prep now/Draft/Ready/At risk).
4. The result is hydrated widget definition (no `{{…}}` placeholders remain). Then call:

```
display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated renderer.json> })
```

**Binding rules:**
- Resolve every `{{token}}` to a literal before calling — numbers stay numbers (`value`), arrays stay arrays.
- Datagrid `value` is a raw number (deal-linked meetings) or `{ value: 0, display: "—" }` (internal meetings). Prep badge `badgeVariant` reflects urgency (error/warning/success/secondary).
- Datagrid rows carry `_tone` (error for needs-prep-now, warning for at-risk, success for ready) and `_status` (Prep now/Draft/Ready/At risk) — the renderer auto-injects a leading Status column from `_status`.
- Callout buttons: primary is `action/sendMessage` with a first-person prompt (`{{primaryButtonMsg}}`), secondary is `action/openLink` with `{{salesforceUrl}}` (an Event record URL), opening a new tab.
- Callout `variant` is tokenized (`{{calloutVariant}}`), typically "error" for urgent prep needs.


> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.
## 5. Markdown — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

One table per day, times in the resolved local timezone (label `(times in UTC)` if it fell back):

```
# Calendar - [Date Range] (times in [TZ label])

## [Day Name], [Mon DD]
| Time | Event | Location |
|------|-------|----------|
| [Start]–[End] | [Subject] | [Location] |
| All day | [Subject] | — |

**Total events:** [N]
```

Group by day (`##` heading, one table each); all-day rows show `All day`; empty location → `—`; no events → `No events found for [range].`; times `10:00 AM` / `2:30 PM` (12-hour).

## [CUSTOMIZE]

- **Time format:** 12-hour default; switch to 24-hour if preferred.
- **What/Who members:** Step 3 spans `Account`/`Opportunity` (What) and `Contact`/`Lead` (Who) — the common cases. Add another member's inline fragment (e.g. `... on Campaign`) if your org uses it on Event.
