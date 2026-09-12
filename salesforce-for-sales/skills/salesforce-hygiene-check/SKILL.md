---
name: salesforce-hygiene-check
description: "Audit open Salesforce opportunities for missing fields, stale dates, weak next steps, stage mismatches and single-threading, producing prioritized fixes. Use to check pipeline data quality, find incomplete deals or plan CRM cleanup without changing records."
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


# Salesforce Hygiene Check

Read-only audit of open opps → fix checklist you apply yourself (nothing is written). Ground → one read → run checks → output.

## 1. Ground (hardcoded — Opportunity only)

Opportunity always exists; naming a missing object fails the whole call. Its fields reveal this org's `__c` hygiene fields (competitor, required-per-stage, next-step trackers) — use exact names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label } } } }\"}" })
```

## 2. Read the open book (one call, scope: MINE)

`scope: MINE` = running user's book (no user lookup). Splice confirmed `__c` fields into `<OPP_CUSTOM>`. **Check `{` vs `}` balance before dispatching** — splicing custom fields is where a brace drops.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(scope: MINE, where: { IsClosed: { eq: false } }, orderBy: { CloseDate: { order: ASC } }, first: 200) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } NextStep { value } LastActivityDate { value } CreatedDate { value } Type { value } LeadSource { value } <OPP_CUSTOM> Account { Name { value } } OpportunityContactRoles { edges { node { Role { value } Contact { Name { value } } } } } } } } } } }\"}" })
```

`InvalidSyntax` / "offending token `<EOF>`" → missing a closing `}`; add it and retry.

## 3. Run checks (per opp)

Flag: **Amount** blank/$0 · **CloseDate** past, or unchanged since creation on a >30d opp · **NextStep** blank or unchanged 14d+ · **Stage age** stuck (>2× median) · **Activity** LastActivityDate >14d · **Contacts** none or single-threaded (≤1 role) · **Stage criteria** exit criteria not evidenced. Required-per-stage expectations are external — infer from the org's data or ask once; never invent.

## 4. Suggest values (cite real names — never generic "champion")

Per flag: **NextStep** `MM/DD - <verb> <what> with <real Contact name>` from recent email/doc context · **CloseDate** realistic per stage + median cycle · **Stage** correct stage if evidence shows a mismatch.

## 5. Widget (default output when `display_widget` is present: Cowork/desktop/web)

When the data is assembled, call `display_widget`; a single one-line "Displaying the visualization now (this may take a minute)." notice may precede it.

### Self-verification (before calling display_widget)

- [ ] `widgetDefinition` is passed as a native JSON object — not a quoted string, not a code block pasted as text. If the value starts with `"{"`, it is wrong.

The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (chart/piechart/datagrid arrays) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text. Layout note: the hygiene-state donut runs with `showLegend:false` and sits in a row beside a text column (`donutAsideTitle` + `donutAside`); the issue-frequency column chart is full-width, preceded by a caption pair (`chartAsideTitle` + `chartAside`). A column chart must be full-width to keep its axis, value labels, and bar height legible — do not put it in a shared row.

Two blocks below: first the **variable contract** (`renderer.props.schema.json`) — every `{{token}}`'s type + a worked example, use it to compute each value; then the **widget template** to hydrate. Substitute your computed values into the template's `{{token}}`s (see the token-typing rules above), leaving no `{{…}}`/`{!…}`.
```json
{
  "$comment": "Variable contract for the native-mosaic dynamic-mode template (renderer.json, sibling). This is NOT a separate display_widget call — it names every {{token}} in the template with its type and a worked example so you compute the right value for each. Workflow: build a props object with these keys, substitute each into the matching {{token}} in renderer.json (a slot that is only a {{token}} becomes the typed value — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string interpolates as text; a key you have no data for is omitted so that leaf drops), then call display_widget({ resourceType: 'dynamic', widgetDefinition: <the hydrated template> }) once with no {{…}}/{!…} left. Realistic values: sample-data.json (sibling). Authoring guidance (from the skill): `hygieneTitle` (plain string — e.g. \"Pipeline hygiene — Dana Ruiz\") · `oppCountBadge` (plain string — e.g. \"18 OPEN OPPS\") · `hygieneSubtitle` (plain string — one-line summary e.g. \"18 open opps · 4 critical, 5 need attention, 9 clean\") · `totalOpps` (plain string — formatted count e.g. \"18\") · `donutAsideTitle donutAside` (short title + one-sentence breakdown beside the hygiene-state donut; because the legend is off, `donutAside` must name every slice — clean/needs-attention/critical — with its count and % in prose) · `hygieneSlices` (donut slices `{label,value,role?}`, drop zero-count, `role:\"highlight\"` on Critical) · `chartAsideTitle chartAside` (short title + one-sentence takeaway above the full-width issue chart; interpret which issues dominate rather than re-listing every bar) · `issueCategories`/`issueSeries` (bar, most-common first, matching order, drop zeros; `issueSeries` is one object `{name:\"Opps\", data:[...numbers...]}`) · `flaggedRows` (`{name (plain string — format as the opportunity name (e.g. \"Meridian Health platform\"); names must be plain strings, not objects: use `Opportunity.Name.value` from the SF response), amount(num), close(YYYY-MM-DD), issue:{value,badgeVariant}, fix, status:{value,badgeVariant}}` — `error`/\"Critical\" for past-close or no-next-step-near-close, `warning`/\"Needs attention\" for stale/missing-amount; clean rows omit a leading `status` object) · footer `flaggedCount` `totalAtRisk`. Callout: `synthTitle` (plain string — e.g. \"Two fixes can't wait\") · `synthDetail` (plain string — one to two sentences) · `ctaLabel` (plain string — button label) · `ctaMsg` (plain string — first-person prompt for the action button) · `hygieneUrl` (plain string — Lightning list URL for \"View in Salesforce\").",
  "props": {
    "hygieneTitle": {
      "description": "Page title (e.g. \"Pipeline hygiene — Dana Ruiz\").",
      "type": "string",
      "example": "Pipeline hygiene — Dana Ruiz"
    },
    "oppCountBadge": {
      "description": "Header count badge (e.g. \"18 OPEN OPPS\").",
      "type": "string",
      "example": "18 OPEN OPPS"
    },
    "hygieneSubtitle": {
      "description": "One-line summary (e.g. \"18 open opps · 4 critical, 5 need attention, 9 clean\").",
      "type": "string",
      "example": "18 open opps · 4 critical, 5 need attention, 9 clean"
    },
    "totalOpps": {
      "description": "Formatted total open-opp count (string, e.g. \"18\").",
      "type": "string",
      "example": "18"
    },
    "hygieneSlices": {
      "description": "Hygiene-state donut slices — one per state (clean / needs-attention / critical); drop zero-count slices. Empty array → the donut is omitted.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "label": {
            "description": "State label.",
            "type": "string"
          },
          "value": {
            "description": "Opp count in this state.",
            "type": "number"
          },
          "role": {
            "description": "Optional emphasis; set \"highlight\" on Critical.",
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
          "label": "Clean",
          "value": 9
        },
        {
          "label": "Needs attention",
          "value": 5
        },
        {
          "label": "Critical",
          "value": 4,
          "role": "highlight"
        }
      ]
    },
    "donutAsideTitle": {
      "description": "Section title beside the hygiene donut.",
      "type": "string",
      "example": "Half the pipeline needs work"
    },
    "donutAside": {
      "description": "One-sentence breakdown naming every slice (clean / needs-attention / critical) with its count and % (replaces the off legend).",
      "type": "string",
      "example": "Half the pipeline is clean: 9 of 18 opps (50%). The other half needs work, split between 4 critical (22%) and 5 needs attention (28%)."
    },
    "chartAsideTitle": {
      "description": "Section title above the issue chart.",
      "type": "string",
      "example": "Issue frequency"
    },
    "chartAside": {
      "description": "One-sentence takeaway interpreting which issues dominate.",
      "type": "string",
      "example": "Flags skew to the top two: past close date and no next step hit the most opps, and both clear with a single CRM field update."
    },
    "issueCategories": {
      "description": "Issue-type names for the chart's x-axis, most-common first.",
      "type": "array",
      "items": {
        "type": "string"
      },
      "example": [
        "Past close date",
        "No next step",
        "Stale > 30d",
        "Missing amount",
        "No contact role"
      ]
    },
    "issueSeries": {
      "description": "Issue-chart series — one object {name:\"Opps\", data}; data matches issueCategories order.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "description": "Series name.",
            "type": "string"
          },
          "data": {
            "description": "Opp count per issue — a number array matching issueCategories.",
            "type": "array",
            "items": {
              "type": "number"
            }
          }
        }
      },
      "example": [
        {
          "name": "Opps",
          "data": [
            6,
            5,
            4,
            3,
            2
          ]
        }
      ]
    },
    "flaggedRows": {
      "description": "Flagged opps needing a fix — one row per opp. Empty array → the datagrid is omitted.",
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
          "name": {
            "description": "Opportunity name, a plain string (use Opportunity.Name.value — never a nested object).",
            "type": "string"
          },
          "amount": {
            "description": "Deal amount (number).",
            "type": "number"
          },
          "close": {
            "description": "Close date, ISO YYYY-MM-DD.",
            "type": "string"
          },
          "issue": {
            "description": "Issue badge cell.",
            "type": "object",
            "properties": {
              "value": {
                "description": "Issue label.",
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
          "fix": {
            "description": "The recommended fix (text).",
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
          "name": "Meridian Health platform",
          "amount": 2400000,
          "close": "2026-06-30",
          "issue": {
            "value": "Past close",
            "badgeVariant": "error"
          },
          "fix": "Close date 24d in the past — reset or mark closed"
        },
        {
          "status": {
            "value": "Critical",
            "badgeVariant": "error"
          },
          "name": "Cobalt Robotics renewal",
          "amount": 1800000,
          "close": "2026-07-30",
          "issue": {
            "value": "No next step",
            "badgeVariant": "error"
          },
          "fix": "Add a dated next step — closes in 6 days"
        },
        {
          "status": {
            "value": "Needs attention",
            "badgeVariant": "warning"
          },
          "name": "Northwind logistics",
          "amount": 450000,
          "close": "2026-09-15",
          "issue": {
            "value": "Stale 55d",
            "badgeVariant": "warning"
          },
          "fix": "No activity in 55 days — log a touch or downgrade"
        },
        {
          "status": {
            "value": "Needs attention",
            "badgeVariant": "warning"
          },
          "name": "Summit Analytics",
          "amount": 300000,
          "close": "2026-08-20",
          "issue": {
            "value": "No amount",
            "badgeVariant": "warning"
          },
          "fix": "Amount is blank — set from the proposal"
        }
      ]
    },
    "synthTitle": {
      "description": "Synthesis callout heading (e.g. \"Two fixes can't wait\").",
      "type": "string",
      "example": "Two fixes can't wait"
    },
    "synthDetail": {
      "description": "Synthesis callout body — one to two sentences.",
      "type": "string",
      "example": "Meridian's close date is 24 days past and Cobalt has no next step with 6 days to close. Both are 7-figure — clean these before the forecast call."
    },
    "ctaLabel": {
      "description": "Primary button label (action/sendMessage).",
      "type": "string",
      "example": "Draft fix plan"
    },
    "ctaMsg": {
      "description": "First-person prompt the primary button sends (action/sendMessage).",
      "type": "string",
      "example": "Draft a plan to fix the two critical 7-figure opportunities before the forecast call."
    },
    "hygieneUrl": {
      "description": "Lightning list URL for the \"View in Salesforce\" button.",
      "type": "string",
      "example": "https://org.lightning.force.com/lightning/o/Opportunity/list"
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
                      "name": "check-circle",
                      "size": "xl",
                      "alt": ""
                    }
                  },
                  {
                    "definition": "tile/text",
                    "attributes": {
                      "text": "{{hygieneTitle}}",
                      "variant": "h1"
                    }
                  }
                ]
              },
              {
                "definition": "tile/badge",
                "attributes": {
                  "label": "{{oppCountBadge}}",
                  "variant": "info"
                }
              }
            ]
          },
          {
            "definition": "tile/text",
            "attributes": {
              "text": "{{hygieneSubtitle}}",
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
              "align": "center",
              "isWrapped": false
            },
            "children": [
              {
                "definition": "tile/column",
                "attributes": {
                  "width": "auto"
                },
                "children": [
                  {
                    "definition": "tile/piechart",
                    "attributes": {
                      "variant": "donut",
                      "caption": "Opps by hygiene state",
                      "valueFormat": "number",
                      "showLegend": false,
                      "centerLabel": "Open opps",
                      "centerValue": "{{totalOpps}}",
                      "slices": "{{hygieneSlices}}"
                    }
                  }
                ]
              },
              {
                "definition": "tile/column",
                "attributes": {
                  "gap": "sm",
                  "align": "start",
                  "width": "stretch"
                },
                "children": [
                  {
                    "definition": "tile/text",
                    "attributes": {
                      "text": "{{donutAsideTitle}}",
                      "variant": "section-title"
                    }
                  },
                  {
                    "definition": "tile/text",
                    "attributes": {
                      "text": "{{donutAside}}",
                      "variant": "body",
                      "color": "muted"
                    }
                  }
                ]
              }
            ]
          },
          {
            "definition": "tile/text",
            "attributes": {
              "text": "{{chartAsideTitle}}",
              "variant": "section-title"
            }
          },
          {
            "definition": "tile/text",
            "attributes": {
              "text": "{{chartAside}}",
              "variant": "body",
              "color": "muted"
            }
          },
          {
            "definition": "tile/chart",
            "attributes": {
              "chartType": "column",
              "caption": "Most common issues across the 18 open opps",
              "categories": "{{issueCategories}}",
              "series": "{{issueSeries}}",
              "valueFormat": "number",
              "showValues": true,
              "showLegend": false
            }
          },
          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Flagged opps with the specific fix, most severe first",
              "appearance": "striped",
              "size": "sm",
              "defaultSort": {
                "key": "amount",
                "direction": "desc"
              },
              "columns": [
                {
                  "key": "status",
                  "header": "Status",
                  "type": "badge"
                },
                {
                  "key": "name",
                  "header": "Opportunity",
                  "type": "text"
                },
                {
                  "key": "amount",
                  "header": "Amount",
                  "type": "currency",
                  "align": "right",
                  "sortable": true
                },
                {
                  "key": "close",
                  "header": "Close",
                  "type": "date"
                },
                {
                  "key": "issue",
                  "header": "Issue",
                  "type": "badge"
                },
                {
                  "key": "fix",
                  "header": "Suggested fix",
                  "type": "text"
                }
              ],
              "rows": "{{flaggedRows}}"
            }
          },
          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "warning",
              "title": "{{synthTitle}}",
              "description": "{{synthDetail}}"
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
                      "label": "{{ctaLabel}}",
                      "variant": "primary",
                      "actions": {
                        "click": [
                          {
                            "definition": "action/sendMessage",
                            "attributes": {
                              "content": "{{ctaMsg}}"
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
                              "url": "{{hygieneUrl}}"
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

Validate bucket counts: critical + attention + clean = total open.

```
# Salesforce Hygiene Check — <N> open opps
## Summary
- 🔴 Critical (<N>): past close dates, $0 amounts
- 🟡 Attention (<N>): stale NextStep, no activity 14d+, single-threaded
- ✅ Clean (<N>)
**Validation:** <crit> + <attn> + <clean> = <N total>
## Fix List
### <Account> — <Opp>  [link]  ·  Stage <X> | $<Amt> | Close <Date>
- ⚠️ <issue> …
> **Suggested NextStep:** `MM/DD - <verb> <what> with <Contact>`
> **Suggested CloseDate:** `<Date>` (current is past)
---
## Bulk Actions
- <N> opps need CloseDate pushed · <N> opps have no Contact Roles
```

Recommendations only — apply one at a time with `update-opportunity` (each confirmed), or manually on a read-only connector.
