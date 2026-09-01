---
name: win-loss-review
description: Analyze recently closed opportunities to find patterns in what wins and what loses - stage of loss, common objections from transcripts, deal characteristics. Leader-focused. Use when the user asks "win loss review", "why are we losing deals", "what's working", or "analyze closed opps".
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

- Reconcile headline totals with the detail rows.

# Win-Loss Review

Ground → (read + evidence, ONE turn) → find patterns → output. Leader-focused: look across recently closed opportunities for patterns a leader can act on.

## Inputs

- **Scope:** "team" (default - all reps under leader) or a specific rep
- **Period:** last quarter (default) or specified range
- **Focus:** all / wins only / losses only

## 1. Ground (hardcoded — Opportunity only)

Ground **only Opportunity** — it always exists (naming a missing object fails the whole call). Its fields reveal this org's loss-reason `__c` schema; don't assume names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

Step 1 is the authority on names — use exact strings, never guess. Note the scalar `__c` field(s) that carry a loss-reason/lost-reason category — that's `<OPP_CUSTOM>` below. If none is grounded, omit it and rely on transcript/email evidence for loss reasons instead.

## 2. Read (fill from step 1)

Compute explicit `gte`/`lte` date-literal boundaries for the review period from today's date — do not use a relative literal like `LAST_N_DAYS:90`, it silently drifts the window as today moves. `scope: MINE` for "my closed deals"; swap for `OwnerId: { eq: \"<UserId>\" }` after resolving one User by name for a named rep (team default = no owner filter, all reps roll up together — ask once if genuinely ambiguous).

One call pulls every closed opportunity in the window — with `Account` spanned for industry/size AND the stage-history child nested (no separate round-trip). **Loss death-stage:** a lost opp's closing `StageName` is just "Closed Lost", so "where losses die" must come from the stage-history child — the last **non-closed** `StageName` before close. Nest `<HISTORY_CHILD>` = the OpportunityHistory child's exact `relationshipName` from Step 1 grounding (commonly `OpportunityHistories`); keep its `first:` small (history rows are tiny, but the child rides on up to 200 parents).

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(scope: MINE, where: { IsClosed: { eq: true }, CloseDate: { gte: { value: \\\"%START%\\\" }, lte: { value: \\\"%END%\\\" } } }, first: 200, orderBy: { Amount: { order: DESC } }) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } CreatedDate { value } LeadSource { value } Type { value } IsWon { value } <OPP_CUSTOM> Account { Name { value } Industry { value } NumberOfEmployees { value } } Owner { Name { value } } <HISTORY_CHILD>(first: 15, orderBy: { CreatedDate: { order: DESC } }) { edges { node { StageName { value } CreatedDate { value } } } } } } } } } } }\"}" })
```

Empty `edges` → no closed deals in this window/scope; say so plainly, skip the rest. `first: 200` is a bounded sample; if it truncates on a very high-volume team, note the cap rather than imply full coverage. **If the history child is empty/unavailable**, fall back to the record's final `StageName` for the death-stage line and omit the median-days-in-stage column — don't fire a separate history round-trip.

## 2b. Evidence (run IN PARALLEL with step 2 — same turn, issue all at once)

**Issue step 2 and all of step 2b as tool calls in a single turn — do not wait for the SF read to return before firing the searches.** They key on the account/rep names from the request, not the SF result:
- **docs**: call transcripts for the largest wins and losses (will narrow to the top 5 each once step 2 returns names, but a first broad pass can start now on account names already known from the request)
- **email**: late-stage threads on the same accounts → stated objections, loss reasons

Use whatever doc/email tools are available; skip silently if none are present (SFDC-only is fine). Cite source + date for anything you use.

## 3. Find patterns (record only; reconcile totals; invent nothing)

- **Win rate** overall and by: rep, lead source, deal size band, industry, type (new vs expansion)
- **Loss stage distribution:** where do losses die — the last **non-closed** `StageName` in each lost opp's history child (NOT "Closed Lost"). Most at Discovery? at Proposal? (Fall back to final `StageName` only if history is unavailable.)
- **Median days in stage:** from consecutive history-row `CreatedDate` deltas (omit if no history child).
- **Cycle length:** median days (`CloseDate` − `CreatedDate`) for wins vs losses
- **Size:** median Amount for wins vs losses
- **Qualitative:** for the 5 largest losses and 5 largest wins (by Amount, from step 2), pull the evidence gathered in 2b — stated loss reasons (competitor, budget, timing, no decision), objections in losses but not wins, what wins had in common. Cite specifics: "[Account] - lost at Proposal, transcript on [date] shows pricing objection with no follow-up."

## 4. Output — widget FIRST (the rendered UI is the default)

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

Layout note: the loss-reason donut runs with `showLegend:false` and sits in a row beside a text column (`donutAsideTitle` + `donutAside`); the win-rate column chart is full-width, preceded by a caption pair (`chartAsideTitle` + `chartAside`). A column chart must be full-width to keep its axis, value labels, and bar height legible — do not put it in a shared row.

Tokens: `title` (page-title text, e.g. "Win / loss review — last 2 quarters") · `subtitle` (one-line caption with closed count, win rate, won/lost $ totals) · `donutAsideTitle donutAside` (short title + one-sentence breakdown beside the loss-reason donut; because the legend is off, `donutAside` must name every slice with its count in prose — a colorblind reader relies on it) · `pieCaption pieSlices` (pie chart — `slices` is `[{label, value, role?}]`; top reason carries `role:"highlight"`) · `chartAsideTitle chartAside` (short title + one-sentence takeaway above the full-width win-rate chart; interpret the shape — e.g. the decline with deal size — rather than re-listing every band) · `chartCaption chartCategories chartSeries` (column chart — `categories` is size-band labels, `series` is an array with one object: `{name:"Win rate", data:[...numbers...]}` — these are win-RATE percentages, not deal counts) · `datagridCaption lossRows` (datagrid — `rows` is `[{name (plain string — format as the opportunity name (e.g. "Meridian Health platform"); names must be plain strings, not objects: use `Opportunity.Name.value` from the SF response), amount, stage:{value, badgeVariant}, reason, comp, _tone:"error", _status:"Lost"}]`, largest first; `amount` is a raw number; `comp` is competitor name or "—" for no-decision losses) · `calloutTitle calloutDescription button1Label button1Content reportUrl` (callout — primary button is `action/sendMessage` with a first-person `content` prompt; `reportUrl` is a Win/Loss report Lightning URL `https://<myDomain>/lightning/r/Report/<Id>/view`, opens new tab). Omit any block whose data you lack rather than passing empty arrays.

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
              }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "lg", "align": "center", "isWrapped": false },
            "children": [
              {
                "definition": "tile/piechart",
                "attributes": {
                  "variant": "donut",
                  "caption": "{{pieCaption}}",
                  "valueFormat": "number",
                  "showLegend": false,
                  "slices": "{{pieSlices}}"
                }
              },
              {
                "definition": "tile/row",
                "attributes": { "gap": "xs", "align": "start", "direction": "column", "width": "stretch" },
                "children": [
                  { "definition": "tile/text", "attributes": { "text": "{{donutAsideTitle}}", "variant": "section-title" } },
                  { "definition": "tile/text", "attributes": { "text": "{{donutAside}}", "variant": "body", "color": "muted" } }
                ]
              }
            ]
          },

          { "definition": "tile/text", "attributes": { "text": "{{chartAsideTitle}}", "variant": "section-title" } },
          { "definition": "tile/text", "attributes": { "text": "{{chartAside}}", "variant": "body", "color": "muted" } },

          {
            "definition": "tile/chart",
            "attributes": {
              "chartType": "column",
              "caption": "{{chartCaption}}",
              "categories": "{{chartCategories}}",
              "series": "{{chartSeries}}",
              "valueFormat": "number",
              "showValues": true,
              "showLegend": false
            }
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{datagridCaption}}",
              "appearance": "striped",
              "size": "sm",
              "defaultSort": { "key": "amount", "direction": "desc" },
              "columns": [
                { "key": "name", "header": "Opportunity", "type": "text" },
                { "key": "amount", "header": "Amount", "type": "currency", "align": "right", "sortable": true },
                { "key": "stage", "header": "Died at", "type": "badge" },
                { "key": "reason", "header": "Reason", "type": "text" },
                { "key": "comp", "header": "Lost to", "type": "text" }
              ],
              "rows": "{{lossRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "info",
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
                      "label": "View in Salesforce",
                      "variant": "secondary",
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{reportUrl}}" } }
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
## 5. Text — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Win-Loss Review — <Scope> — <Period>
**Headline:** <the pattern that matters most, 2 sentences>

## Win Rate
| Cut | Win Rate | n |
|---|---|---|
| Overall | <pct>% | <N> |
| By rep / source / size band / industry | <pct>% | <N> |

## Where Losses Die
| Stage | % of losses | Median days in stage |
|---|---|---|
| <Stage> | <pct>% | <N>d |
(Stage = last non-closed stage from history; omit the median-days column if no history child.)

## Loss Reasons
| Reason | Count | Example |
|---|---|---|
| <Reason> | <N> | <Account>: <one-line evidence w/ date+source> |

## What Wins Have In Common
- <pattern> (<N of M> wins) …

## Largest Losses
- **<Account>** $<X> — died at <Stage> — <one-line evidence>

## Recommended Actions
1. Systemic — <process/enablement tied to the headline>
2. Coaching — <which rep, on what>
3. Data — <what to start capturing>
```
