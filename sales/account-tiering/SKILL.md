---
name: account-tiering
description: Score and tier a list of accounts (or your full book) against ICP fit and engagement signals to prioritize where to spend time. Use when the user asks to "tier my accounts", "prioritize my book", "which accounts should I focus on", or "score these accounts".
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

- Resolve to ONE account before the deep read. When the name is ambiguous, ask the user to pick — don't probe candidates or guess.

# Account Tiering

Ground → (read + evidence, all in ONE turn) → score → tier. Scope: "my accounts", a named list, or a report/list view name. Default tier count: 3 (A/B/C).

## 1. Ground (hardcoded — Account only)

Ground **only Account** — it always exists (naming a missing object fails the whole call). Its fields + childRelationships reveal this org's real ICP/engagement schema (custom fit score, territory, renewal fields, etc.) — don't assume custom field names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Account\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

Use exact strings from the result, never guess. Note: (a) scalar `__c` fields carrying ICP-fit/engagement signals — take their `{ value }`; (b) each lookup's exact `relationshipName` for spanning a related name; (c) confirm `Opportunities`/`Contacts` are present (standard, always are).

The ICP itself (industries, size, titles, disqualifiers) is external knowledge — infer it from the org's own account/opportunity data, or ask the user once. Never invent it.

## 2. Read (fill from step 1, one dispatch)

`%SCOPE%` = `scope: MINE` for "my accounts"; `where: { Name: { in: [\\\"Acme\\\", ...] } }` for a named list. (A report/list-view scope needs its own name→Id resolve first — outside the common path; ask for a name list instead if one isn't already resolved.)

**Reference-field rules (avoids the retry loop):** a scalar/`__c` field → `Field__c { value }` (`displayValue` is null for Id fields here — don't rely on it). For a related record's name, span the exact `relationshipName` from Step 1: `<relationshipName> { Name { value } }` — never subselect a raw Id. No usable relationshipName → take the Id and move on, don't retry.

Insert `<ACCOUNT_CUSTOM>` = confirmed scalar `__c { value }` fields relevant to fit/engagement; `<REL_BLOCKS>` = one block per confirmed custom lookup. `Owner`/`Opportunities`/`Contacts` always work.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(%SCOPE%, first: 200) { edges { node { Id Name { value } Industry { value } NumberOfEmployees { value } AnnualRevenue { value displayValue } Website { value } Type { value } LastActivityDate { value } <ACCOUNT_CUSTOM> Owner { Name { value } } <REL_BLOCKS> Opportunities { edges { node { Id StageName { value } IsClosed { value } Amount { value displayValue } CloseDate { value } } } } Contacts { edges { node { Id Title { value } } } } } } } } } }\"}" })
```

Filter `IsClosed = false` in analysis (Step 4), not the query. Empty `edges` → broaden the scope or confirm account names. `first: 200` caps the book — if the scope is larger, say so and ask the user to narrow it rather than silently truncating.

## 2b. Evidence (fired IN PARALLEL with step 2 — same turn)

Issue step 2 and step 2b together in one turn; don't wait for the SF read. Keyed on the account scope (names/domains), not the SF result:
- **email**: inbound threads from account domains in the last 90d → which accounts, last date
- **docs/slack**: any account mentions → triggers, concerns

Use whatever tools are available; skip silently if none (SFDC-only is fine). Never block on these; cite source + date for anything you use.

## 3. Score ICP fit (0-10)

| Signal | Weight | Scoring |
|---|---|---|
| Industry match | 3 | exact=3, adjacent=1, off-ICP=0 |
| Size in range | 3 | in range=3, ±50%=1, outside=0 |
| Target persona present (Contact titles) | 2 | yes=2, maybe=1, none=0 |
| No disqualifiers | 2 | clean=2, soft DQ=1, hard DQ=0 |

## 4. Score engagement (0-10)

| Signal | Weight | Scoring |
|---|---|---|
| Open opportunity exists (`IsClosed=false` in Step 2 data) | 3 | yes=3, no=0 |
| LastActivityDate recency | 3 | <30d=3, 30-90d=2, 90-180d=1, >180d=0 |
| Inbound signal (Step 2b email, last 90d) | 2 | yes=2, no=0 |
| Multiple contacts engaged | 2 | 3+=2, 2=1, ≤1=0 |

## 5. Tier and recommend

Plot on a 2x2 (Fit × Engagement):
- **Tier A** (high fit, high engagement): active pursuit — progress the open opp, multi-thread.
- **Tier B** (high fit, low engagement): activation — outbound sequence, find a trigger.
- **Tier C** (low fit, high engagement): qualify hard — one discovery call to confirm fit or DQ.
- **Deprioritize** (low fit, low engagement): no active motion, revisit quarterly.

## 6. Output — widget FIRST (the rendered UI is the default)

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

The widget template is embedded below — a widget-definition envelope whose leaf values carry {{token}} placeholders. Resolve every {{token}} to a literal (no {{…}}/{!…} left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a {{token}} becomes the typed literal — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string is interpolated as text. Tokens: `title` (page title with account count), `subtitle` (tier counts summary) · `heatmapCaption`, `heatmapXLabels`, `heatmapYLabels`, `heatmapDomain` (array `[min, max]`), `heatmapCells` (array of `{x, y, value, valueLabel?}`, one per quadrant) · `piechartCaption`, `piechartCenterLabel`, `piechartCenterValue`, `piechartSlices` (array of `{label, value, role?}`, role:"highlight" on Tier A) · `datagridCaption`, `datagridRows` (array, one per Tier A account: `{account, fit: 1-5 number, engage: 0-100 number, arr: number, white: number, motion: {value, badgeVariant}}`) · `calloutTitle`, `calloutDescription` (coverage gap), `primaryButtonLabel`, `primaryButtonMsg` (sendMessage action), `salesforceUrl` (Account list view URL).

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
                  { "definition": "tile/icon", "attributes": { "name": "layers", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{title}}", "variant": "page-title" } }
                ]
              }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "lg", "align": "stretch", "isWrapped": false },
            "children": [
              {
                "definition": "tile/heatmap",
                "attributes": {
                  "width": "stretch",
                  "layout": "matrix",
                  "caption": "{{heatmapCaption}}",
                  "xLabels": "{{heatmapXLabels}}",
                  "yLabels": "{{heatmapYLabels}}",
                  "encode": "color",
                  "scale": "sequential",
                  "valueFormat": "number",
                  "domain": "{{heatmapDomain}}",
                  "cells": "{{heatmapCells}}"
                }
              },
              {
                "definition": "tile/piechart",
                "attributes": {
                  "width": "stretch",
                  "caption": "{{piechartCaption}}",
                  "variant": "donut",
                  "valueFormat": "number",
                  "centerLabel": "{{piechartCenterLabel}}",
                  "centerValue": "{{piechartCenterValue}}",
                  "slices": "{{piechartSlices}}"
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
              "defaultSort": { "key": "fit", "direction": "desc" },
              "columns": [
                { "key": "account", "header": "Account", "type": "text" },
                { "key": "fit", "header": "ICP fit", "type": "number", "align": "right", "sortable": true },
                { "key": "engage", "header": "Engagement", "type": "databar", "target": 100 },
                { "key": "arr", "header": "ARR", "type": "currency", "align": "right", "sortable": true },
                { "key": "white", "header": "Whitespace", "type": "currency", "align": "right" },
                { "key": "motion", "header": "Motion", "type": "badge" }
              ],
              "rows": "{{datagridRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "recommended",
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


> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.
## 7. Text — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Account Tiering - [N] accounts

## Tier A - Active Pursuit ([N], $[pipeline sum])
| Account | Fit | Eng | Open Opp | Last Touch | Next Action |
|---|---|---|---|---|---|
...

## Tier B - Activate ([N])
...

## Tier C - Qualify or DQ ([N])
...

## Deprioritized ([N])
[Just names, collapsed]

## Coverage Gaps
- [N] Tier A/B accounts with no activity in 30+ days
- [N] accounts missing Industry or NumberOfEmployees (can't score - fix in SFDC)
```
