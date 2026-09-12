---
name: renewal-radar
description: "Build a renewal risk brief from Salesforce opportunities, email, documents and Slack, covering timing, activity, uplift and next moves. Use to scan upcoming renewals or prepare one renewal motion; for overall account health or QBR prep, use customer-health."
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

- **Empty owned book → fail fast, then ask which scope.** If the my-book read (the `OwnerId` filter) returns zero renewals, **do not** drop the owner filter and go org-wide on your own. Stop, tell the user plainly that their own book came back empty, and ask which scope they want instead (org-wide, a named rep, or a named account) before re-running, then wait. Never invent records, and never silently widen to org-wide.

# Renewal Radar

The renewal you start 90 days out is a process; the one you notice 2 weeks out is a discount. Keep the renewal calendar visible, flag the risky ones early, prep each renewal motion.

**Inputs:** my book (default), named rep, named account, or the team. Window: next N days (default 120), or specific quarter (Q1/Q2/Q3/Q4 FY26 → compute start/end dates).

## 1. Resolve scope (if named rep)

- **"my renewals"** (default) → resolve `currentUser.Id` once through this exact query, then use that ID for the OwnerId filter:
  ```
  dispatch_readonly(method: "GET", url: "/services/data/v66.0/graphql",
    queryParams: { "queryInput": "{\"query\":\"query { uiapi { currentUser { Id } } }\"}" })
  ```
- **"[Rep]'s renewals"** → resolve one User. Shared/demo orgs collide (one name → base user + regional variants like `(AM)`/`(BK)`). Pull enough to disambiguate:
  ```
  dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
    queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { User(where: { Name: { like: \\\"%REP%\\\" } }, first: 10) { edges { node { Id Name { value } Email { value } IsActive { value } } } } } } }\"}" })
  ```
  **One match** → take its Id for OwnerId filter in step 3. **Several** → list them (Name · Email · active? · Id) and ask user to pick. **Zero** → ask user to clarify.
- **Named account** → resolve Account by name, use AccountId filter in step 3
- **Team** → no owner filter

## 2. Ground (hardcoded — Opportunity only)

Ground **only Opportunity** — it always exists. Its fields reveal this org's renewal-specific custom signals.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label } } } }\"}" })
```

From the result, select only relevant `__c` fields (ARR, renewal type, usage signals, auto-renew flags) and take their `{ value }`.

## 3. Pull renewal calendar (GraphQL — fill from step 2)

Insert `<OPP_CUSTOM>` = confirmed scalar `__c { value }` fields from Step 2. **Nest Account and Owner in this one query.**

**Date filter:** user can specify window as "next N days" (default 120) or "Q1 FY26" / "Q2 FY26" etc.
- **"next N days"** → use `CloseDate: { gte: { literal: TODAY }, lte: { range: { next_n_days: 120 } } }`
- **"Q1 FY26"** → compute quarter ISO dates, use `CloseDate: { gte: { value: "2026-02-01" }, lte: { value: "2026-04-30" } }`

**Primary query (`like`/`or` catches both Type picklist values and Name patterns):**

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { OwnerId: { eq: \\\"<currentUserId>\\\" }, IsClosed: { eq: false }, CloseDate: { gte: { literal: TODAY }, lte: { range: { next_n_days: 120 } } }, or: [{ Type: { like: \\\"%renew%\\\" } }, { Name: { like: \\\"%renew%\\\" } }] }, orderBy: { CloseDate: { order: ASC } }, first: 50) { edges { node { Id Name { value } Type { value displayValue } Amount { value displayValue } CloseDate { value } StageName { value displayValue } NextStep { value } LastActivityDate { value } Account { Name { value } Industry { value displayValue } Type { value displayValue } } Owner { Name { value } } <OPP_CUSTOM> } } } } } }\"}" })
```

Replace the `CloseDate` clause with the computed date filter. Insert `<OPP_CUSTOM>` as `ARR__c { value } AutoRenew__c { value }` if those fields exist, or omit if none.

**Scope filters:**
- **My book** (default): keep `OwnerId: { eq: "<currentUserId>" }` using the `currentUser.Id` resolved in step 1
- **Named rep**: replace it with `OwnerId: { eq: "<resolvedUserId>" }`
- **Named account**: replace it with `AccountId: { eq: "<accountId>" }`
- **Team**: omit the owner clause

## 3b. Evidence (run IN PARALLEL with step 3 — same turn)

**Issue step 3 and all of step 3b as tool calls in a single turn.** They're independent (searches key on account names, not the SF result):
- **email**: threads mentioning each account name in last 90d → escalations, sentiment, exec engagement
- **docs**: docs mentioning account names → prioritize files with "escalation", "churn", "expansion" in title, most recent first. Read top 1–2 per account and extract: risk signals, expansion discussions.
- **slack**: account names in last 30d → internal context (support escalations, CSM warnings, expansion threads)

Use whatever email/doc/Slack search tools are available. If none present, skip silently (SF-only is fine). Cite source + date for anything you use.

**Perf guardrail:** Do NOT fire additional SF dispatches for `Task` or `Contract` — the step 3 read has the data.

## 4. Score each renewal

| Signal | Effect |
|---|---|
| No activity on the account in 30+ days (LastActivityDate < 30 days ago) | risk ↑ |
| Open support escalation mentioned in email/Slack | risk ↑ |
| Usage/adoption signals trending down (if `__c` field present) | risk ↑ |
| Active expansion conversation in email/Slack | risk ↓ / uplift ↑ |
| Multi-year or auto-renew term (if `__c` flag present) | risk ↓ |
| NextStep blank or stale | risk ↑ |
| Champion or economic buyer has changed/left (email/Slack evidence from 3b) | risk ↑ |

Verdict per renewal: 🟢 on track / 🟡 needs attention / 🔴 at risk - with the evidence.

## 5. Widget (default output when `display_widget` is present: Cowork/desktop/web)

Default output on Cowork/desktop/web; in a terminal `display_widget` is unavailable, so section 6 is the whole output there.

When the data is assembled, call `display_widget`; a single one-line "Displaying the visualization now (this may take a minute)." notice may precede it.

### Self-verification (before calling display_widget)

- [ ] `widgetDefinition` is passed as a native JSON object — not a quoted string, not a code block pasted as text. If the value starts with `"{"`, it is wrong.

The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left — this echo path does no expression compilation), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (meter `value`/`bands`, piechart `slices`, datagrid `rows`) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text.

Blocks, all from data already fetched: header icon + `{{pageTitle}}` title + `{{headerStatus}}` warning badge, then `{{subtitle}}` caption; a meter ("At-risk ARR share": `{{riskValue}}` vs `{{riskTarget}}` over a fixed 0–100 range, with `{{riskValueLabel}}`/`{{riskTargetLabel}}`/`{{riskStatus}}`/`{{riskBands}}`) and a donut piechart ("Renewal ARR by risk verdict": `{{pieCenter}}` center, `{{pieSlices}}`) in a wrapped row; a renewals datagrid (`{{gridRows}}`, count `{{totalRenewals}}`) with columns Account, ARR (currency), Renews (date), Usage trend (sparkline), Verdict (badge), Play; one error callout (`{{synthTitle}}`/`{{synthDescription}}`) with a primary sendMessage button (`{{primaryLabel}}`/`{{primaryPrompt}}`) and a secondary openLink button ("View in Salesforce", `{{criticalRenewalsUrl}}`).

Binding:
- Numbers stay numbers (`{{riskValue}}`, `{{riskTarget}}`, each row's `arr`, `usage` arrays); arrays stay arrays (`{{riskBands}}`, `{{pieSlices}}`, `{{gridRows}}`).
- `{{riskBands}}`: array of `{ from, to, variant, label }` covering 0→100 in order — success (0–15 Healthy), warning (15–30 Elevated), error (30–100 High).
- `{{pieSlices}}`: array of `{ label, value, role? }`, one per verdict; mark the at-risk segment `"role": "highlight"`. `{{pieCenter}}` is total renewal ARR as a formatted currency string (e.g. "$4.7M"), not a raw number.
- `{{gridRows}}`: array of `{ account (plain string — format as the account name (e.g. "Cobalt Robotics"); names must be plain strings, not objects: use `Account.Name.value` from the SF GraphQL response), arr (number), close (ISO YYYY-MM-DD), usage (number[]), verdict ({ value, badgeVariant }), action, status:{value,badgeVariant} (value Critical|At risk, badgeVariant error|warning) }`. Verdict badge: error=Critical, warning=At risk, success=On track. Risky rows carry a leading `status` object; healthy rows omit both. Rank Critical first, then by close date. `{{totalRenewals}}` = row count.
- Callout: `{{primaryPrompt}}` is first-person (e.g. "Draft an executive save plan for…"); `{{criticalRenewalsUrl}}` = `https://<myDomain>/lightning/o/Opportunity/list?filterName=Critical_Renewals`, or the account record URL for a single renewal.

Verify before calling: no `{{…}}`/`{!…}` remain; exactly 2 graphs (meter + piechart); datagrid `arr`/`usage` are numbers/arrays, `close` is ISO, risky rows carry a leading `status` object and healthy rows omit both; callout has 2 real buttons (sendMessage, openLink); section 6 text is produced only when `display_widget` is unavailable.


Two blocks below: first the **variable contract** (`renderer.props.schema.json`) — every `{{token}}`'s type + a worked example, use it to compute each value; then the **widget template** to hydrate. Substitute your computed values into the template's `{{token}}`s (see the token-typing rules above), leaving no `{{…}}`/`{!…}`.
```json
{
  "$comment": "Variable contract for the native-mosaic dynamic-mode template (renderer.json, sibling). This is NOT a separate display_widget call — it names every {{token}} in the template with its type and a worked example so you compute the right value for each. Workflow: build a props object with these keys, substitute each into the matching {{token}} in renderer.json (a slot that is only a {{token}} becomes the typed value — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string interpolates as text; a key you have no data for is omitted so that leaf drops), then call display_widget({ resourceType: 'dynamic', widgetDefinition: <the hydrated template> }) once with no {{…}}/{!…} left. Realistic values: sample-data.json (sibling). Authoring guidance (from the skill): `{{pageTitle}}` (e.g. \"Renewal radar — next 90 days\"), `{{headerStatus}}` (e.g. \"$1.4M AT RISK\"), `{{subtitle}}` (window summary); meter `{{riskValue}}`/`{{riskTarget}}`/`{{riskValueLabel}}`/`{{riskTargetLabel}}`/`{{riskStatus}}`/`{{riskBands}}`; piechart `{{pieCenter}}` (formatted currency string e.g. \"$4.7M\")/`{{pieSlices}}`; datagrid `{{gridRows}}`/`{{totalRenewals}}`; callout `{{synthTitle}}`/`{{synthDescription}}`/`{{primaryLabel}}`/`{{primaryPrompt}}`/`{{criticalRenewalsUrl}}`.",
  "props": {
    "pageTitle": {
      "description": "Page title (e.g. \"Renewal radar — next 90 days\").",
      "type": "string",
      "example": "Renewal radar — next 90 days"
    },
    "headerStatus": {
      "description": "Header at-risk badge (e.g. \"$1.4M AT RISK\").",
      "type": "string",
      "example": "$1.4M AT RISK"
    },
    "subtitle": {
      "description": "Window summary.",
      "type": "string",
      "example": "$4.7M ARR across 11 renewals · $1.4M at risk · 3 need attention now"
    },
    "riskValue": {
      "description": "At-risk ARR — the meter's current value.",
      "type": "number",
      "example": 30
    },
    "riskTarget": {
      "description": "Target/threshold marker on the meter.",
      "type": "number",
      "example": 15
    },
    "riskValueLabel": {
      "description": "Display string for the at-risk value.",
      "type": "string",
      "example": "$1.4M of $4.7M ARR at risk (30%)"
    },
    "riskTargetLabel": {
      "description": "Display string for the target.",
      "type": "string",
      "example": "15% ceiling"
    },
    "riskStatus": {
      "description": "Short risk read shown on the meter.",
      "type": "string",
      "example": "over ceiling"
    },
    "riskBands": {
      "description": "Color bands for the risk meter, in order covering 0→max.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "from": {
            "description": "Band start value.",
            "type": "number"
          },
          "to": {
            "description": "Band end value.",
            "type": "number"
          },
          "variant": {
            "description": "Band color.",
            "type": "string",
            "enum": [
              "error",
              "warning",
              "success"
            ]
          },
          "label": {
            "description": "Short band label.",
            "type": "string"
          }
        }
      },
      "example": [
        {
          "from": 0,
          "to": 15,
          "variant": "success",
          "label": "Healthy"
        },
        {
          "from": 15,
          "to": 30,
          "variant": "warning",
          "label": "Elevated"
        },
        {
          "from": 30,
          "to": 100,
          "variant": "error",
          "label": "High"
        }
      ]
    },
    "pieCenter": {
      "description": "Pie center value — total renewal ARR, a formatted currency string (e.g. \"$4.7M\").",
      "type": "string",
      "example": "$4.7M"
    },
    "pieSlices": {
      "description": "Renewal ARR by segment — one slice per segment. Empty array → the pie is omitted.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "label": {
            "description": "Slice label.",
            "type": "string"
          },
          "value": {
            "description": "Slice value (ARR).",
            "type": "number"
          },
          "role": {
            "description": "Optional emphasis; set \"highlight\" on the key slice.",
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
          "label": "On track",
          "value": 3300000
        },
        {
          "label": "At risk",
          "value": 900000,
          "role": "highlight"
        },
        {
          "label": "Critical",
          "value": 500000
        }
      ]
    },
    "gridRows": {
      "description": "Upcoming renewals — one row per account. Empty array → the datagrid is omitted.",
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
          "account": {
            "description": "Account name.",
            "type": "string"
          },
          "arr": {
            "description": "Renewal ARR, in dollars (number).",
            "type": "number"
          },
          "close": {
            "description": "Renewal/close date, ISO YYYY-MM-DD.",
            "type": "string"
          },
          "usage": {
            "description": "Recent usage trend — a number array (sparkline).",
            "type": "array",
            "items": {
              "type": "number"
            }
          },
          "verdict": {
            "description": "Renewal-verdict badge cell.",
            "type": "object",
            "properties": {
              "value": {
                "description": "Verdict label.",
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
          "action": {
            "description": "Recommended action (text).",
            "type": "string"
          }
        }
      },
      "example": [
        {
          "status": {
            "value": "Critical",
            "badgeVariant": "error"
          },
          "account": "Cobalt Robotics",
          "arr": 500000,
          "close": "2026-08-12",
          "usage": [
            82,
            78,
            71,
            60,
            44,
            38
          ],
          "verdict": {
            "value": "Critical",
            "badgeVariant": "error"
          },
          "action": "⚠ exec save plan — usage down 54%"
        },
        {
          "status": {
            "value": "At risk",
            "badgeVariant": "warning"
          },
          "account": "Alto Financial",
          "arr": 400000,
          "close": "2026-08-20",
          "usage": [
            50,
            52,
            49,
            55,
            58,
            61
          ],
          "verdict": {
            "value": "At risk",
            "badgeVariant": "warning"
          },
          "action": "Multi-year + expansion pitch"
        },
        {
          "account": "Pier 9 Retail",
          "arr": 700000,
          "close": "2026-08-28",
          "usage": [
            60,
            64,
            66,
            70,
            72,
            75
          ],
          "verdict": {
            "value": "On track",
            "badgeVariant": "success"
          },
          "action": "Uplift candidate: +12% list"
        },
        {
          "account": "Meridian Health",
          "arr": 1200000,
          "close": "2026-09-18",
          "usage": [
            88,
            90,
            91,
            93,
            95,
            96
          ],
          "verdict": {
            "value": "On track",
            "badgeVariant": "success"
          },
          "action": "Anchor reference; propose 3-yr"
        }
      ]
    },
    "totalRenewals": {
      "description": "Total renewal count in the window (number).",
      "type": "number",
      "example": 11
    },
    "synthTitle": {
      "description": "Synthesis callout heading — the biggest renewal risk.",
      "type": "string",
      "example": "Cobalt Robotics is the critical renewal this month"
    },
    "synthDescription": {
      "description": "Synthesis callout body — the risk and the move.",
      "type": "string",
      "example": "Cobalt ($500K, renews Aug 12) has seen usage drop 54% in 6 weeks and needs an exec save plan now. Alto Financial ($400K, Aug 20) is at risk and could be secured with a multi-year + expansion pitch. These two renewals carry $900K of the $1.4M at-risk ARR."
    },
    "primaryLabel": {
      "description": "Primary button label (action/sendMessage).",
      "type": "string",
      "example": "Draft exec save plan"
    },
    "primaryPrompt": {
      "description": "First-person prompt the primary button sends (action/sendMessage).",
      "type": "string",
      "example": "Draft an executive save plan for Cobalt Robotics to address the 54% usage decline before their August 12 renewal."
    },
    "criticalRenewalsUrl": {
      "description": "Lightning URL for the \"View in Salesforce\" button (critical renewals).",
      "type": "string",
      "example": "https://org.lightning.force.com/lightning/o/Opportunity/list?filterName=Critical_Renewals"
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
            "attributes": {
              "gap": "sm",
              "align": "center",
              "justify": "between",
              "isWrapped": true
            },
            "children": [
              {
                "definition": "tile/row",
                "attributes": {
                  "gap": "sm",
                  "align": "center"
                },
                "children": [
                  {
                    "definition": "tile/icon",
                    "attributes": {
                      "name": "refresh",
                      "size": "xl",
                      "alt": ""
                    }
                  },
                  {
                    "definition": "tile/text",
                    "attributes": {
                      "text": "{{pageTitle}}",
                      "variant": "h1"
                    }
                  }
                ]
              },
              {
                "definition": "tile/badge",
                "attributes": {
                  "label": "{{headerStatus}}",
                  "variant": "warning"
                }
              }
            ]
          },
          {
            "definition": "tile/text",
            "attributes": {
              "text": "{{subtitle}}",
              "variant": "caption",
              "color": "muted"
            }
          },
          {
            "definition": "tile/separator"
          },
          {
            "definition": "tile/row",
            "attributes": {
              "gap": "lg",
              "align": "stretch",
              "isWrapped": true
            },
            "children": [
              {
                "definition": "tile/column",
                "attributes": {
                  "width": "stretch"
                },
                "children": [
                  {
                    "definition": "tile/meter",
                    "attributes": {
                      "label": "At-risk ARR share",
                      "value": "{{riskValue}}",
                      "min": 0,
                      "max": 100,
                      "target": "{{riskTarget}}",
                      "valueFormat": "percent",
                      "valueLabel": "{{riskValueLabel}}",
                      "targetLabel": "{{riskTargetLabel}}",
                      "status": "{{riskStatus}}",
                      "bands": "{{riskBands}}",
                      "size": "lg"
                    }
                  }
                ]
              },
              {
                "definition": "tile/column",
                "attributes": {
                  "width": "stretch"
                },
                "children": [
                  {
                    "definition": "tile/piechart",
                    "attributes": {
                      "caption": "Renewal ARR by risk verdict",
                      "variant": "donut",
                      "valueFormat": "currency",
                      "centerLabel": "ARR",
                      "centerValue": "{{pieCenter}}",
                      "slices": "{{pieSlices}}"
                    }
                  }
                ]
              }
            ]
          },
          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Renewals in the next 90 days, soonest and riskiest first",
              "appearance": "striped",
              "defaultSort": {
                "key": "close",
                "direction": "asc"
              },
              "columns": [
                {
                  "key": "status",
                  "header": "Status",
                  "type": "badge"
                },
                {
                  "key": "account",
                  "header": "Account",
                  "type": "text"
                },
                {
                  "key": "arr",
                  "header": "ARR",
                  "type": "currency",
                  "align": "right",
                  "sortable": true
                },
                {
                  "key": "close",
                  "header": "Renews",
                  "type": "date",
                  "sortable": true
                },
                {
                  "key": "usage",
                  "header": "Usage trend",
                  "type": "sparkline"
                },
                {
                  "key": "verdict",
                  "header": "Verdict",
                  "type": "badge"
                },
                {
                  "key": "action",
                  "header": "Play",
                  "type": "text"
                }
              ],
              "rows": "{{gridRows}}",
              "totalRows": "{{totalRenewals}}"
            }
          },
          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "error",
              "title": "{{synthTitle}}",
              "description": "{{synthDescription}}"
            },
            "children": [
              {
                "definition": "tile/row",
                "attributes": {
                  "gap": "sm",
                  "align": "center",
                  "isWrapped": true
                },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{primaryLabel}}",
                      "variant": "primary",
                      "actions": {
                        "click": [
                          {
                            "definition": "action/sendMessage",
                            "attributes": {
                              "content": "{{primaryPrompt}}"
                            }
                          }
                        ]
                      }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "View in Salesforce",
                      "iconName": "open-in-new",
                      "variant": "secondary",
                      "actions": {
                        "click": [
                          {
                            "definition": "action/openLink",
                            "attributes": {
                              "url": "{{criticalRenewalsUrl}}"
                            }
                          }
                        ]
                      }
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

**Formatting rules:**
- **Link every opportunity:** `[Account] [↗](https://[instanceUrl]/lightning/r/Opportunity/[Id]/view)` inline in table + full URLs in Hygiene section
- **Extract instance URL:** from query result's `url` field or construct from org subdomain (e.g. `org62.my.salesforce.com`)
- **Specify date window:** e.g. "Aug 4 – Dec 1, 2026" (not just "next 120 days")
- **Status column:** extract from NextStep/Description/custom fields if present (e.g. "Ali resell", "Out of ext."), else fall back to StageName
- **Timeline specifics in At-risk section:** days until close, months since last activity, field API names for data discrepancies

```
# Renewal Radar - [scope] - [date range] ([instanceUrl])

| Account | Opp | Renewal date | ARR/Amount | Status | Risk driver | Next step |
|---|---|---|---|---|---|---|
| [Account] | [↗](https://[instanceUrl]/lightning/r/Opportunity/[Id]/view) | [date] | $[X] | [extracted status] | [flag] | [action] |

## At risk (act this week)
- **[Account] [↗](url)** - [date] ([N days away]) - [specific risk with timeline context: "no activity in 2.5 months", "6 days away"] → [the play]

## Uplift candidates
- **[Account] [↗](url)** - [the expansion signal and the proposed uplift motion]

## Hygiene

For each renewal with missing/incorrect data, propose the EXACT field change needed with **full Lightning URL**:

**Missing NextStep:**
```
🔧 Update [Opp Name]

Current NextStep: [blank]
→ Should be: [specific action based on stage and date proximity]

Apply this change via update-opportunity?
```

**Incorrect CloseDate:**
```
🔧 Update [Opp Name]

Current Close Date: [wrong date]
→ Should be: [corrected date based on contract/renewal timing]

Apply this change via update-opportunity?
```

**Missing renewal opportunity** (an account whose term is ending with no renewal opp on the books):
```
📋 Create Renewal Opportunity

Account: [Account]  ·  Name: "[Account] – [Year] Renewal"
Type: Renewal  ·  Amount: [prior ARR]  ·  Close Date: [term end]  ·  Stage: [initial renewal stage]

Create this record?
```

Present each proposed change with confirmation before attempting any write. On a read-only connector, output these as a checklist for manual entry.
```

For a single named account, expand into a renewal prep brief: history, current sentiment, pricing/uplift recommendation, paperwork timeline worked back from the end date.
