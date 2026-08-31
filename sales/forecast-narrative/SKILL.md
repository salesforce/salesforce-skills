---
name: forecast-narrative
description: Generate the commit / best-case / pipeline narrative for a forecast call or 1:1 - what's closing, what's at risk, what changed since last time. Use when the user asks "write my forecast", "forecast narrative", "prep for forecast call", or runs /forecast.
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


# Forecast Narrative

Ground → aggregate the number + sample the deals (ONE turn) → narrative. Scope: my forecast (default), or a named rep/team. Period: current quarter (default).

## 1. Ground (hardcoded — Opportunity only)

Opportunity always exists; naming a missing object fails the whole call. Its fields reveal this org's ForecastCategory/StageName picklists + any custom forecast/override `__c` fields — use exact names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } } } }\"}" })
```

## 2. AGGREGATE the number, SAMPLE the deals — ISSUE BOTH IN ONE TURN

**Don't compute the number from a `first: N` page.** A raw pull caps at its page (`first: 200` returns 200 rows, not the book) — summing that page silently under-reports the total on a large book, and the first page isn't the whole set. Salesforce aggregates the totals server-side; use that for the number, and pull only a small bounded sample for the per-deal commentary.

`scope: MINE` = running user's book (no user lookup). `%QSTART%`/`%QEND%` = quarter's first/last day as explicit `YYYY-MM-DD` (never a quarter-relative literal — a bare `THIS_QUARTER` silently empties as boundaries move). Bound **both** ends of `CloseDate` — an open-ended `gte` pulls next-quarter+ deals into the current number. **Named rep/team:** swap `scope: MINE` for `OwnerId: { eq: \"<UserId>\" }`; for a team rollup, add `Owner { Name { value } }` to the sample so each deal attributes to its rep.

**2a. The number — aggregate by ForecastCategory (accurate at any volume).** One row per forecast bucket: count + $ sum. This is "The Number" table and it reconciles by construction — no page cap, no client-side sum of a truncated page.
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { aggregate { Opportunity(scope: MINE, where: { CloseDate: { gte: { value: \\\"%QSTART%\\\" }, lte: { value: \\\"%QEND%\\\" } } }, groupBy: { ForecastCategory: { group: true } }) { edges { node { aggregate { ForecastCategory { value } Id { count { value } } Amount { sum { value } } } } } totalCount } } } }\"}" })
```
`ForecastCategory` maps to the buckets: **Closed** = Closed Won (in the bank), **Commit**, **Best Case**, **Pipeline**; **Omitted** = drop (closed-lost/omitted). Org doesn't populate `ForecastCategory` → swap `groupBy` to `StageName` and infer buckets from the stage map (ask once if unclear). **If the `aggregate` query errors** (some orgs throw `DataFetchingException` grouping a picklist) → don't re-fire the same shape; fall to the SOQL `GROUP BY` equivalent:
```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT ForecastCategory, COUNT(Id) cnt, SUM(Amount) amt FROM Opportunity WHERE OwnerId = '%OWNERID%' AND CloseDate >= %QSTART% AND CloseDate <= %QEND% GROUP BY ForecastCategory" })
```
SOQL has no `scope: MINE`, so scope it by owner Id — without the `OwnerId` clause this fallback returns the whole org, not your book. `%OWNERID%` = the running user's Id for "my forecast"; resolve it with one `currentUser` read (needs **v66.0** — the GraphQL endpoint otherwise pins v65.0, so bump the version for this one call):
```
dispatch_readonly(method: "GET", url: "/services/data/v66.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { currentUser { Id } } }\"}" })
```
For a named rep/team, `%OWNERID%` is the `UserId` you already resolved for 2a's `OwnerId: { eq }` (or filter `Owner.Name` instead) — no `currentUser` lookup needed.

**2b. Sample the deals for commentary (bounded raw — Commit/Best Case lines).** The aggregate gives the number; this gives named deals to comment on. Cap hard (`first: 50`, biggest first) so it never overflows — this is a sample, not the book. Splice confirmed `__c` fields into `<OPP_CUSTOM>`. **Check `{` vs `}` balance before dispatching** — splicing `<OPP_CUSTOM>` is where a brace drops.
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(scope: MINE, where: { IsClosed: { eq: false }, CloseDate: { gte: { value: \\\"%QSTART%\\\" }, lte: { value: \\\"%QEND%\\\" } } }, orderBy: { Amount: { order: DESC } }, first: 50) { edges { node { Id Name { value } StageName { value displayValue } ForecastCategory { value displayValue } Amount { value displayValue } CloseDate { value } Probability { value } NextStep { value } LastActivityDate { value } <OPP_CUSTOM> Account { Name { value } } Owner { Name { value } } } } } } } }\"}" })
```

`InvalidSyntax` / "offending token `<EOF>`" → missing a closing `}`; add it and retry (once, with corrected text — never re-send identical text).

## 3. Bucket (in-prompt — no extra reads)

**The Number comes from 2a's aggregate** — count + $ per bucket (Closed Won / Commit / Best Case / Pipeline), whole-book and reconciled; drop the Omitted/closed-lost row. **Per-deal commentary comes from 2b's sample** — the top-by-Amount Commit and Best Case deals (the ones that matter for the call). Prefer `ForecastCategory`; else infer from `StageName` (never invent bucketing — infer from the org's stages or ask once). Say the per-deal lines are the top deals sampled, while the bucket totals are whole-book from the aggregate.

## 4. Changes + commentary

Prior snapshot pasted → diff it (up / slipped / added / lost). No snapshot → pull this quarter's field history for the delta (SOQL only — `OpportunityFieldHistory` has no GraphQL form), and only skip the section if that too is empty/unavailable:
```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT OpportunityId, Field, OldValue, NewValue, CreatedDate FROM OpportunityFieldHistory WHERE CreatedDate >= %QSTART% AND Field IN ('StageName','Amount','CloseDate') ORDER BY CreatedDate DESC" })
```
Derive moved-up / slipped / added / lost from those rows. Per **Commit**/**Best Case** deal, one grounded line — status, what's needed, risk (cite `NextStep`/`LastActivityDate`). Link each deal. **Leader/team rollup across many reps:** cap per-deal commentary to top 5 by Amount per rep.

## 5. Widget (default output when `display_widget` is present: Cowork/desktop/web)

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

The widget template is embedded below — a widget-definition envelope whose leaf values carry {{token}} placeholders. Resolve every {{token}} to a literal (no {{…}}/{!…} left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a {{token}} becomes the typed literal — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string is interpolated as text. Tokens: strings `title headerStatus subtitle meterLabel meterValueLabel meterTargetLabel meterStatus waterfallCaption datagridCaption calloutTitle calloutDescription primaryButtonLabel primaryButtonContent secondaryButtonLabel secondaryButtonContent` · numbers `meterValue meterMax meterTarget` · objects `waterfallStart` ({label,value}) `waterfallEnd` ({label}) · arrays `meterBands` ([{from,to,variant,label}]) `waterfallSteps` ([{label,delta}]) `datagridRows` ([{name (plain string — format as the opportunity name (e.g. "Meridian Health platform"); names must be plain strings, not objects: use `Opportunity.Name.value` from the SF response),amount,prob,close(YYYY-MM-DD),call:{value,badgeVariant},_tone,_status}] — set `_tone:"warning"` + `_status` for at-risk rows: Best Case, or Commit with blank NextStep or 7d+ stale LastActivityDate; healthy Commit rows omit _tone).

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
                  { "definition": "tile/icon", "attributes": { "name": "trending-up", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{title}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{headerStatus}}", "variant": "warning" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

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
              "showValues": true,
              "size": "lg",
              "start": "{{waterfallStart}}",
              "steps": "{{waterfallSteps}}",
              "end": "{{waterfallEnd}}"
            }
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{datagridCaption}}",
              "appearance": "striped",
              "defaultSort": { "key": "amount", "direction": "desc" },
              "columns": [
                { "key": "name", "header": "Deal", "type": "text" },
                { "key": "amount", "header": "Amount", "type": "currency", "align": "right", "sortable": true },
                { "key": "prob", "header": "Prob.", "type": "number", "align": "right" },
                { "key": "close", "header": "Close", "type": "date" },
                { "key": "call", "header": "My call", "type": "badge" }
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


> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.
## 6. Text — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Forecast — <Scope> — <Period>
## The Number
| | $ | # |
|---|---|---|
| Closed Won | $<X> | <N> |
| Commit | $<X> | <N> |
| Best Case | $<X> | <N> |
| Pipeline | $<X> | <N> |
| **Commit Total** | **$<Closed+Commit>** | |

## Changes Since Last Week
- ⬆/⬇/✅/❌ <Deal> … (or "No prior snapshot — skipping delta")

## Commit Deals
- **<Account>** $<X> closing <Date> — <status, what's needed, risk>

## Best Case Deals
- **<Account>** $<X> — <what gets it to commit>

## Risk to Commit
- <Deal + specific risk + mitigation>

## On the Radar
- <Pipeline/Best-Case deals that could pull INTO the number if accelerated, or slip OUT — the upside/downside not yet in Commit>

## Asks
- <exec help / resourcing / unblocks>
```
**Concentration callout:** if a single deal is a large share (~40%+) of the Commit number, call it out explicitly — a single-deal quarter is a risk headline, not a footnote.

ForecastCategory should change? Offer `update-opportunity` (one field, on confirmation). "What if <deal> slips?" → `deal-slip-scenario`. Submission stays manual.
