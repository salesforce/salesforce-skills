---
name: query-activity-history
description: "Build an interaction timeline from closed Salesforce Tasks and Events on one Account, Contact, Lead or Opportunity, with dates, people and notes. Use when inspecting what happened on a record or reviewing its activity. To create an entry, use log-activity."
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
# Goal:
Pull and summarize the `ActivityHistory` for ONE `Account`, `Contact`, `Lead`, or `Opportunity` — the timeline of closed Tasks and Events on that record.

# Audience:
Sales-org workers who want results fast. Minimize thinking when it's not needed; get them the timeline.

# Rules:

- **Only these four parents expose `ActivityHistories`: `Account`, `Contact`, `Lead`, `Opportunity`.** Any other object → stop and tell the user; don't attempt the query.
- `ActivityHistory` is a **child subquery only** — it can't be queried standalone, and UI-API GraphQL doesn't expose it, so this skill uses **SOQL at `v63.0`**. Every field below is standard and fixed; no schema grounding is needed.
- Render `ActivitySubtype` (Call/Email/Task/Event), NOT `ActivityType` — the latter is often empty.
- A blank/absent history is a valid "no activity" result, not an error.

# Query Activity History

## 1. Validate the object

`objectName` must be one of `Account`, `Contact`, `Lead`, `Opportunity` (key prefixes `001`/`003`/`00Q`/`006`). Anything else → stop, tell the user only those four are supported, don't query.

## 2. Resolve the record

If the user gave an Id matching the object's prefix, use it. Otherwise look up by name (`Name` works for all four — compound for Contact/Lead):

```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
         queryParams: { "q": "SELECT Id, Name FROM [objectName] WHERE Name LIKE '%[match]%' LIMIT 5" })
```

- **One match** → use its `Id`. **Multiple** → list (Name · Id) and ask which. **None** → tell the user no `[objectName]` by that name exists; never invent or create one.

## 3. Query activity history

Subquery from the resolved parent (standard fields, no grounding):

```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
         queryParams: { "q": "SELECT (SELECT ActivityDate, ActivitySubtype, ActivityType, CompletedDateTime, Description, Subject, OwnerId, Owner.Name, CreatedById, CreatedBy.Name, WhoId, Who.Name, StartDateTime, EndDateTime, LastModifiedDate FROM ActivityHistories ORDER BY ActivityDate DESC NULLS LAST, LastModifiedDate DESC LIMIT 500) FROM [objectName] WHERE Id = '[recordId]'" })
```

- **On error `"There is an implementation restriction on ActivityHistories"`** (very large history) → retry the exact same query with `LIMIT 500` appended inside the subquery (before the closing `)`).
- Response is one parent record with a nested `ActivityHistories` collection. Absent/empty collection = valid "no activity", not an error.
- Use `ActivitySubtype` for the type; `ActivityType` is often blank.

## 4. Render → **Step R**.

## Step R — Render

When the data is assembled, call `display_widget`; a single one-line "Displaying the visualization now (this may take a minute)." notice may precede it.

### Self-verification (before calling display_widget)

- [ ] `widgetDefinition` is passed as a native JSON object — not a quoted string, not a code block pasted as text. If the value starts with `"{"`, it is wrong.

The widget template is embedded below — resolve its tokens and call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once (see the `widgetDefinition` param for token-resolution rules).

Every token is backed by the Step 3 subquery: `ActivityDate` drives both the heatmap day buckets and each datagrid `date`; `ActivitySubtype` → the type badge; `Subject` → `note`; `Who.Name` → `who`; `ActivityHistories.totalSize` → `datagridTotalRows`. The heatmap domain, cadence buckets, and the synthesis callout are computed in-prompt from those rows. `viewRecordUrl` is `https://<myDomain>/lightning/r/<ObjectName>/<recordId>/view`. `TotalCount = 0` → skip the widget and render only the empty-state markdown below. Never fabricate activities.

Two blocks below: first the **variable contract** (`renderer.props.schema.json`) — every `{{token}}`'s type + a worked example, use it to compute each value; then the **widget template** to hydrate. Substitute your computed values into the template's `{{token}}`s (see the token-typing rules above), leaving no `{{…}}`/`{!…}`.
```json
{
  "$comment": "Variable contract for the native-mosaic dynamic-mode template (renderer.json, sibling). This is NOT a separate display_widget call — it names every {{token}} in the template with its type and a worked example so you compute the right value for each. Workflow: build a props object with these keys, substitute each into the matching {{token}} in renderer.json (a slot that is only a {{token}} becomes the typed value — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string interpolates as text; a key you have no data for is omitted so that leaf drops), then call display_widget({ resourceType: 'dynamic', widgetDefinition: <the hydrated template> }) once with no {{…}}/{!…} left. Realistic values: sample-data.json (sibling). Authoring guidance (from the skill): `pageTitle` (e.g. \"Activity history — <RecordName>\") · `pageSubtitle` (one line: window · N touches · last contact) · **calendar heatmap** `heatmapCaption`, `heatmapDomain` (2-element `[min,max]` number array, e.g. `[0,4]`), `heatmapDays` (array of `{date: \"YYYY-MM-DD\", value: number}` — one per day, touch cadence over the last ~12 weeks) · **datagrid** `datagridCaption`, `datagridTotalRows` (number = `ActivityHistories.totalSize`), `datagridRows` (array of the most recent ~5: `{date: \"YYYY-MM-DD\", type: {value, badgeVariant}, who, note}` — `type.value` is `ActivitySubtype` (Call/Email/Task/Event/Meeting), `who` is `Who.Name` or \"—\", `note` is `Subject`) · **callout** `calloutVariant` (info), `calloutTitle`/`calloutDescription` (the engagement read + the gap), `primaryButtonLabel`/`primaryButtonMsg` (`action/sendMessage`, first-person next-step prompt), `viewRecordUrl` (the record's Lightning URL for \"View in Salesforce\").",
  "props": {
    "pageTitle": {
      "description": "Page title (e.g. \"Activity history — <RecordName>\").",
      "type": "string",
      "example": "Activity history — Cobalt Robotics"
    },
    "pageSubtitle": {
      "description": "One line: window, touch count, last contact.",
      "type": "string",
      "example": "Last 90 days · 47 touches · last contact 2 days ago"
    },
    "heatmapCaption": {
      "description": "Caption for the calendar heatmap.",
      "type": "string",
      "example": "Touch cadence — last 12 weeks, darker is more activity"
    },
    "heatmapDomain": {
      "description": "Color-scale domain as [min, max] (e.g. [0, 4]).",
      "type": "array",
      "items": {
        "type": "number"
      },
      "example": [
        0,
        4
      ]
    },
    "heatmapDays": {
      "description": "Daily touch cadence over ~12 weeks — one entry per day.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "date": {
            "description": "Day, ISO YYYY-MM-DD.",
            "type": "string"
          },
          "value": {
            "description": "Touch count that day — drives the cell color.",
            "type": "number"
          }
        }
      },
      "example": [
        {
          "date": "2026-05-04",
          "value": 1
        },
        {
          "date": "2026-05-06",
          "value": 2
        },
        {
          "date": "2026-05-11",
          "value": 1
        },
        {
          "date": "2026-05-14",
          "value": 3
        },
        {
          "date": "2026-05-19",
          "value": 1
        },
        {
          "date": "2026-05-26",
          "value": 2
        },
        {
          "date": "2026-06-01",
          "value": 1
        },
        {
          "date": "2026-06-03",
          "value": 2
        },
        {
          "date": "2026-06-09",
          "value": 4
        },
        {
          "date": "2026-06-15",
          "value": 1
        },
        {
          "date": "2026-06-22",
          "value": 2
        },
        {
          "date": "2026-06-29",
          "value": 1
        },
        {
          "date": "2026-07-06",
          "value": 3
        },
        {
          "date": "2026-07-13",
          "value": 2
        },
        {
          "date": "2026-07-20",
          "value": 4
        },
        {
          "date": "2026-07-21",
          "value": 2
        },
        {
          "date": "2026-07-22",
          "value": 3
        }
      ]
    },
    "calloutVariant": {
      "description": "Callout color; typically \"info\".",
      "type": "string",
      "enum": [
        "error",
        "warning",
        "success",
        "info",
        "recommended"
      ],
      "example": "info"
    },
    "calloutTitle": {
      "description": "Synthesis callout heading — the engagement read.",
      "type": "string",
      "example": "Engaged, but the CIO is dark"
    },
    "calloutDescription": {
      "description": "Synthesis callout body — the read and the gap.",
      "type": "string",
      "example": "Cadence is healthy — 47 touches and steady weekly contact with the CFO and VP Eng. No logged activity with the CIO in 90 days; that gap lines up with the stakeholder risk on this deal."
    },
    "primaryButtonLabel": {
      "description": "Primary button label (action/sendMessage).",
      "type": "string",
      "example": "Draft CIO intro ask"
    },
    "primaryButtonMsg": {
      "description": "First-person prompt the primary button sends (action/sendMessage).",
      "type": "string",
      "example": "Draft a warm intro ask to Dana Kwon (CFO) to connect us with the CIO at Cobalt Robotics for a meeting this week."
    },
    "viewRecordUrl": {
      "description": "The record's Lightning URL for the \"View in Salesforce\" button.",
      "type": "string",
      "example": "https://org.lightning.force.com/lightning/r/Account/001AX000004pQ2rYAE/view"
    },
    "datagridCaption": {
      "description": "Caption for the activity datagrid.",
      "type": "string",
      "example": "Recent touches, newest first"
    },
    "datagridTotalRows": {
      "description": "Total activity count (ActivityHistories.totalSize) — a number.",
      "type": "number",
      "example": 47
    },
    "datagridRows": {
      "description": "Most recent ~5 activities — one row per activity. Empty array → the datagrid is omitted.",
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "date": {
            "description": "Activity date, ISO YYYY-MM-DD.",
            "type": "string"
          },
          "type": {
            "description": "Activity-type badge cell.",
            "type": "object",
            "properties": {
              "value": {
                "description": "Activity subtype (Call / Email / Task / Event / Meeting).",
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
          "who": {
            "description": "Contact name (Who.Name) or \"—\".",
            "type": "string"
          },
          "note": {
            "description": "Activity subject.",
            "type": "string"
          }
        }
      },
      "example": [
        {
          "date": "2026-07-22",
          "type": {
            "value": "Meeting",
            "badgeVariant": "neutral"
          },
          "who": "Dana Kwon (CFO)",
          "note": "Reviewed contract terms, agreed Friday follow-up"
        },
        {
          "date": "2026-07-21",
          "type": {
            "value": "Call",
            "badgeVariant": "info"
          },
          "who": "Raj Patel (VP Eng)",
          "note": "Walked ROI model, strong support"
        },
        {
          "date": "2026-07-20",
          "type": {
            "value": "Email",
            "badgeVariant": "neutral"
          },
          "who": "Procurement",
          "note": "Sent order form, awaiting PO"
        },
        {
          "date": "2026-07-13",
          "type": {
            "value": "Meeting",
            "badgeVariant": "neutral"
          },
          "who": "Buying committee",
          "note": "Demo of expansion modules"
        },
        {
          "date": "2026-07-06",
          "type": {
            "value": "Call",
            "badgeVariant": "info"
          },
          "who": "Dana Kwon (CFO)",
          "note": "Budget confirmed for renewal + expansion"
        }
      ]
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
                  "name": "activity",
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
            "definition": "tile/text",
            "attributes": {
              "text": "{{pageSubtitle}}",
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
              "align": "start",
              "isWrapped": false
            },
            "children": [
              {
                "definition": "tile/column",
                "attributes": {
                  "width": "md"
                },
                "children": [
                  {
                    "definition": "tile/heatmap",
                    "attributes": {
                      "layout": "calendar",
                      "caption": "{{heatmapCaption}}",
                      "encode": "color",
                      "scale": "sequential",
                      "valueFormat": "number",
                      "domain": "{{heatmapDomain}}",
                      "days": "{{heatmapDays}}"
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
                    "definition": "tile/callout",
                    "attributes": {
                      "variant": "{{calloutVariant}}",
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
                                      "content": "{{primaryButtonMsg}}"
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
                                      "url": "{{viewRecordUrl}}"
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
            ]
          },
          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{datagridCaption}}",
              "appearance": "striped",
              "totalRows": "{{datagridTotalRows}}",
              "columns": [
                {
                  "key": "date",
                  "header": "Date",
                  "type": "date"
                },
                {
                  "key": "type",
                  "header": "Type",
                  "type": "badge"
                },
                {
                  "key": "who",
                  "header": "With",
                  "type": "text"
                },
                {
                  "key": "note",
                  "header": "Summary",
                  "type": "text"
                }
              ],
              "rows": "{{datagridRows}}"
            }
          }
        ]
      }
    }
  }
}
```



Markdown — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED. Apply the formatting rules below:

```markdown
# Activity History: [RecordName] ([ObjectName])
**[TotalCount] activities**  |  **Last:** [LastActivityDate]  |  **Owner:** [OwnerName]

| Date | Type | Subject | Owner | With |
|---|---|---|---|---|
| [ActivityDate] | [ActivitySubtype] | [Subject] | [Owner.Name] | [Who.Name or —] |
| … | | | | |
```

- One row per activity, most recent first (sorted by `ActivityDate` desc, then `LastModifiedDate` desc).
- Show at most **20**; if `TotalCount > 20` append `…and [N] older activities not shown`.
- `TotalCount = 0` → render only `No activity history found for [RecordName].`
- Label undated activities "Undated"; omit the "With" cell when `Who.Name` is null.
- Append each non-empty `Description` as a short sub-bullet under its row (truncate at 200 chars), or add a Description column inline — don't drop it (the widget path shows it).
