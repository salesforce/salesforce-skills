---
name: pipeline-review
description: Stage-by-stage pipeline health check - coverage, aging, conversion, and at-risk deals - from Salesforce opportunity data. Use when the user asks "review my pipeline", "my pipeline", "pipeline health", "where's my pipeline stuck", "show me my deals", or runs /pipeline. This is for an INDIVIDUAL REP'S pipeline - if the user asks about "my team's pipeline", use team-pipeline instead. IMPORTANT: If the user asks "what changed" or about CHANGES/SIGNALS, use deal-signals instead - this skill shows CURRENT STATE, not changes.
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

- Resolve scope to one owner before the read; if a named rep is ambiguous, ask — don't guess or probe.
- Reconcile headline totals with the detail rows.

# Pipeline Review

Ground → resolve scope → (aggregate the book + sample the top deals, ONE turn) → assemble + flag → output. This is one rep's pipeline — for "my team's pipeline" use team-pipeline; for "what changed" use deal-signals.

## 1. Ground (hardcoded — Opportunity only)

Ground **only Opportunity** — it always exists (naming a missing object fails the whole call). Its fields reveal this org's stage/risk/activity `__c` schema and the exact `relationshipName`s; don't assume names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label } } } }\"}" })
```

Step 1 is the authority on names — use exact strings, never guess. Note scalar `__c` fields worth rolling up (stage-entry date, risk, health, forecast). **Response can be large** on customized orgs — if it truncates and auto-persists to a temp file, that file is **outside the bash mount**: don't shell to it (`cat`/`jq`/`python3`/`ls` will fail, it's not on that mount). Read it back with the **Read tool only**, go straight there — don't retry bash first — and scan for `__c` fields whose `label` matches your keywords. Grounding is best-effort (customs are additive); if the Read tool can't load it either, take the standard fields and move on. Stage buckets come from the `StageName` values the reads return; standard fields, `Account`/`Owner` spans, and `OpportunityContactRoles` are reliable across orgs.

## 1b. Resolve scope

- **"my pipeline"** (default) → add `scope: MINE` to the query root — no user-Id lookup.
- **named rep** → resolve one User. Pull enough to disambiguate at a glance — shared/demo orgs collide hard (one name → base user plus regional variants like `(AM)`/`(BK)`/`(SG)`):
  ```
  dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
    queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { User(where: { Name: { like: \\\"%REP%\\\" } }, first: 10) { edges { node { Id Name { value } Title { value } IsActive { value } } } } } } }\"}" })
  ```
  **One match** → take its Id. **Several** → list them (Name · Title · active? · Id) and ask the user to pick; the suffix/title is usually the tell. Don't pick or probe their pipelines to guess. Then filter opps by `OwnerId: { eq: \"<UserId>\" }`.
- **team** → out of scope; hand to team-pipeline.

## 2. Read (fill from step 1) — AGGREGATE the book, SAMPLE the top deals, ISSUE ALL IN ONE TURN

**Do not pull the whole book as raw records.** A rep with 100+ open opps returns 75KB+, which overflows the tool result and auto-persists to a temp file (then you can't shell to it — it's outside the bash mount; you'd have to read it back directly). Salesforce aggregates server-side — use it. The stats come from aggregate rows (a handful, not hundreds); only a small, bounded sample of concrete deals comes back as raw records.

Fire these as tool calls in **one turn** (independent). Insert `<OPP_CUSTOM>` = confirmed `__c { value }` fields on the sample query only (aggregates don't need them).

**2a. Whole-book rollup by stage (GraphQL aggregate).** No `CloseDate` filter for a health view — a `THIS_QUARTER` filter silently drops deals as quarter boundaries move. If the user names a period, add explicit `CloseDate: { gte: … lte: … }`.
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { aggregate { Opportunity(scope: MINE, where: { IsClosed: { eq: false } }, groupBy: { StageName: { group: true } }) { edges { node { aggregate { StageName { value } Id { count { value } } Amount { sum { value } } } } } totalCount } } } }\"}" })
```
Returns one row per stage: stage name, count, $ sum. That's the by-stage table and the open total (Σ) — no record pull.

**2b. Top-N sample per stage (raw — bounded, for concrete specifics).** The rollup gives the shape; this gives named deals to point at. Cap hard (`first: 40`, biggest first) so it never overflows — this is a sample, not the book. Order by `Amount DESC`; take the top few per stage when you present.
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(scope: MINE, where: { IsClosed: { eq: false } }, first: 40, orderBy: { Amount: { order: DESC } }) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } CreatedDate { value } NextStep { value } LastActivityDate { value } Type { value } <OPP_CUSTOM> Account { Name { value } } OpportunityContactRoles { edges { node { Id } } } } } } } } }\"}" })
```

**2c. Closed-baseline win rate (GraphQL aggregate, last full quarter).** Counts grouped by won/lost — no record pull, zero date math (`eq: { literal: LAST_QUARTER }`; widen only if asked):
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { aggregate { Opportunity(scope: MINE, where: { IsClosed: { eq: true }, CloseDate: { eq: { literal: LAST_QUARTER } } }, groupBy: { IsWon: { group: true } }) { edges { node { aggregate { IsWon { value } Id { count { value } } Amount { sum { value } } } } } } } } }\"}" })
```

**2d. Whole-book hygiene by stage (GraphQL aggregate).** Blank-`NextStep` count per stage across the entire book — so the hygiene finding is book-wide, not "among the top 40 sampled". No date math:
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { aggregate { Opportunity(scope: MINE, where: { IsClosed: { eq: false }, NextStep: { eq: null } }, groupBy: { StageName: { group: true } }) { edges { node { aggregate { StageName { value } Id { count { value } } } } } } } } }\"}" })
```
(Same `OwnerId` swap for a named rep. A stale-by-stage rollup is also expressible with a computed `LastActivityDate: { lt: "<today−14d>" }` cutoff grouped by StageName — but null-activity rows won't match `lt`, so it under-counts never-touched deals; blank-NextStep is the clean whole-book signal.)

**Named rep** → swap every `scope: MINE` for `OwnerId: { eq: \"<UserId>\" }`. **Empty** 2a `edges`/`totalCount: 0` → no open pipeline for this scope; say so plainly, skip the rest.

**If a GraphQL `aggregate` query errors** (some orgs throw `DataFetchingException` grouping a picklist/Id field), don't retry the same shape — fall to the SOQL `GROUP BY` equivalent, which groups picklists cleanly:
```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT StageName, COUNT(Id) cnt, SUM(Amount) amt FROM Opportunity WHERE IsClosed = false AND OwnerId = '<UserId>' GROUP BY StageName" })
```
(Own scope → resolve the current user's Id first, or filter by `Owner.Name`; SOQL has no `scope: MINE`.) Win rate the same way: `SELECT IsWon, COUNT(Id) cnt FROM Opportunity WHERE IsClosed = true AND CloseDate = LAST_QUARTER AND OwnerId = '<UserId>' GROUP BY IsWon`.

## 3. Assemble + flag (record only; reconcile totals; invent nothing)

- **By stage** — straight from 2a's aggregate rows: count, $ sum per stage. Σ of stage $ = open total (they come from the same query, so they reconcile by construction). **Blank-NextStep per stage is whole-book from 2d** — report those counts as book-wide. Staleness/aging per-stage aren't in an aggregate; report those from the 2b sample and **say they're "among the top N sampled," not whole-book**.
- **Top deals per stage** — from the 2b sample, name the biggest 2–3 opps in each stage (Account · $ · close · next-step state · type) so the rep sees concrete deals, not just totals.
- **At-risk opps** — from the 2b sample, flag any that hit: stale (no activity 14d+) · past `CloseDate` · blank `NextStep` · **single-threaded (`OpportunityContactRoles` edge count ≤ 1)**. **If a flag matches nearly the whole sample** (e.g. every opp has a blank `NextStep`, common in lightly-maintained orgs), report it once as a **systemic finding** — use 2d's book-wide blank-NextStep count for that line ("next-step blank on N of M open — hygiene gap") — and rank the at-risk list by $, rather than dumping dozens of identical-looking rows.
- **Coverage** — weighted open pipeline (from 2a totals × stage probability if grounded, else raw open $) vs quota (only if the user gives one) or vs last-quarter closed $ from 2c; 3× remaining-gap heuristic; note if under.
- **Velocity** — from 2c: win rate = won ÷ (won+lost) counts. **Cycle time / median: don't compute it** — no API (GraphQL aggregate or SOQL) supports median or date subtraction, and reconstructing it means pulling every closed record (the overflow we're avoiding). Only report an average cycle if grounding surfaced a numeric sales-cycle `__c` field you can `avg` in the aggregate. Stage→stage conversion needs stage history; omit — don't fabricate.

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

- [ ] Every {{token}} replaced with a resolved literal — no {{…}}, no {!…}.
- [ ] Numeric attributes (meter value/max/target, meter band from/to, datagrid amount/age) are numbers, not strings.
- [ ] The meter bands span [0, max] and the chart series data matches categories length.
- [ ] Every datagrid row carries _tone (error/warning) for risky opps or omits it for healthy ones; _status is present.
- [ ] The callout carries resolved title/description, and both buttons are real actions (sendMessage/openLink).
- [ ] The Step 5 text is produced only when `display_widget` is unavailable (the terminal fallback) — not alongside a rendered widget.
- [ ] No prose written before or after this call — no input narration, no transition text, no summary (only applies when display_widget is available; if unavailable, produce the text fallback section below).
- [ ] I am producing zero prose before or after this call. If I am tempted to summarize findings, I must not.

If `display_widget` is available (Cowork/desktop/web), the widget IS the output; produce the text section below only as the fallback when `display_widget` is unavailable (e.g. a terminal). The widget template is embedded below — a widget-definition envelope whose leaf values carry {{token}} placeholders. Resolve every {{token}} to a literal (no {{…}}/{!…} left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a {{token}} becomes the typed literal — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string is interpolated as text. 

Tokens: `pageTitle` (e.g. "Pipeline review — Dana Ruiz"), `pageSubtitle` (one-line summary: "$6.4M open across 18 opps · weighted $2.1M · closes this quarter") · `chartCaption`, `chartCategories` (array of stage names), `chartSeries` (array with one object `{ name, data }` where data is number[] matching categories) · `coverageValue` (number), `coverageMax` (number), `coverageTarget` (number, typically 3.0), `coverageValueLabel` (e.g. "2.4× open pipeline to $2.7M gap"), `coverageTargetLabel` (e.g. "3.0× target"), `coverageStatus` (string: "under-covered" or "covered"), `coverageBands` (array of `{ from, to, variant, label }`, variants warning/success, spanning 0→max) · `datagridCaption` (e.g. "At-risk opps: stalled, past close date, or missing next step"), `datagridRows` (array, one per at-risk opp: `{name (plain string — format as the opportunity name (e.g. "Meridian Health platform"); names must be plain strings, not objects: use `Opportunity.Name.value` from the SF response), stage:{value,badgeVariant}, amount(number), age(number days in stage), close("YYYY-MM-DD"), risk, _tone(error/warning for risky rows or omit), _status}`) · `calloutVariant` ("info"), `calloutTitle` (e.g. "Monday focus"), `calloutDescription` (week's priorities), `primaryButtonLabel`, `primaryButtonMsg` (first-person prompt for sendMessage, e.g. "Draft an email to..."), `viewOppsUrl` (Opportunities list URL: `https://<myDomain>/lightning/o/Opportunity/list`). Omit any block whose data you lack rather than passing empty arrays; each `status` word must land in its meter band (under-covered/covered).

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
                  { "definition": "tile/icon", "attributes": { "name": "dashboard", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{pageTitle}}", "variant": "page-title" } }
                ]
              }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{pageSubtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "lg", "align": "stretch", "isWrapped": true },
            "children": [
              {
                "definition": "tile/chart",
                "attributes": {
                  "chartType": "column",
                  "caption": "{{chartCaption}}",
                  "categories": "{{chartCategories}}",
                  "series": "{{chartSeries}}",
                  "valueFormat": "compact",
                  "showValues": true,
                  "showLegend": false
                }
              },
              {
                "definition": "tile/meter",
                "attributes": {
                  "label": "Coverage vs remaining gap",
                  "value": "{{coverageValue}}",
                  "min": 0,
                  "max": "{{coverageMax}}",
                  "target": "{{coverageTarget}}",
                  "valueLabel": "{{coverageValueLabel}}",
                  "targetLabel": "{{coverageTargetLabel}}",
                  "status": "{{coverageStatus}}",
                  "bands": "{{coverageBands}}"
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
                { "key": "name", "header": "Opportunity", "type": "text" },
                { "key": "stage", "header": "Stage", "type": "badge" },
                { "key": "amount", "header": "Amount", "type": "currency", "align": "right", "sortable": true },
                { "key": "age", "header": "Days in stage", "type": "number", "align": "right", "sortable": true },
                { "key": "close", "header": "Close", "type": "date" },
                { "key": "risk", "header": "Risk", "type": "text" }
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
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{viewOppsUrl}}" } }
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
# Pipeline Review — <Scope> — <Period>

## Summary
Open: <N> opps, $<total> · weighted $<weighted> · coverage <N>× <✅ / ⚠ under 3×> · at-risk <N>, $<sum>

## By stage (whole book)
<Stage> · <N> opps · $<sum>
…  (Σ stage $ = $<total>, Σ opps = <N> — from the rollup)

## Top deals per stage (sampled, biggest first)
<Stage>: <Account> $<X> close <Date> · <next-step state> · <Type>; <Account> $<X> close <Date> …
… (name the biggest 2–3 opps per stage — the sample holds them)

## At-risk (from sample, biggest first)
<Account> · <Stage> · $<X> · close <Date> · <flags> → <action>
…  (Σ at-risk $ = $<sum>)
[If a flag hits nearly all sampled: one line — "Systemic: next-step blank on all <N> sampled — hygiene gap", don't list every row.]

## Conversion Signal (last-Q baseline)
Win rate <N%> (won <N> ÷ won+lost <N>, from 2c)[ · avg cycle <N>d only if a cycle-days field was grounded]. Stage→stage conversion needs stage history — omit, don't fabricate.

## Focus
1. Highest-$ at-risk + action
2. Biggest / most-exposed stage + action
3. Coverage gap if under 3×
```
