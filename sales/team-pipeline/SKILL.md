---
name: team-pipeline
description: Leader view - roll up a team's pipeline by rep and stage, flag at-risk deals, and surface coaching moments. Use when the user asks "show my team's pipeline", "team forecast", "team's deals", "my team's opportunities", "prep for pipeline review", or "where does my team need help". IMPORTANT: This is for MANAGERS viewing their TEAM - if the user says "my pipeline" without "team", use pipeline-review instead.
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


# Team Pipeline

Ground → resolve team → read opps → analyze → output. **No per-opp SF follow-ups** — the team opps read has the data.

## 1. Ground (hardcoded — User + Opportunity)

Ground **User** (for team resolution) and **Opportunity** (for pipeline fields). Both always exist. **Fire as two separate calls, not one combined call** — combined User+Opportunity ObjectInfo commonly exceeds the tool's char limit, and recovering from that overflow (temp file outside the bash mount, failed `cat`, retry) costs far more than just issuing two calls up front. Same turn, same shape, one `apiNames` each:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"User\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })

dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

**If either still overflows**, the result auto-persists to a temp file **outside the bash mount** — don't shell to it (`cat`/`python3`/`ls` will fail, it's not on that mount). Read it back with the Read tool only, and go straight to that — don't retry bash first. If the Read tool can't load it either, skip custom-field grounding for that object and proceed with standard fields only; don't keep retrying.

From the result: (a) scalar `__c` fields (quota, forecast, risk, etc.) — take their `{ value }`; (b) each lookup field's exact `relationshipName` to span for a related record's Name; (c) each child `relationshipName`.

## 2. Resolve team

**"my team"** (default) — reps where Manager = current user:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { User(where: { and: [{ ManagerId: { eq: \\\"<CURRENT_USER_ID>\\\" } }, { IsActive: { eq: true } }] }, first: 50) { edges { node { Id Name { value } Email { value } <USER_CUSTOM> } } } } } }\"}" })
```

**A named list, role, or territory** (disambiguate — do NOT probe): shared/demo orgs collide hard on name (one name → base user plus regional variants like `(AM)`/`(BK)`/`(SG)`). Pull enough to disambiguate at a glance — never pull each candidate's pipeline to guess which is real:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { User(where: { Name: { like: \\\"%REP%\\\" } }, first: 10) { edges { node { Id Name { value } Title { value } IsActive { value } } } } } } }\"}" })
```

**One match per name** → take its Id. **Several** → list them (Name · Title · active? · Id) and ask the user to pick; the suffix/title is usually the tell. Don't guess.

Insert `<USER_CUSTOM>` = confirmed scalar `__c { value }` fields (quota, etc.). Capture the Ids — they become the owner filter in step 3.

## 3. Read team opps — AGGREGATE the rollup, SAMPLE the top deals, ISSUE ALL IN ONE TURN

**Do not pull the whole team's book as raw records.** A team of 5+ reps with 200 open opps returns well past the point a tool result overflows and auto-persists to a temp file (then you can't shell to it — it's outside the bash mount; same overflow `pipeline-review` hit). Salesforce aggregates server-side — use it for the scoreboard math; only a small, bounded sample of concrete deals comes back as raw records, for swing-deal specifics and at-risk flags.

Fire these as tool calls in **one turn** (independent, all filtered by the team-user Ids from step 2). Insert `<OPP_CUSTOM>` = confirmed scalar `__c { value }` fields (risk, coaching signals, etc.) on the sample query only — aggregates don't need them.

**Date filters take a `DateInput` object, never a bare string** (`gte: \"2026-07-01\"` fails `WrongType … must be an object type`). For the current-quarter bounds below, use the exact-date form on both ends: `{ value: \"YYYY-MM-DD\" }`. Multiple ops on one field (`gte`/`lte`) AND automatically — no `and: [...]` wrapper needed around them.

**Rollup by forecast category (GraphQL aggregate).** `ExpectedRevenue` (Amount × Probability, a standard field) sums straight to the Weighted column — no client-side probability math:
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { aggregate { Opportunity(where: { OwnerId: { in: [<TEAM_USER_IDS>] }, IsClosed: { eq: false }, CloseDate: { gte: { value: \\\"<Q_START>\\\" }, lte: { value: \\\"<Q_END>\\\" } } }, groupBy: { OwnerId: { group: true }, ForecastCategory: { group: true } }) { edges { node { aggregate { OwnerId { value } ForecastCategory { value } Id { count { value } } Amount { sum { value } } ExpectedRevenue { sum { value } } } } } } } } }\"}" })
```
One row per rep × forecast category. Per rep: Commit $ = that rep's `Commit`-category `Amount.sum`; Best-case $ = the `BestCase` row; Weighted = Σ `ExpectedRevenue.sum` across that rep's rows.

**Closed-won this period, per rep (GraphQL aggregate).** Feeds the scoreboard's Closed column:
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { aggregate { Opportunity(where: { OwnerId: { in: [<TEAM_USER_IDS>] }, IsWon: { eq: true }, CloseDate: { gte: { value: \\\"<Q_START>\\\" }, lte: { value: \\\"<Q_END>\\\" } } }, groupBy: { OwnerId: { group: true } }) { edges { node { aggregate { OwnerId { value } Id { count { value } } Amount { sum { value } } } } } } } } }\"}" })
```

**Top-N sample per rep (raw — bounded, for concrete specifics).** The rollups give the numbers; this gives named deals for the swing-deal writeups, at-risk flags, hygiene flags, and Monday questions below. Cap hard (`first: 60`, biggest first) so it never overflows — this is a sample, not the book. **`orderBy` takes only ONE field** — a multi-field array (`orderBy: [{...},{...},{...}]`) fails `WrongType ... must be an object type`; sort by `Amount` alone and group by owner client-side from the `Owner.Name` on each row.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { OwnerId: { in: [<TEAM_USER_IDS>] }, IsClosed: { eq: false }, CloseDate: { gte: { value: \\\"<Q_START>\\\" }, lte: { value: \\\"<Q_END>\\\" } } }, orderBy: { Amount: { order: DESC } }, first: 60) { edges { node { Id Name { value } StageName { value displayValue } ForecastCategory { value } Amount { value displayValue } CloseDate { value } NextStep { value } LastActivityDate { value } CreatedDate { value } Probability { value } <OPP_CUSTOM> Account { Name { value } } Owner { Name { value } } } } } } } }\"}" })
```

Map each row's `OwnerId` → rep name using the User list from step 2 — no extra lookup needed.

**If a GraphQL `aggregate` query errors** (some orgs throw grouping a picklist/Id field), don't retry the same shape — fall to the SOQL `GROUP BY` equivalent, which groups cleanly:
```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT OwnerId, ForecastCategory, COUNT(Id) cnt, SUM(Amount) amt, SUM(ExpectedRevenue) weighted FROM Opportunity WHERE OwnerId IN (<TEAM_USER_IDS>) AND IsClosed = false AND CloseDate >= <Q_START> AND CloseDate <= <Q_END> GROUP BY OwnerId, ForecastCategory" })
```
(Closed-won the same way: swap `IsClosed = false` for `IsWon = true` and drop the `ForecastCategory` group.)

**Hygiene counts (GraphQL aggregate, full book — feeds step 6, not sample-limited).** The top-60 sample above skews toward the biggest deals; these three counts cover every open opp so stale/overdue/blank-NextStep flags aren't undercounted. `<STALE_CUTOFF>` = today − 14 days, `<TODAY>` = today, both as `DateInput` (`{ value: "YYYY-MM-DD" }`):
```
-- Stale 14d+, per rep
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { aggregate { Opportunity(where: { OwnerId: { in: [<TEAM_USER_IDS>] }, IsClosed: { eq: false }, LastActivityDate: { lte: { value: \\\"<STALE_CUTOFF>\\\" } } }, groupBy: { OwnerId: { group: true } }) { edges { node { aggregate { OwnerId { value } Id { count { value } } } } } } } } }\"}" })

-- Past CloseDate, per rep
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { aggregate { Opportunity(where: { OwnerId: { in: [<TEAM_USER_IDS>] }, IsClosed: { eq: false }, CloseDate: { lt: { value: \\\"<TODAY>\\\" } } }, groupBy: { OwnerId: { group: true } }) { edges { node { aggregate { OwnerId { value } Id { count { value } } } } } } } } }\"}" })

-- Blank NextStep, per rep
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { aggregate { Opportunity(where: { OwnerId: { in: [<TEAM_USER_IDS>] }, IsClosed: { eq: false }, NextStep: { eq: null } }, groupBy: { OwnerId: { group: true } }) { edges { node { aggregate { OwnerId { value } Id { count { value } } } } } } } } }\"}" })
```
Fire these in the same turn as the rollup/closed-won/sample queries above. If `aggregate` errors on any of the three, fall to SOQL `COUNT(Id) ... GROUP BY OwnerId` with the matching WHERE (same fallback pattern as the rollup above).

**Perf guardrail:** Do NOT fire per-opp SF follow-ups (`EmailMessage`, `Task`, `OpportunityFieldHistory`) — the rollups + sample above already have the data. Email/doc/Slack searches for flagged accounts only (step 3b).

## 3b. Evidence (run IN PARALLEL with step 3 — same turn)

**Issue step 3 and step 3b as tool calls in a single turn.** Fire email/doc/Slack searches for top 3–5 at-risk accounts only (keyed on account name, not the SF result):
- **slack**: internal mentions in team channel (if configured) → reps already flagging something

Use whatever Slack search tools are available. If none present, skip silently. Cite source + date for anything you use.

## 4. Per-rep scoreboard

For each rep, compute and assign a one-word **Call**:

| Rep | Closed | Commit | Weighted | vs Quota | Call |
|---|---|---|---|---|---|

- **Weighted** = sum of (Amount × Probability/100) across open opps
- **Call** = Ahead (closed ≥ quota or weighted comfortably covers gap) / On-track / Behind
- Tip: if a rep's Commit > Weighted, their stages are probably optimistic — challenge it.

If quotas aren't in SFDC, ask once and remember for the session.

## 5. Deals that decide the quarter

Identify the 3–5 opps that swing the number: large Amount × late stage × rep-needs-it × closing this period. For each, write three lines:

- **Why it matters:** [the math — "$X is N% of [rep]'s gap"]
- **Risk:** [specific thing that could kill it, from evidence]
- **Do this:** [one concrete leader action — "ask [rep] when they last talked to procurement; offer to send exec note if it's been 5+ days"]

The "do this" is the point. Be specific enough that the leader can act without further research.

## 6. Team-level flags

- **At-risk Commit deals:** any Commit-category deal with risk flags — these threaten the number
- **Coaching signals:** reps with high stale-% (from the hygiene aggregates above, full book) or low coverage
- **Hygiene:** reps ranked by the stale/past-CloseDate/blank-NextStep aggregate counts (full book, not the sample) — name specific accounts from the top-60 sample where they overlap
- **Big swings:** deals >2x average that could make or break the quarter

## 7. Monday questions

For each Behind or At-risk rep, write ONE question phrased the way the leader would actually ask it in a 1:1 or Slack. Grounded in a specific deal, conversational, not interrogative. Examples: "where's the [Account] security review at — saw it's been a couple weeks" / "do you need anything from me on [Account] or is it just waiting on them."

Search Slack for each rep's recent posts in the team channel from config — if they already flagged something, reference it instead of re-asking.


## 8. Output — widget FIRST (the rendered UI is the default)

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

If `display_widget` is available (Cowork/desktop/web), the widget IS the output; produce the text section below only as the fallback when `display_widget` is unavailable (e.g. a terminal). The widget template is embedded below — a widget-definition envelope whose leaf values carry {{token}} placeholders. Resolve every {{token}} to a literal (no {{…}}/{!…} left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a {{token}} becomes the typed literal — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string is interpolated as text.

Tokens: `title` (page title string) · `headerStatus` (badge label) · `subtitle` (one-line summary) · `chartCaption chartCategories chartSeries` (chart title, rep names array, series array of `{name, data}` objects) · `meterLabel meterValue meterMax meterTarget meterValueLabel meterTargetLabel meterStatus meterBands` (meter scalars + bands array) · `datagridCaption datagridRows` (grid title + rows array, each row: `{rep (plain string — format as the rep's display name (e.g. "Priya Nair"); names must be plain strings, not objects: use `Owner.Name.value` from the SF GraphQL response), plan, closed, commit, gap, attain, _tone?, _status?}`) · `calloutTitle calloutDescription ctaPrimaryLabel ctaPrimaryMsg ctaSecondaryLabel ctaSecondaryMsg` (callout text + button labels/actions).

Chart series are FORECAST categories (Proposal / Negotiation / Closing), not sales stage — `chartSeries` has three `{name, data}` objects, each `data` array holding one raw-dollar value per rep, matching `chartCategories` order. Datagrid rows: `plan`/`closed`/`commit`/`gap` are raw currency numbers, `attain` is 0–100 percentage; set `_tone` (error/warning/success) and `_status` (Behind/At risk/Ahead) only on risky rows.

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
                  { "definition": "tile/text", "attributes": { "text": "{{title}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{headerStatus}}", "variant": "warning" } }
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
                  "caption": "{{chartCaption}}",
                  "categories": "{{chartCategories}}",
                  "series": "{{chartSeries}}",
                  "stackMode": "stacked",
                  "valueFormat": "compact",
                  "showValues": false
                }
              },
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
                  "bands": "{{meterBands}}"
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
              "defaultSort": { "key": "gap", "direction": "asc" },
              "columns": [
                { "key": "rep", "header": "Rep", "type": "avatar" },
                { "key": "plan", "header": "Plan", "type": "currency", "align": "right" },
                { "key": "closed", "header": "Closed", "type": "currency", "align": "right", "sortable": true },
                { "key": "commit", "header": "Commit", "type": "currency", "align": "right" },
                { "key": "gap", "header": "Gap to plan", "type": "currency", "align": "right", "sortable": true },
                { "key": "attain", "header": "Attainment", "type": "databar", "target": 100 }
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
                      "label": "{{ctaPrimaryLabel}}",
                      "variant": "primary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{ctaPrimaryMsg}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{ctaSecondaryLabel}}",
                      "variant": "secondary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{ctaSecondaryMsg}}" } }
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

Self-verification before calling:
- [ ] Every `{{token}}` replaced with a resolved literal — no `{{…}}` left.
- [ ] One attainment meter only; its `value`/`max`/`target`/band bounds are dollar numbers (millions) and bands tile `0 → low% → mid% → plan` with `target` reachable below `max`.
- [ ] Chart has visible caption, `stackMode: "stacked"`, three series (Proposal / Negotiation / Closing) with one raw-dollar value per rep, matching `categories` length/order.
- [ ] Every datagrid currency cell is a raw number (not `{ value, display }` — the type annotation handles formatting).
- [ ] Risky datagrid rows carry `_tone` (error/warning) and `_status` (Behind/At risk); healthy/ahead rows carry `_tone: "success"` + `_status: "Ahead"` or omit both.
- [ ] Blocks with no data are omitted, not sent with empty arrays.
- [ ] Order is header → separator → (chart | meter) row → reps grid → callout last.



> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.
## 9. Text — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Team Pipeline - [Period]
Target $[X] | Closed $[X] | [N] days left

## Scoreboard
| Rep | Closed | Commit | Weighted | Gap | Call |
|---|---|---|---|---|---|
| [Name] | $[X] | $[X] | $[X] | $[X] | Behind |
...
| **Team** | **$[X]** | **$[X]** | **$[X]** | **$[X]** | |

## Deals That Decide the Quarter
**[Account]** - $[X], [Stage], [Rep]
  Why it matters: [the math]
  Risk: [specific, evidenced]
  → **Do this:** [one concrete leader action]

[repeat 3–5x]

## Risk Flags
- Pushed dates: [N] opps moved CloseDate this week
- Stale 14d+: [N] opps - [Account, Account, ...]
- Past close date: [N] opps need hygiene before the call

## Monday Questions
- **[Rep]:** "[one question, conversational, deal-grounded]"
- **[Rep]:** "[...]"

## If you want to dig
- Per-rep detail: ask "just [rep name]"
- Full at-risk list: run pipeline-review with team scope
```
