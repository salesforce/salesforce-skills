---
name: rep-context
description: Leader's catch-up on a single rep before a 1:1 - their pipeline, recent activity, what they've been working on per Slack and calendar, and where they might need help. Use when the user asks "catch me up on [rep]", "prep for my 1:1 with [name]", "what's [rep] working on", "how is [rep] doing", or "brief me on [rep]". IMPORTANT: This is for MANAGERS prepping for 1:1s with their SALES REPS - the person named is an internal team member, not a customer contact. If the user is prepping for a meeting with a CUSTOMER contact, use call-prep instead.
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


# Rep Context

Leader's 1:1 prep on one rep — pipeline, activity, where they're stuck. The named person is an INTERNAL rep (not a customer). Ground → read (pipeline + activity, one turn) → needs-help + questions.

## 1. Ground (hardcoded — Opportunity only)

Opportunity always exists; naming a missing object fails the whole call. Its fields reveal this org's risk/health/next-step `__c` fields — use exact names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } } } }\"}" })
```

## 2. Read the rep's book + activity (one turn)

Filter by `Owner: { Name: { like: "%REP%" } }` (the rep's name/email). Splice confirmed `__c` fields into `<OPP_CUSTOM>`. **Check `{` vs `}` balance before dispatching.**

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { Owner: { Name: { like: \\\"%REP%\\\" } }, IsClosed: { eq: false } }, orderBy: { Amount: { order: DESC } }, first: 100) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } NextStep { value } LastActivityDate { value } <OPP_CUSTOM> Account { Name { value } } OpportunityContactRoles { edges { node { Id } } } } } } } } }\"}" })
```

In the SAME turn, fire the rep's recent activity — both Tasks AND Events (last 14d), plus this-quarter closed-won for the "This Q closed" number. These are independent reads keyed on the rep name (not on each other), so batch all of them in this one turn — no added round-trip depth:

```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT Subject, ActivityDate, TaskSubtype, Status FROM Task WHERE Owner.Name LIKE '%REP%' AND ActivityDate >= LAST_N_DAYS:14 ORDER BY ActivityDate DESC" })

dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT Subject, ActivityDate, EventSubtype FROM Event WHERE Owner.Name LIKE '%REP%' AND ActivityDate >= LAST_N_DAYS:14 ORDER BY ActivityDate DESC" })

dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT SUM(Amount) amt, COUNT(Id) cnt FROM Opportunity WHERE Owner.Name LIKE '%REP%' AND IsWon = true AND CloseDate = THIS_QUARTER" })
```

Count logged meetings from the Event read alongside Tasks toward the activity tally. `InvalidSyntax` / "offending token `<EOF>`" → missing a closing `}`; add it and retry.

## 2b. Evidence (same turn — skip silently if absent)

- **Slack**: rep's posts in team/deal channels last 14d — blockers, asks, exec/deal-desk flags. (Ask once which channels if unknown.)
- **calendar**: external meetings last 14d + booked next 7d, if visible.

## 3. Analyze (cite records/threads; invent nothing)

From pipeline + activity: largest opp with risk flags (stale LastActivityDate, blank NextStep, single-threaded = ≤1 contact role); any opp a Slack post flags a blocker on; coverage gap if pipeline thin; hygiene if many stale.

## 4. 1:1 questions

3–4 specific, grounded questions — not "how's pipeline" but "[Account] at [Stage] [N] days, you flagged a security review in Slack — where's that?"

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

The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. The widget is the output when `display_widget` is available; produce the text below only as the fallback when it's unavailable (e.g. a terminal). Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (chart categories/series, piechart slices, datagrid rows) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text. Tokens: `{{pageTitle}}` header title (users icon) + `{{headerStatus}}` status badge (e.g. "BEHIND PACE", variant error) + `{{subtitle}}` quarter/attainment subhead; two wrapped graphs — column chart with `{{chartCategories}}` (quarter-label string array) and `{{chartSeries}}` (`[{ name, data }]`, data a number array, valueFormat percent, showValues), and piechart with `{{pieCenter}}` center value + `{{pieSlices}}` (`[{ label, value, role? }]`, one per stage, mark the largest/riskiest `"role":"highlight"`); `{{gridRows}}` top-open-deals datagrid (`[{ deal (plain string — format as the account name (e.g. "Cobalt Robotics"); names must be plain strings, not objects: use `Account.Name.value` from the SF GraphQL response), amount (number), stage ({ value, badgeVariant }: warning stalled/Negotiation, info Proposal/advancing), age (number), next, _tone (error|warning|info), _status (At risk|Coach|Advance) }]`, ranked by amount desc, `_tone`/`_status` on deals needing attention); `{{synthTitle}}`/`{{synthDescription}}` synthesis callout (variant warning) with two action/sendMessage buttons — primary `{{primaryLabel}}`/`{{primaryPrompt}}` (biggest gap / pipeline generation), secondary `{{secondaryLabel}}`/`{{secondaryPrompt}}` (most urgent deal / unstick the stalled deal). Before calling: every `{{token}}` resolved (no `{{…}}`/`{!…}`); exactly 2 graphs (column + piechart); datagrid `amount`/`age` numbers and `stage` a badge object, rows carry `_tone`/`_status` where needed; callout has 2 real sendMessage buttons; the text section below is produced only when `display_widget` is unavailable.

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
                  { "definition": "tile/icon", "attributes": { "name": "users", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{pageTitle}}", "variant": "page-title" } }
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
                "definition": "tile/chart",
                "attributes": {
                  "chartType": "column",
                  "caption": "Attainment by quarter — trending down",
                  "categories": "{{chartCategories}}",
                  "series": "{{chartSeries}}",
                  "valueFormat": "percent",
                  "showValues": true,
                  "showLegend": false
                }
              },
              {
                "definition": "tile/piechart",
                "attributes": {
                  "caption": "Open pipeline by stage",
                  "variant": "donut",
                  "valueFormat": "currency",
                  "centerLabel": "Open",
                  "centerValue": "{{pieCenter}}",
                  "slices": "{{pieSlices}}"
                }
              }
            ]
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Top open deals — where to coach",
              "appearance": "striped",
              "defaultSort": { "key": "amount", "direction": "desc" },
              "columns": [
                { "key": "deal", "header": "Deal", "type": "text" },
                { "key": "amount", "header": "Amount", "type": "currency", "align": "right", "sortable": true },
                { "key": "stage", "header": "Stage", "type": "badge" },
                { "key": "age", "header": "Age (d)", "type": "number", "align": "right" },
                { "key": "next", "header": "Next step", "type": "text" }
              ],
              "rows": "{{gridRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "warning",
              "title": "{{synthTitle}}",
              "description": "{{synthDescription}}"
            },
            "children": [
              {
                "definition": "tile/row",
                "attributes": { "gap": "sm", "align": "center", "isWrapped": true },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{primaryLabel}}",
                      "variant": "primary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{primaryPrompt}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{secondaryLabel}}",
                      "variant": "secondary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{secondaryPrompt}}" } }
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
# Rep Context: <Name>
## Pipeline
- Open: <N> opps, $<total> | by stage: <counts> | This Q closed: $<X> (<N> won)
- Top 3: **<Account>** $<X> <Stage> …
## Last 2 Weeks
- <N> activities logged; <N> external meetings (if calendar visible)
- Slack: <1–2 lines of what they raised — link threads>
## Likely Needs Help On
- **<Account>** $<X> — <specific flag + evidence>
## 1:1 Questions
1. <deal-specific, evidenced>
## Wins to Acknowledge
- <closed / advanced / notable from Slack>
```
