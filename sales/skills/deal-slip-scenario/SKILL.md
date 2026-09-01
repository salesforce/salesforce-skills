---
name: deal-slip-scenario
description: Model what happens to your number if a deal slips, shrinks, or dies - quota impact, coverage ratio change, and the substitute pipeline needed to stay on plan. Use when the user asks "what if [deal] slips", "what happens if [account] pushes to next quarter", "can I still hit my number without [deal]", or "model losing [deal]".
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

# Deal Slip Scenario


# Rules:


# Deal Slip Scenario

Ground → read baseline → apply scenario → output. **No per-opp follow-ups** — the opp reads have the data.

## 1. Ground (hardcoded — Opportunity only)

Ground **Opportunity** (for pipeline fields). Always exists. One call:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

**If it overflows**, the result auto-persists to a temp file **outside the bash mount** — don't shell to it (`cat`/`python3`/`ls` will fail, it's not on that mount). Read it back with the Read tool only, and go straight to that — don't retry bash first. If the Read tool can't load it either, skip custom-field grounding and proceed with standard fields only; don't keep retrying.

From the result: (a) scalar `__c` fields (risk, timing, health, etc.) — take their `{ value }`; (b) each lookup field's exact `relationshipName` to span for a related record's Name; (c) each child `relationshipName`.

## 2. Read baseline (templated, one turn)

Fire these as tool calls in **one turn** (independent). Insert `<OPP_CUSTOM>` = confirmed scalar `__c { value }` fields (risk, health, timing signals, etc.).

**Date filters take a `DateInput` object, never a bare string** (`gte: \"2026-07-01\"` fails `WrongType … must be an object type`). For the current-quarter bounds below, use the exact-date form on both ends: `{ value: \"YYYY-MM-DD\" }`. Multiple ops on one field (`gte`/`lte`) AND automatically — no `and: [...]` wrapper needed around them.

**Open opps this quarter (ordered by forecast category then amount):**
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { OwnerId: { eq: \\\"<SCOPE_USER_ID>\\\" }, IsClosed: { eq: false }, CloseDate: { gte: { value: \\\"<Q_START>\\\" }, lte: { value: \\\"<Q_END>\\\" } } }, orderBy: { Amount: { order: DESC } }, first: 200) { edges { node { Id Name { value } StageName { value displayValue } ForecastCategory { value } Amount { value displayValue } CloseDate { value } Probability { value } NextStep { value } LastActivityDate { value } <OPP_CUSTOM> Account { Name { value } } Owner { Name { value } } } } } } } }\"}" })
```

**Closed-won this period (for booked baseline):**
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { OwnerId: { eq: \\\"<SCOPE_USER_ID>\\\" }, IsWon: { eq: true }, CloseDate: { gte: { value: \\\"<Q_START>\\\" }, lte: { value: \\\"<Q_END>\\\" } } }, first: 200) { edges { node { Id Name { value } Amount { value } Account { Name { value } } } } } } } }\"}" })
```

`<SCOPE_USER_ID>` = current user (default) or disambiguated rep. Compute baseline:
- **Booked** = Σ closed-won `Amount.value`
- **Commit total** = Booked + Σ open opps where `ForecastCategory.value = "Commit"`
- **Best case total** = Commit total + Σ `ForecastCategory.value = "BestCase"`
- **Open pipeline total** = Σ all open opps `Amount.value`
- **Coverage ratio** = Open pipeline total ÷ (Quota − Booked)

If quota isn't in org data, ask once.

## 3. Apply scenario

Remove or restate the named deal(s):
- **Slip:** subtract from this period's buckets; note it lands next period
- **Reduced amount:** replace Amount with user's revised figure
- **Lost:** subtract entirely

Recompute commit total, gap to quota, coverage ratio.

## 4. Find substitute pipeline

What in the existing open pipeline could realistically backfill this period:
- Best Case deals with recent activity (`LastActivityDate` within 14 days) and `CloseDate` inside period
- Deals one stage away from commit where timing looks achievable
- Be honest about timing: deal needing 6 weeks doesn't rescue quarter with 3 weeks left

> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.
## 5. Text — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Slip Scenario: [Deal] - [slips / cut to $X / lost]

## Before vs After
| | Baseline | Scenario | Δ |
|---|---|---|---|
| Booked | $[X] | $[X] | - |
| Commit total | $[X] | $[X] | -$[X] |
| Gap to quota | $[X] | $[X] | +$[X] |
| Coverage ratio | [X.X]x | [X.X]x | |

## Verdict
[One sentence: still on plan / at risk / not recoverable this period without new pipeline]

## Substitute pipeline (what could backfill)
- **[Account]** $[X] - [bucket] - [why it's plausible this period, what has to happen, by when]
- ...
- Realistic backfill total: $[X] of the $[X] gap

## What to do this week
1. [Highest-leverage action to either save the slipping deal or accelerate a substitute - specific]
2. ...

## If it slips anyway
- Next-period commit starts at $[X] including this deal - [note any knock-on risk, e.g. stacked renewals or capacity]
```


## 6. Dashboard widget (data-viz tiles)

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

The widget template is embedded below — a widget-definition envelope whose leaf values carry {{token}} placeholders. Resolve every {{token}} to a literal (no {{…}}/{!…} left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a {{token}} becomes the typed literal — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string is interpolated as text.

**Tokens:**
- `{{title}}`, `{{headerStatus}}`, `{{subtitle}}` — scenario header (derived from deal names, commit vs quota)
- `{{meterLabel}}`, `{{meterValue}}`, `{{meterMax}}`, `{{meterTarget}}`, `{{meterValueLabel}}`, `{{meterTargetLabel}}`, `{{meterStatus}}`, `{{meterBands}}` — meter showing commit vs quota if all slip (bands = array of `{ from, to, variant, label }` for Miss/Close/Make zones)
- `{{waterfallCaption}}`, `{{waterfallStart}}` (object `{ label, value }`), `{{waterfallSteps}}` (array of `{ label, delta }` with negative deltas for slips), `{{waterfallEnd}}` (object `{ label }`) — waterfall from today's commit to downside
- `{{datagridCaption}}`, `{{datagridRows}}` — at-risk deals, each row: `{ deal, amount, close, prob, block, _tone, _status }` (high-risk: `_tone: "error"` + `_status: "High"`; medium: `_tone: "warning"` + `_status: "Medium"`)
- `{{calloutTitle}}`, `{{calloutDescription}}`, `{{primaryButtonLabel}}`, `{{primaryButtonContent}}`, `{{secondaryButtonLabel}}`, `{{secondaryButtonContent}}` — synthesis callout with action buttons
- `{{meterMax}}` > `{{meterTarget}}` so "Make" band has width

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
                  { "definition": "tile/icon", "attributes": { "name": "alert-triangle", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{title}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{headerStatus}}", "variant": "error" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "lg", "align": "stretch", "isWrapped": true },
            "children": [
              {
                "definition": "tile/meter",
                "attributes": {
                  "label": "{{meterLabel}}",
                  "value": "{{meterValue}}",
                  "min": 0,
                  "max": "{{meterMax}}",
                  "target": "{{meterTarget}}",
                  "valueFormat": "currency",
                  "valueLabel": "{{meterValueLabel}}",
                  "targetLabel": "{{meterTargetLabel}}",
                  "status": "{{meterStatus}}",
                  "size": "lg",
                  "bands": "{{meterBands}}"
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
              "defaultSort": { "key": "amount", "direction": "desc" },
              "columns": [
                { "key": "deal", "header": "Deal", "type": "text" },
                { "key": "amount", "header": "Commit", "type": "currency", "align": "right", "sortable": true },
                { "key": "close", "header": "Close", "type": "date" },
                { "key": "prob", "header": "Slip risk", "type": "databar", "target": 100 },
                { "key": "block", "header": "What's blocking", "type": "text" }
              ],
              "rows": "{{datagridRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "warning",
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
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{primaryButtonContent}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{secondaryButtonLabel}}",
                      "variant": "secondary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{secondaryButtonContent}}" } }
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

**Self-verification:**
- [ ] Every `{{token}}` replaced, no `{!…}` expressions
- [ ] Numeric attributes are numbers, not strings
- [ ] Meter `max` > `target`, "Make" band spans `[quota, max]`
- [ ] Risky rows carry both `_tone` and `_status`; low-risk rows carry neither
- [ ] Text produced only when `display_widget` is unavailable (terminal fallback)

