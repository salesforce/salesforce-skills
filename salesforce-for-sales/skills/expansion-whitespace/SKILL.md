---
name: expansion-whitespace
description: "Identify ranked expansion plays for one customer from Salesforce contacts, owned products and opportunities plus recent email, documents and Slack. Use to find evidence-backed whitespace, upsell paths or adjacent teams and products ready for outreach."
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

- **Expansion Whitespace text contract.** Aside from the exact required pre-widget notice, the text fallback is the only permitted prose, and it must start with `# Expansion Whitespace`.

# Expansion Whitespace

Resolve account → ground → read → map whitespace → output. Product catalog is external knowledge — ask once.

## 1. Resolve the account

Shared/demo orgs collide on name. If user gave Salesforce Id, skip to Step 2. Otherwise:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Name: { like: \\\"%ACCOUNT%\\\" } }, first: 10) { edges { node { Id Name { value } Website { value } Type { value } Industry { value } Owner { Name { value } } } } } } } }\"}" })
```

**One match** → take its Id, continue to Step 2.

**Several** → STOP. Before Step 2, determine which account:
- **If user provided $amount or seat count:** Search Opportunities across ALL candidate account Ids to find which has matching renewal/deal:
  ```
  dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
    queryParams: { "q": "SELECT Id, AccountId, Account.Name, Name, Amount, CloseDate, StageName FROM Opportunity WHERE AccountId IN ('<ID1>','<ID2>',...) AND (Amount = <USER_AMOUNT> OR Name LIKE '%<USER_PRODUCT>%' OR CloseDate >= TODAY) ORDER BY CloseDate DESC LIMIT 50" })
  ```
  Match by Amount or product name. Take that AccountId, continue to Step 2.
  
- **Else:** List candidates (Name · Website/Industry · Owner · Id) and ask user to pick.

**None** → broaden name or ask for correct account. Don't guess.

## 2. Ground (hardcoded — Account + Contact)

Ground **Account + Contact** (both always exist). Lean projection discovers this org's custom fields without the full schema payload. **Fire as two separate calls** (combined ObjectInfo often overflows):

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Account\\\"]) { fields { ApiName label } } } }\"}" })

dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Contact\\\"]) { fields { ApiName label } } } }\"}" })
```

From the results: note scalar `__c` fields (Success_Segment, License_Utilization, Job_Function, Job_Level, etc.) — take their `{ value }` in the read queries. Without `dataType`/`relationshipName`, you can't perfectly distinguish scalar vs reference fields, but most customs are scalar; reference fields that slip through will show Ids (cryptic but not broken). Standard relationships (`Account`, `Owner`, `Contacts`, `ChildAccounts`) are hardcoded in queries below.

## 3. Read (fill from steps 1–2)

Insert `<ACCOUNT_CUSTOM>` = confirmed scalar `__c { value }` fields on Account; `<CONTACT_CUSTOM>` = confirmed scalar `__c { value }` fields on Contact (role, department, etc.).

**Fire TWO separate dispatches in ONE turn** (parallel, no dependency). Triple-nesting (Account > Opportunities > OpportunityLineItems) commonly fails; split avoids errors.

**Dispatch A — Account + Contacts + ChildAccounts:**
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Id: { eq: \\\"<ACCOUNT_ID>\\\" } }, first: 1) { edges { node { Id Name { value } Industry { value } NumberOfEmployees { value } AnnualRevenue { value displayValue } <ACCOUNT_CUSTOM> Contacts(first: 30) { edges { node { Name { value } Title { value } <CONTACT_CUSTOM> } } } ChildAccounts { edges { node { Name { value } Industry { value } Owner { Name { value } } } } } } } } } } }\"}" })
```

**Dispatch B — Won Opportunities + line items (the actual products/SKUs owned):**
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { Account: { Id: { eq: \\\"<ACCOUNT_ID>\\\" } }, IsWon: { eq: true } }, first: 30, orderBy: { CloseDate: { order: DESC } }) { edges { node { Name { value } Amount { value } CloseDate { value } StageName { value } Description { value } OpportunityLineItems(first: 50) { edges { node { Quantity { value } TotalPrice { value displayValue } Product2 { Name { value } } } } } } } } } } }\"}" })
```

The `OpportunityLineItems` child (span `Product2` for the SKU name, with `Quantity`/`TotalPrice`) is the real "Owned today" input for the Step 4 grid — one read, no extra round-trip (this is a single child level, not the triple-nesting that overflows). Fall back to `Opportunity.Name` only if the org doesn't use line items (empty `edges`).

For book-level sweep: replace Dispatch A `where: { Id: { eq: ... } }` with `scope: MINE` or team filter, limit 20.

## 3b. Evidence (run IN PARALLEL with step 3 — same turn)

**Issue step 3 and all of step 3b as tool calls in a single turn.** They're independent (searches key on account name, not the SF result):
- **email**: threads mentioning teams/use-cases/products not yet sold, **plus recent events/invites/webinars as timing hooks**
- **docs**: recent transcripts/notes → teams/departments mentioned, **job changes, new projects**
- **slack**: internal mentions → expansion plays discussed

Use whatever email/doc/Slack search tools are available. If none present, skip silently (SF-only is fine). Cite source + date for anything you use. **Prioritize evidence from last 90 days for recency/relevance.**

## 4. Map whitespace

**Product catalog (external):** ask user for the product/SKU list once — never invent. Build owned-vs-possible grid:

| Dimension | Owned today | Whitespace | Evidence |
|---|---|---|---|
| Products / SKUs | [SKUs owned, from Dispatch B's OpportunityLineItems (Product2 name · Quantity · TotalPrice); fall back to Opportunity.Name only if no line items] | [catalog items they haven't] | [need signal: mentioned in calls/emails? industry-typical?] |
| Teams / departments | [all contacts from Contacts child: name + title, not just technical subset] | [adjacent teams named in transcripts] | |
| Geography / subsidiaries | [entities under contract, plus reseller contacts if Account Type = reseller] | [child accounts with no spend] | |
| Volume / tier | [seats or usage from `__c`, penetration as exact % = seats/NumberOfEmployees] | [headroom vs employee count or benchmark, Success_Segment__c gap if present] | |

**Only call something whitespace if there is at least one piece of evidence** (stakeholder mentioned the team, transcript named the use case, org structure shows the entity). "They could theoretically buy everything" is not a finding.

## 4b. Cross-dimensional analysis (no extra dispatches — use data already fetched)

**Contact-to-product gap:** Cross-match contact titles/roles against owned products. Flag senior/exec/C-suite titles NOT reflected in product ownership (e.g., CIO with no BI tool seat, VP Sales with no CRM license = upsell hook).

**Child account routing:** For ChildAccounts with different Owner than parent, note AE-to-AE warm intro path (e.g., "Parent CIO → intro to Child Account Owner [Name]").

## 5. Rank plays

**Prioritize by sales motion complexity, not just $ size:**
1. **Renewal add-ons** (bundle into active renewal — lowest friction)
2. **Warm intro expansions** (existing contact opens door — medium friction)
3. **Cold new products** (no prior relationship — highest friction)

When evidence strength equal, prefer lower friction. Score on evidence strength, deal size potential, and access. **For reseller/partner accounts in "Owned today", name individual contacts, not just entity.** Top plays get a one-line motion: who to approach, with what message, anchored on which existing success.


## 6. Output — widget FIRST (the rendered UI is the default)

When the data is assembled, call `display_widget`; a single one-line "Displaying the visualization now (this may take a minute)." notice may precede it.

### Self-verification (before calling display_widget)

- [ ] `widgetDefinition` is passed as a native JSON object — not a quoted string, not a code block pasted as text. If the value starts with `"{"`, it is wrong.

The widget template is embedded below — resolve its tokens and call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once (see the `widgetDefinition` param for token-resolution rules).

Two blocks below: first the **variable contract** (`renderer.props.schema.json`) — every `{{token}}`'s type + a worked example, use it to compute each value; then the **widget template** to hydrate. Substitute your computed values into the template's `{{token}}`s (see the token-typing rules above), leaving no `{{…}}`/`{!…}`.
```json
{
  "$comment": "Variable contract for the native-mosaic dynamic-mode template (renderer.json, sibling). This is NOT a separate display_widget call — it names every {{token}} in the template with its type and a worked example so you compute the right value for each. Workflow: build a props object with these keys, substitute each into the matching {{token}} in renderer.json (a slot that is only a {{token}} becomes the typed value — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string interpolates as text; a key you have no data for is omitted so that leaf drops), then call display_widget({ resourceType: 'dynamic', widgetDefinition: <the hydrated template> }) once with no {{…}}/{!…} left. Realistic values: sample-data.json (sibling). Authoring guidance (from the skill): `title` (account name in heading) · `subtitle` (one-line ARR summary) · `heatmapCaption heatmapXLabels heatmapYLabels` (product adoption matrix: X=products from won Opps, Y=business units from ChildAccounts or Contact departments) · `heatmapDomain` (array `[0, maxValue]`) · `heatmapCells` (array, one per owned product×BU combo: `{x, y, value, valueLabel}` — omit whitespace combos so they render dashed/empty) · `piechartCaption piechartCenterLabel piechartCenterValue piechartSlices` (live ARR breakdown: array of `{label, value, role?}`, with `role:\"highlight\"` on largest slice) · `datagridCaption datagridRows` (expansion plays: array of `{play, unit, fit, arr, motion:{value,badgeVariant}, status?:{value,badgeVariant}}`) · `calloutTitle calloutDescription` (top play synthesis) · `primaryButtonLabel primaryButtonContent` (draft-plan button + sendMessage prompt) · `accountUrl` (Lightning URL `https://<myDomain>/lightning/r/Account/<Id>/view`).",
  "props": {
    "title": {
      "description": "Page title — the account name.",
      "type": "string",
      "example": "Expansion whitespace — Meridian Health"
    },
    "subtitle": {
      "description": "One-line ARR summary.",
      "type": "string",
      "example": "$1.2M live · $2.4M whitespace across 6 products and 4 business units"
    },
    "heatmapCaption": {
      "description": "Caption for the product-adoption heatmap (products × business units).",
      "type": "string",
      "example": "Product adoption by business unit — darker is more spend, empty is open whitespace"
    },
    "heatmapXLabels": {
      "description": "Heatmap X-axis labels — products (from won Opps). Keep each ≤12 chars, one or two short words — column headers sit in narrow equal-width columns and do NOT truncate, so long single tokens (e.g. 'Tableau/Analytics') overrun into the neighboring header. Abbreviate: 'Data Cloud', 'Analytics', 'Sales Cloud', 'MuleSoft'.",
      "type": "array",
      "items": {
        "type": "string",
        "maxLength": 12
      },
      "example": [
        "Platform",
        "Analytics",
        "Automation",
        "Security",
        "Data",
        "Support"
      ]
    },
    "heatmapYLabels": {
      "description": "Heatmap Y-axis labels — business units (from child accounts or contact departments). Keep each ≤16 chars; long labels widen the row-label gutter and squeeze the grid. Abbreviate business-unit names.",
      "type": "array",
      "items": {
        "type": "string",
        "maxLength": 16
      },
      "example": [
        "Clinical",
        "Finance",
        "Operations",
        "IT"
      ]
    },
    "heatmapDomain": {
      "description": "Color-scale domain as [0, maxValue].",
      "type": "array",
      "items": {
        "type": "number"
      },
      "example": [
        0,
        400000
      ]
    },
    "heatmapCells": {
      "description": "One entry per owned product×BU combo; drives the heatmap. Omit whitespace combos so they render empty.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "x": {
            "description": "Product label (matches an entry in heatmapXLabels).",
            "type": "string"
          },
          "y": {
            "description": "Business-unit label (matches an entry in heatmapYLabels).",
            "type": "string"
          },
          "value": {
            "description": "Cell value (adoption/ARR) — drives the color.",
            "type": "number"
          },
          "valueLabel": {
            "description": "Display label for the cell.",
            "type": "string"
          }
        }
      },
      "example": [
        {
          "x": "Platform",
          "y": "Clinical",
          "value": 400000,
          "valueLabel": "$400K"
        },
        {
          "x": "Analytics",
          "y": "Clinical",
          "value": 120000,
          "valueLabel": "$120K"
        },
        {
          "x": "Platform",
          "y": "Finance",
          "value": 260000,
          "valueLabel": "$260K"
        },
        {
          "x": "Data",
          "y": "Finance",
          "value": 90000,
          "valueLabel": "$90K"
        },
        {
          "x": "Platform",
          "y": "Operations",
          "value": 180000,
          "valueLabel": "$180K"
        },
        {
          "x": "Automation",
          "y": "Operations",
          "value": 150000,
          "valueLabel": "$150K"
        },
        {
          "x": "Security",
          "y": "IT",
          "value": 200000,
          "valueLabel": "$200K"
        },
        {
          "x": "Platform",
          "y": "IT",
          "value": 100000,
          "valueLabel": "$100K"
        }
      ]
    },
    "piechartCaption": {
      "description": "Caption for the live-ARR breakdown pie.",
      "type": "string",
      "example": "Live ARR by product"
    },
    "piechartCenterLabel": {
      "description": "Pie center label.",
      "type": "string",
      "example": "Live ARR"
    },
    "piechartCenterValue": {
      "description": "Pie center value — total live ARR.",
      "type": "string",
      "example": "$1.2M"
    },
    "piechartSlices": {
      "description": "Live ARR breakdown — one slice per segment. Empty array → the pie is omitted.",
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
            "description": "Optional emphasis; set \"highlight\" on the largest slice.",
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
          "label": "Platform",
          "value": 800000,
          "role": "highlight"
        },
        {
          "label": "Analytics",
          "value": 120000
        },
        {
          "label": "Automation",
          "value": 130000
        },
        {
          "label": "Security",
          "value": 150000
        }
      ]
    },
    "datagridCaption": {
      "description": "Caption for the expansion-plays datagrid.",
      "type": "string",
      "example": "Top expansion plays, ranked by fit and reachable ARR"
    },
    "datagridRows": {
      "description": "Expansion plays — one row per play. Empty array → the datagrid is omitted.",
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
          "play": {
            "description": "The expansion play.",
            "type": "string"
          },
          "unit": {
            "description": "Target business unit.",
            "type": "string"
          },
          "fit": {
            "description": "Fit score (number).",
            "type": "number"
          },
          "arr": {
            "description": "Expansion ARR opportunity, in dollars (number).",
            "type": "number"
          },
          "motion": {
            "description": "Recommended motion badge cell.",
            "type": "object",
            "properties": {
              "value": {
                "description": "Motion label.",
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
          }
        }
      },
      "example": [
        {
          "status": {
            "value": "Ready",
            "badgeVariant": "success"
          },
          "play": "Analytics for Clinical",
          "unit": "Clinical",
          "fit": 5,
          "arr": 480000,
          "motion": {
            "value": "Warm intro",
            "badgeVariant": "success"
          }
        },
        {
          "status": {
            "value": "Qualify",
            "badgeVariant": "info"
          },
          "play": "Data platform for Finance",
          "unit": "Finance",
          "fit": 4,
          "arr": 620000,
          "motion": {
            "value": "Discovery",
            "badgeVariant": "info"
          }
        },
        {
          "status": {
            "value": "Qualify",
            "badgeVariant": "info"
          },
          "play": "Automation for Operations",
          "unit": "Operations",
          "fit": 4,
          "arr": 330000,
          "motion": {
            "value": "Champion build",
            "badgeVariant": "info"
          }
        },
        {
          "play": "Support tier upgrade",
          "unit": "IT",
          "fit": 3,
          "arr": 320000,
          "motion": {
            "value": "Nurture",
            "badgeVariant": "neutral"
          }
        }
      ]
    },
    "calloutTitle": {
      "description": "Synthesis callout heading — the top expansion play.",
      "type": "string",
      "example": "Start with Clinical analytics"
    },
    "calloutDescription": {
      "description": "Synthesis callout body — the play and the move.",
      "type": "string",
      "example": "Clinical already runs Platform at full spend and has a warm champion — Analytics is a natural next buy at ~$480K. Pair it with the Finance data play for a combined $1.1M expansion path this half."
    },
    "primaryButtonLabel": {
      "description": "Primary button label (action/sendMessage).",
      "type": "string",
      "example": "Draft expansion plan"
    },
    "primaryButtonContent": {
      "description": "First-person prompt the primary button sends (action/sendMessage).",
      "type": "string",
      "example": "Draft an expansion plan pairing Clinical analytics (~$480K, warm intro ready) with Finance data platform (~$620K, discovery next) for a $1.1M combined play at Meridian Health."
    },
    "accountUrl": {
      "description": "Account Lightning URL for the \"View in Salesforce\" button.",
      "type": "string",
      "example": "https://org.lightning.force.com/lightning/r/Account/001AX000004pQ2rYAE/view"
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
              "isWrapped": false
            },
            "children": [
              {
                "definition": "tile/icon",
                "attributes": {
                  "name": "users",
                  "size": "xl",
                  "alt": ""
                }
              },
              {
                "definition": "tile/text",
                "attributes": {
                  "text": "{{title}}",
                  "variant": "h1"
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
              "isWrapped": false
            },
            "children": [
              {
                "definition": "tile/column",
                "attributes": {
                  "width": "lg"
                },
                "children": [
                  {
                    "definition": "tile/heatmap",
                    "attributes": {
                      "layout": "matrix",
                      "caption": "{{heatmapCaption}}",
                      "xLabels": "{{heatmapXLabels}}",
                      "yLabels": "{{heatmapYLabels}}",
                      "encode": "color",
                      "scale": "sequential",
                      "valueFormat": "currency",
                      "domain": "{{heatmapDomain}}",
                      "cells": "{{heatmapCells}}"
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
                      "caption": "{{piechartCaption}}",
                      "variant": "donut",
                      "valueFormat": "currency",
                      "centerLabel": "{{piechartCenterLabel}}",
                      "centerValue": "{{piechartCenterValue}}",
                      "slices": "{{piechartSlices}}"
                    }
                  }
                ]
              }
            ]
          },
          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{datagridCaption}}",
              "appearance": "striped",
              "defaultSort": {
                "key": "arr",
                "direction": "desc"
              },
              "columns": [
                {
                  "key": "status",
                  "header": "Status",
                  "type": "badge"
                },
                {
                  "key": "play",
                  "header": "Play",
                  "type": "text"
                },
                {
                  "key": "unit",
                  "header": "Business unit",
                  "type": "text"
                },
                {
                  "key": "fit",
                  "header": "Fit",
                  "type": "number",
                  "align": "right"
                },
                {
                  "key": "arr",
                  "header": "ARR",
                  "type": "currency",
                  "align": "right",
                  "sortable": true
                },
                {
                  "key": "motion",
                  "header": "Next step",
                  "type": "badge"
                }
              ],
              "rows": "{{datagridRows}}",
              "size": "sm"
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
                "attributes": {
                  "gap": "sm",
                  "align": "center",
                  "isWrapped": true
                },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{primaryButtonLabel}}",
                      "variant": "primary",
                      "actions": {
                        "click": [
                          {
                            "definition": "action/sendMessage",
                            "attributes": {
                              "content": "{{primaryButtonContent}}"
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
                              "url": "{{accountUrl}}"
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

Self-verification before calling:
- [ ] Numeric attributes (heatmap cell `value`/`domain`, `datagrid` `arr`/`fit`, piechart slice `value`) are numbers, not strings.
- [ ] Heatmap has a cell only for owned combos (whitespace omitted → dashed/empty); axis labels short; `heatmapDomain` = `[0, largestCellValue]`.
- [ ] `datagrid` plays with warm access or ready motion carry a leading `status` object; speculative plays carry neither.
- [ ] Donut slices sum to the `centerValue` live ARR; zero-ARR products dropped; largest slice `highlight`ed.



## 7. Text — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Expansion Whitespace: [Account / scope]

## Owned vs possible
[the grid]

## Top plays
1. **[Play]** - est. $[range] - evidence: [source] - way in: [person/path] - first move: [action]
2. ...

## Not yet credible (parking lot)
- [Items with no evidence - what signal would promote them]

## Ready to create

For each top play, present concrete Opportunity proposal:

📋 **Opportunity: [Account] - [Product/Play]**
```
Name: "[Account] - [Product] Expansion"
Account: [account name + link]
Type: Existing Customer - Expansion
Amount: $[estimated amount based on sizing heuristics]
Stage: [initial stage, typically Discovery or Qualified]
Close Date: [Q end date, 90-120 days out]
Description: [evidence + way in + first move]

Create this opportunity?
```

Repeat for each play. On read-only connector, output as checklist for manual creation.
```

For book-level sweeps, output ranked account list with their single best play each, plus opportunity proposals ready to create.
