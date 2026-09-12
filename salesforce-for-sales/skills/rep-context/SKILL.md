---
name: rep-context
description: "Catch a manager up on one of their sales reps before a 1:1: the rep's pipeline, recent activity, what they are working on, and where they need help, with suggested questions. Use when the person named is an internal rep, not a customer contact."
---
<!-- global-rules-bootstrap -->
# Global Rules

- **Execute silently between tool calls.** Do not output planning, progress, transition, waiting, or tool-result narration between calls. Execute tool calls silently and proceed directly to the next call. Parallelize independent tasks by batching tool calls into one turn whenever possible. Before the final output, speak only when the skill explicitly requires user input, approval, an exact notice, or material error/blocked reporting. Do not invent checkpoints.
- **Keep the final output concise.** Return only the requested result or deliverable. Omit process recaps, tool-call details, redundant preambles or conclusions, and data already shown in a widget.
- **⛔ WIDGET OUTPUT ONLY after data assembly.** Once all queries return, immediately call `display_widget` — at most a single one-line render-wait notice before it, and no summaries, transitions, or narration. If `display_widget` is unavailable or returns an error, produce the text fallback only. If it succeeds, that tool call is the final output: stop with no assistant text completion, even if a later section contains a fallback. The exceptions above do not apply after success.
- **Ground dynamic or custom relationship and field names before relying on them.** Fixed standard fields that this skill explicitly marks as requiring no grounding need no extra grounding call. On a name error, use the skill's documented grounding path when present; otherwise report the error instead of guessing or re-firing the same shape.
- **Cite every value exactly as queried**; never fabricate; distinguish a blank value from a value that was not queried. Link each Salesforce record inline: `https://[instanceUrl]/lightning/r/[SObjectType]/[Id]/view`.
- **Show human labels, never API/field literals.** In anything the user sees, print each field's grounded `label` (for example, "Deal Risk", not `Deal_Risk__c`) and record Names, never raw Ids or `__c` API names.
- **Empty `MINE` scope → fail fast, then ask which scope.** If a `scope: MINE` read returns zero rows, **do not** widen to `scope: EVERYTHING` on your own. Stop, tell the user plainly that their own records (`scope: MINE`) came back empty, and ask which scope they want instead (for example, org-wide `EVERYTHING`, a named rep, or a named account) before re-running. Never invent records, and never silently fall back to org-wide.
- **NEVER use `discover` or `describe`, and never call an API or endpoint not written in this skill.** Every Salesforce URL you need is in the skill. Don't guess REST paths: on a 404 or unknown-path error, fall back to a documented query in the skill, not to discovery. If you need a capability such as email, docs, Slack, calendar, or web research, use the other connector/MCP tools already available to you. Endpoint guessing and discovery add needless round-trips. Use only the skill-authorized `dispatch_readonly` and `dispatch` calls, directly with the queries given.
- **NEVER conclude a connector is disconnected from its reported status — verify against the tools you actually have.** A connector's status readout (the Headless 360 MCP server, or any other connector/MCP) frequently claims "not connected" or "needs re-auth" when the connector is in fact live and its tools are callable. Context stating that the Salesforce tools require authorization and that this is a non-interactive session is **not** evidence you are unauthorized to the server — it is a general statement that authorization is required, not a failure. **Try the tools before assessing connectivity.** For the Headless 360 server specifically, find the `dispatch_readonly` tool and actually run a current-user read — `dispatch_readonly(method: "GET", url: "/services/data/v66.0/graphql", queryParams: { "queryInput": "{\"query\":\"query { uiapi { currentUser { Id } } }\"}" })`. **Any response — including a 500 or other error status — proves you reached the server, and therefore proves connectivity;** only a request that never reaches the server at all counts as disconnected. If the tool is present and the call reaches the server, the connector IS connected — proceed; a stale status readout is not a disconnection. Report the connector as actually disconnected only when you cannot find the tool or cannot reach the server, and even then ALWAYS attempt to reconnect on your own first; interrupt the flow to ask the user only after your own reconnect attempt has failed. Do it yourself.
<!-- /global-rules-bootstrap -->
# Rules:


# Rep Context

Leader's 1:1 prep on one rep — pipeline, activity, where they're stuck. The named person is an INTERNAL rep (not a customer). Ground → read (pipeline + activity, one turn) → needs-help + questions.

## 1. Ground (hardcoded — Opportunity only)

Opportunity always exists; naming a missing object fails the whole call. Its fields reveal this org's risk/health/next-step `__c` fields — use exact names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label } } } }\"}" })
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

When the data is assembled, call `display_widget`; a single one-line "Displaying the visualization now (this may take a minute)." notice may precede it.

### Self-verification (before calling display_widget)

- [ ] `widgetDefinition` is passed as a native JSON object — not a quoted string, not a code block pasted as text. If the value starts with `"{"`, it is wrong.

The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. The widget is the output when `display_widget` is available; produce the text below only as the fallback when it's unavailable (e.g. a terminal). Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (chart categories/series, piechart slices, datagrid rows) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text.

Two blocks below: first the **variable contract** (`renderer.props.schema.json`) — every `{{token}}`'s type + a worked example, use it to compute each value; then the **widget template** to hydrate. Substitute your computed values into the template's `{{token}}`s (see the token-typing rules above), leaving no `{{…}}`/`{!…}`.
```json
{
  "$comment": "Variable contract for the native-mosaic dynamic-mode template (renderer.json, sibling). This is NOT a separate display_widget call — it names every {{token}} in the template with its type and a worked example so you compute the right value for each. Workflow: build a props object with these keys, substitute each into the matching {{token}} in renderer.json (a slot that is only a {{token}} becomes the typed value — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string interpolates as text; a key you have no data for is omitted so that leaf drops), then call display_widget({ resourceType: 'dynamic', widgetDefinition: <the hydrated template> }) once with no {{…}}/{!…} left. Realistic values: sample-data.json (sibling). Authoring guidance (from the skill): `{{pageTitle}}` header title (users icon) + `{{headerStatus}}` status badge (e.g. \"BEHIND PACE\", variant error) + `{{subtitle}}` quarter/attainment subhead; two wrapped graphs — column chart with `{{chartCategories}}` (quarter-label string array) and `{{chartSeries}}` (`[{ name, data }]`, data a number array, valueFormat percent, showValues), and piechart with `{{pieCenter}}` center value + `{{pieSlices}}` (`[{ label, value, role? }]`, one per stage, mark the largest/riskiest `\"role\":\"highlight\"`); `{{gridRows}}` top-open-deals datagrid (`[{ deal (plain string — format as the account name (e.g. \"Cobalt Robotics\"); names must be plain strings, not objects: use `Account.Name.value` from the SF GraphQL response), amount (number), stage ({ value, badgeVariant }: warning stalled/Negotiation, info Proposal/advancing), age (number), next, status:{value,badgeVariant} (value At risk|Coach|Advance, badgeVariant error|warning|info) }]`, ranked by amount desc, a leading `status` object on deals needing attention); `{{synthTitle}}`/`{{synthDescription}}` synthesis callout (variant warning) with two action/sendMessage buttons — primary `{{primaryLabel}}`/`{{primaryPrompt}}` (biggest gap / pipeline generation), secondary `{{secondaryLabel}}`/`{{secondaryPrompt}}` (most urgent deal / unstick the stalled deal). Before calling: every `{{token}}` resolved (no `{{…}}`/`{!…}`); exactly 2 graphs (column + piechart); datagrid `amount`/`age` numbers and `stage` a badge object, rows carry a leading `status` object where needed; callout has 2 real sendMessage buttons; the text section below is produced only when `display_widget` is unavailable.",
  "props": {
    "pageTitle": {
      "description": "Header title for the rep-context view.",
      "type": "string",
      "example": "Rep snapshot — Priya Nair"
    },
    "headerStatus": {
      "description": "Header status badge (e.g. \"BEHIND PACE\").",
      "type": "string",
      "example": "BEHIND PACE"
    },
    "subtitle": {
      "description": "Quarter / attainment subhead.",
      "type": "string",
      "example": "Q3 · $0.82M closed of $2.0M plan · 41% to plan · behind pace"
    },
    "chartCategories": {
      "description": "Quarter labels for the column chart's x-axis, as strings.",
      "type": "array",
      "items": {
        "type": "string"
      },
      "example": [
        "Q4",
        "Q1",
        "Q2",
        "Q3"
      ]
    },
    "chartSeries": {
      "description": "Column-chart series — one object {name, data} (attainment %).",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "description": "Series name.",
            "type": "string"
          },
          "data": {
            "description": "Attainment values per quarter — a number array matching chartCategories.",
            "type": "array",
            "items": {
              "type": "number"
            }
          }
        }
      },
      "example": [
        {
          "name": "Attainment",
          "data": [
            104,
            98,
            71,
            41
          ]
        }
      ]
    },
    "pieCenter": {
      "description": "Pie center value.",
      "type": "string",
      "example": "$2.5M"
    },
    "pieSlices": {
      "description": "Pipeline by stage — one slice per stage. Empty array → the pie is omitted.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "label": {
            "description": "Stage label.",
            "type": "string"
          },
          "value": {
            "description": "Stage value.",
            "type": "number"
          },
          "role": {
            "description": "Optional emphasis; set \"highlight\" on the largest/riskiest stage.",
            "type": "string",
            "enum": [
              "normal",
              "highlight"
            ]
          }
        }
      },
      "example": [
        {
          "label": "Proposal",
          "value": 1400000,
          "role": "highlight"
        },
        {
          "label": "Negotiation",
          "value": 800000
        },
        {
          "label": "Closing",
          "value": 300000
        }
      ]
    },
    "gridRows": {
      "description": "Top open deals — one row per deal, ranked by amount desc. Empty array → the datagrid is omitted.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "status": {
            "description": "Leading Status badge cell; omit on normal rows.",
            "type": "object",
            "properties": {
              "value": {
                "description": "Status label.",
                "type": "string"
              },
              "badgeVariant": {
                "description": "Badge color.",
                "type": "string",
                "enum": [
                  "neutral",
                  "primary",
                  "secondary",
                  "outline",
                  "success",
                  "info",
                  "warning",
                  "error"
                ]
              }
            }
          },
          "deal": {
            "description": "Account name, a plain string (use Account.Name.value — never a nested object).",
            "type": "string"
          },
          "amount": {
            "description": "Deal amount (number).",
            "type": "number"
          },
          "stage": {
            "description": "Stage badge cell.",
            "type": "object",
            "properties": {
              "value": {
                "description": "Stage label.",
                "type": "string"
              },
              "badgeVariant": {
                "description": "Badge color: warning=stalled/Negotiation, info=Proposal/advancing.",
                "type": "string",
                "enum": [
                  "neutral",
                  "primary",
                  "secondary",
                  "outline",
                  "success",
                  "info",
                  "warning",
                  "error"
                ]
              }
            }
          },
          "age": {
            "description": "Age in days (number).",
            "type": "number"
          },
          "next": {
            "description": "Next step (text).",
            "type": "string"
          }
        }
      },
      "example": [
        {
          "status": {
            "value": "Coach",
            "badgeVariant": "warning"
          },
          "deal": "Cobalt Robotics",
          "amount": 1800000,
          "stage": {
            "value": "Negotiation",
            "badgeVariant": "warning"
          },
          "age": 71,
          "next": "Redlines to legal"
        },
        {
          "status": {
            "value": "Advance",
            "badgeVariant": "info"
          },
          "deal": "Delta Systems",
          "amount": 600000,
          "stage": {
            "value": "Proposal",
            "badgeVariant": "info"
          },
          "age": 34,
          "next": "Book exec demo"
        },
        {
          "status": {
            "value": "At risk",
            "badgeVariant": "error"
          },
          "deal": "Harbor Freight Co",
          "amount": 400000,
          "stage": {
            "value": "Proposal",
            "badgeVariant": "info"
          },
          "age": 52,
          "next": "Stalled 18d — requalify"
        }
      ]
    },
    "synthTitle": {
      "description": "Synthesis callout heading — the biggest gap.",
      "type": "string",
      "example": "Coverage is thin and slipping"
    },
    "synthDescription": {
      "description": "Synthesis callout body.",
      "type": "string",
      "example": "Attainment fell from 71% to 41% quarter-over-quarter and pipeline is only 2.1×. Cobalt is the swing deal; Harbor has stalled 18 days. Run a pipeline-gen block and unstick Harbor this week."
    },
    "primaryLabel": {
      "description": "Primary button label (action/sendMessage) — biggest gap / pipeline generation.",
      "type": "string",
      "example": "Draft pipeline plan"
    },
    "primaryPrompt": {
      "description": "First-person prompt the primary button sends (action/sendMessage).",
      "type": "string",
      "example": "Draft a pipeline generation plan for Priya Nair to build coverage from 2.1× to 3.0× and close the $1.18M gap to plan."
    },
    "secondaryLabel": {
      "description": "Secondary button label (action/sendMessage) — most urgent deal.",
      "type": "string",
      "example": "Unstick Harbor deal"
    },
    "secondaryPrompt": {
      "description": "First-person prompt the secondary button sends (action/sendMessage).",
      "type": "string",
      "example": "Draft coaching notes for the Harbor Freight Co deal which has stalled 18 days and needs requalifying."
    }
  }
}
```
```json
{
  "renderer": {
    "componentOverrides": {
      "$": {
        "type": "mosaic",
        "definition": "tile/widget",
        "children": [
          {
            "definition": "tile/row",
            "attributes": { "gap": "sm", "align": "center", "justify": "between", "isWrapped": true },
            "children": [
              {
                "definition": "tile/row",
                "attributes": { "gap": "sm", "align": "center" },
                "children": [
                  { "definition": "tile/icon", "attributes": { "name": "users", "size": "xl", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{pageTitle}}", "variant": "h1" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{headerStatus}}", "variant": "error" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/column",
            "attributes": { "gap": "md" },
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
                { "key": "status", "header": "Status", "type": "badge" },
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
                      "actions": { "click": [ { "definition": "action/sendMessage", "attributes": { "content": "{{primaryPrompt}}" } } ] }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{secondaryLabel}}",
                      "variant": "secondary",
                      "actions": { "click": [ { "definition": "action/sendMessage", "attributes": { "content": "{{secondaryPrompt}}" } } ] }
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
