---
name: calendar-events
description: "Show a schedule from Salesforce Event data with local times, subjects, locations, and linked contacts, accounts or deals. Use to review today's calendar, upcoming meetings, or a past or future schedule; for a broader morning rundown, use daily-briefing."
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

- **Pick View vs Create from the verb before doing anything.** View = show/get/pull up/view/see. Create = create/build/set up/draft/make. Ambiguous → ask which; **never fall through a view request into creating a record.**
- On the create path, flag anything you can't source with `[needs validation]`.
- **`Status` is always `"Not Started"` on creation.** Never create a plan in any other status; lifecycle changes are out of scope.

# Calendar Events

Resolve timezone → compute range (no call) → read Events → render. All dates/times in the user's **local** timezone, not UTC.

## 1. Resolve timezone

Standard field, no grounding needed:

```
dispatch_readonly(method: "GET", url: "/services/data/v66.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { currentUser { TimeZoneSidKey { value } } } }\"}" })
```

Derive the current UTC offset from the IANA zone (e.g. `America/Los_Angeles` → `-07:00` or `-08:00`), accounting for DST at the dates in question — use the actual current date from context as the reference. Unresolvable → fall back to UTC (`+00:00`), note it in the output.

## 2. Date range (prompt-only — no dispatch)

Anchor to the resolved local timezone:
- **today** → today 00:00–23:59 · **tomorrow** → tomorrow 00:00–23:59
- **this/next/last week** → Mon–Sun of that week · **this month** → 1st–last day
- **specific date** → that date 00:00–23:59 · **explicit range** → as given

Always ISO-8601 with the offset from Step 1 (e.g. `2026-08-04T00:00:00-07:00`).

## 3. Read Events

`scope: MINE` already filters to the current user — no Id lookup needed. `%START%`/`%END%` = Step 2's ISO boundaries. `Who`/`What` are polymorphic unions on Event (stable, not org-specific) — span via inline fragments, never bare:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Event(scope: MINE, where: { StartDateTime: { gte: { value: \\\"%START%\\\" }, lt: { value: \\\"%END%\\\" } } }, orderBy: { StartDateTime: { order: ASC } }, first: 100) { edges { node { Id Subject { value } StartDateTime { value displayValue } EndDateTime { value displayValue } Description { value } Location { value } IsAllDayEvent { value } Who { ... on Contact { Name { value } } ... on Lead { Name { value } } } What { ... on Account { Name { value } } ... on Opportunity { Name { value } } } } } } } } } \"}" })
```

Empty `edges` → say "No events found for [range]", don't retry with a broader window unasked.

## 4. Render — widget first

Call `display_widget` immediately after assembling the event list. Do not write markdown first — only fall back to the Step 5 markdown when the tool is unavailable (e.g. Claude Code, where raw HTML would just show up as `<div>` text).

When the data is assembled, call `display_widget`; a single one-line "Displaying the visualization now (this may take a minute)." notice may precede it.

### Self-verification (before calling display_widget)

- [ ] `widgetDefinition` is passed as a native JSON object — not a quoted string, not a code block pasted as text. If the value starts with `"{"`, it is wrong.
- [ ] Every `{{token}}` placeholder replaced with a resolved literal — no `{{…}}` left, no `{!…}` expressions in the widget definition.
- [ ] No graphs (heatmap/piechart/chart/meter/waterfall count = 0).
- [ ] Datagrid `value` is a raw number (deal-linked) or `{ value: 0, display: "—" }` (internal).
- [ ] Datagrid rows with urgent prep state carry `status:{value:"Prep now",badgeVariant:"error"}`.
- [ ] Callout buttons wired to sendMessage (primary) and openLink (secondary).

The widget template is embedded below. Call `display_widget` in **dynamic** mode with it. It is a skeleton: replace every `{{token}}` with a fully-resolved literal computed from the events you gathered — this echo path does no expression compilation, so no `{!…}` bindings.

Two blocks below: first the **variable contract** (`renderer.props.schema.json`) — every `{{token}}`'s type + a worked example, use it to compute each value; then the **widget template** to hydrate. Substitute your computed values into the template's `{{token}}`s (see the token-typing rules above), leaving no `{{…}}`/`{!…}`.
```json
{
  "$comment": "Variable contract for the native-mosaic dynamic-mode template (renderer.json, sibling). This is NOT a separate display_widget call — it names every {{token}} in the template with its type and a worked example so you compute the right value for each. Workflow: build a props object with these keys, substitute each into the matching {{token}} in renderer.json (a slot that is only a {{token}} becomes the typed value — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string interpolates as text; a key you have no data for is omitted so that leaf drops), then call display_widget({ resourceType: 'dynamic', widgetDefinition: <the hydrated template> }) once with no {{…}}/{!…} left. Realistic values: sample-data.json (sibling). Authoring guidance (from the skill): - [ ] Every `{{token}}` placeholder replaced with a resolved literal — no `{{…}}` left, no `{!…}` expressions in the widget definition.\nThe widget template is embedded below. Call `display_widget` in **dynamic** mode with it. It is a skeleton: replace every `{{token}}` with a fully-resolved literal computed from the events you gathered — this echo path does no expression compilation, so no `{!…}` bindings.\n- **Header** — an icon + page-title text (`{{title}}`, e.g. \"Today — Thursday, Jul 24\"), with a one-line caption subhead (`{{subtitle}}` = \"[N] meetings · [N] deal-linked · [N] external · first at [time], last ends [time]\") and a separator.\n- **Schedule datagrid** (`{{datagridCaption}}`, `{{datagridRows}}`) — one row per meeting in order. Columns: Time (text), Meeting (text), Deal (text), Value (currency), Prep (badge). Rows carry a leading `status` object (`{value,badgeVariant}` — value Prep now/Draft/Ready/At risk, badgeVariant error/warning/success) for prep state. Non-deal meetings show \"—\" for deal and a currency cell with `{ value: 0, display: \"—\" }`.\n- **One synthesis callout** (`variant` = `{{calloutVariant}}`, typically \"error\") — `{{calloutTitle}}` and `{{calloutDescription}}` (the single meeting that needs prep before you walk in, why, and the move). It carries two buttons: a primary with `{{primaryButtonLabel}}` and `{{primaryButtonMsg}}` (`action/sendMessage`), and a secondary \"View in Salesforce\" with `{{salesforceUrl}}` (`action/openLink`).\n1. Start from the embedded template above — a valid-JSON widget-definition envelope whose leaf values carry `{{token}}` placeholders.\n2. Resolve every `{{token}}`. A value that is **only** a `{{token}}` (datagrid `rows`) becomes the resolved **typed** literal — numbers stay numbers, arrays stay arrays. A `{{token}}` **inside** a larger string is interpolated as text.\n3. `{{datagridRows}}` is an array of row objects with `time` (text), `title` (text), `deal` (text, \"—\" for internal), `value` (number, or `{ value: 0, display: \"—\" }` for internal), `prep` (`{ value, badgeVariant }`), `status` (`{value,badgeVariant}` — value Prep now/Draft/Ready/At risk, badgeVariant error/warning/success).\n4. The result is hydrated widget definition (no `{{…}}` placeholders remain). Then call:\n- Resolve every `{{token}}` to a literal before calling — numbers stay numbers (`value`), arrays stay arrays.\n- Callout buttons: primary is `action/sendMessage` with a first-person prompt (`{{primaryButtonMsg}}`), secondary is `action/openLink` with `{{salesforceUrl}}` (an Event record URL), opening a new tab.\n- Callout `variant` is tokenized (`{{calloutVariant}}`), typically \"error\" for urgent prep needs.",
  "props": {
    "title": {
      "description": "Page title — the day (e.g. \"Today — Thursday, Jul 24\").",
      "type": "string",
      "example": "Today — Thursday, Jul 24"
    },
    "subtitle": {
      "description": "Caption subhead: meeting count, deal-linked count, external count, first start / last end.",
      "type": "string",
      "example": "6 meetings · 4 deal-linked · 2 external · first at 9:00, last ends 4:30"
    },
    "datagridCaption": {
      "description": "Caption for the schedule datagrid.",
      "type": "string",
      "example": "Schedule, in order"
    },
    "datagridRows": {
      "description": "Meetings for the day — one row per meeting, in time order. Empty array → the datagrid is omitted.",
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
          "time": {
            "description": "Meeting time (text).",
            "type": "string"
          },
          "title": {
            "description": "Meeting title (text).",
            "type": "string"
          },
          "deal": {
            "description": "Linked deal name; \"—\" for non-deal meetings.",
            "type": "string"
          },
          "value": {
            "description": "Deal amount. Use a raw number for a deal-linked meeting; for a non-deal meeting use the sentinel { value: 0, display: \"—\" } to render an em-dash.",
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "object",
                "properties": {
                  "value": {
                    "type": "number"
                  },
                  "display": {
                    "type": "string"
                  }
                }
              }
            ]
          },
          "prep": {
            "description": "Prep-state badge cell.",
            "type": "object",
            "properties": {
              "value": {
                "description": "Prep label shown on the badge.",
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
            "value": "Prep now",
            "badgeVariant": "error"
          },
          "time": "9:00",
          "title": "Cobalt — contract walkthrough",
          "deal": "Cobalt renewal",
          "value": 1800000,
          "prep": {
            "value": "Redlines ready?",
            "badgeVariant": "error"
          }
        },
        {
          "time": "10:30",
          "title": "Pipeline sync (internal)",
          "deal": "—",
          "value": {
            "value": 0,
            "display": "—"
          },
          "prep": {
            "value": "Scoreboard",
            "badgeVariant": "neutral"
          }
        },
        {
          "status": {
            "value": "Ready",
            "badgeVariant": "success"
          },
          "time": "11:30",
          "title": "Delta Systems — demo",
          "deal": "Delta Systems",
          "value": 600000,
          "prep": {
            "value": "Deck loaded",
            "badgeVariant": "success"
          }
        },
        {
          "status": {
            "value": "Draft",
            "badgeVariant": "warning"
          },
          "time": "1:00",
          "title": "Meridian — pricing review",
          "deal": "Meridian expansion",
          "value": 1000000,
          "prep": {
            "value": "Quote draft",
            "badgeVariant": "warning"
          }
        },
        {
          "time": "3:00",
          "title": "1:1 with manager",
          "deal": "—",
          "value": {
            "value": 0,
            "display": "—"
          },
          "prep": {
            "value": "Forecast",
            "badgeVariant": "neutral"
          }
        },
        {
          "status": {
            "value": "At risk",
            "badgeVariant": "warning"
          },
          "time": "4:00",
          "title": "Harbor Freight — check-in",
          "deal": "Harbor Freight",
          "value": 400000,
          "prep": {
            "value": "Stalled 18d",
            "badgeVariant": "warning"
          }
        }
      ]
    },
    "calloutVariant": {
      "description": "Callout color; typically \"error\" for urgent prep.",
      "type": "string",
      "enum": [
        "error",
        "warning",
        "success",
        "info",
        "recommended"
      ],
      "example": "error"
    },
    "calloutTitle": {
      "description": "Synthesis callout heading — the meeting that needs prep before you walk in.",
      "type": "string",
      "example": "The 9:00 needs prep before you walk in"
    },
    "calloutDescription": {
      "description": "Synthesis callout body — why it needs prep and the move.",
      "type": "string",
      "example": "Cobalt contract walkthrough is your biggest meeting today ($1.8M, closes in 6 days) and the redlines aren't back from legal yet. Send them now or reframe the meeting to a timeline-and-terms alignment."
    },
    "primaryButtonLabel": {
      "description": "Primary button label (action/sendMessage).",
      "type": "string",
      "example": "Draft agenda"
    },
    "primaryButtonMsg": {
      "description": "First-person prompt the primary button sends (action/sendMessage).",
      "type": "string",
      "example": "Draft an agenda for the 9:00 Cobalt contract walkthrough focused on getting the redlined MSA agreed in principle."
    },
    "salesforceUrl": {
      "description": "Event Lightning URL for the secondary \"View in Salesforce\" button (action/openLink).",
      "type": "string",
      "example": "https://org.lightning.force.com/lightning/r/Event/00U000000000000AAA/view"
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
                  "name": "calendar",
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
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{datagridCaption}}",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                {
                  "key": "status",
                  "header": "Status",
                  "type": "badge"
                },
                {
                  "key": "time",
                  "header": "Time",
                  "type": "text"
                },
                {
                  "key": "title",
                  "header": "Meeting",
                  "type": "text"
                },
                {
                  "key": "deal",
                  "header": "Deal",
                  "type": "text"
                },
                {
                  "key": "value",
                  "header": "Value",
                  "type": "currency",
                  "align": "right"
                },
                {
                  "key": "prep",
                  "header": "Prep",
                  "type": "badge"
                }
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
                              "url": "{{salesforceUrl}}"
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

What each block shows, from data you already have:

- **Header** — an icon + page-title text (`{{title}}`, e.g. "Today — Thursday, Jul 24"), with a one-line caption subhead (`{{subtitle}}` = "[N] meetings · [N] deal-linked · [N] external · first at [time], last ends [time]") and a separator.
- **Schedule datagrid** (`{{datagridCaption}}`, `{{datagridRows}}`) — one row per meeting in order. Columns: Time (text), Meeting (text), Deal (text), Value (currency), Prep (badge). Rows carry a leading `status` object (`{value,badgeVariant}` — value Prep now/Draft/Ready/At risk, badgeVariant error/warning/success) for prep state. Non-deal meetings show "—" for deal and a currency cell with `{ value: 0, display: "—" }`.
- **One synthesis callout** (`variant` = `{{calloutVariant}}`, typically "error") — `{{calloutTitle}}` and `{{calloutDescription}}` (the single meeting that needs prep before you walk in, why, and the move). It carries two buttons: a primary with `{{primaryButtonLabel}}` and `{{primaryButtonMsg}}` (`action/sendMessage`), and a secondary "View in Salesforce" with `{{salesforceUrl}}` (`action/openLink`).

**Hydration rules:**
1. Start from the embedded template above — a valid-JSON widget-definition envelope whose leaf values carry `{{token}}` placeholders.
2. Resolve every `{{token}}`. A value that is **only** a `{{token}}` (datagrid `rows`) becomes the resolved **typed** literal — numbers stay numbers, arrays stay arrays. A `{{token}}` **inside** a larger string is interpolated as text.
3. `{{datagridRows}}` is an array of row objects with `time` (text), `title` (text), `deal` (text, "—" for internal), `value` (number, or `{ value: 0, display: "—" }` for internal), `prep` (`{ value, badgeVariant }`), `status` (`{value,badgeVariant}` — value Prep now/Draft/Ready/At risk, badgeVariant error/warning/success).
4. The result is hydrated widget definition (no `{{…}}` placeholders remain). Then call:

```
display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated renderer.json> })
```

**Binding rules:**
- Resolve every `{{token}}` to a literal before calling — numbers stay numbers (`value`), arrays stay arrays.
- Datagrid `value` is a raw number (deal-linked meetings) or `{ value: 0, display: "—" }` (internal meetings). Prep badge `badgeVariant` reflects urgency (error/warning/success/secondary).
- Datagrid rows carry a leading `status` object (`{value,badgeVariant}` — value Prep now/Draft/Ready/At risk, badgeVariant error for needs-prep-now, warning for at-risk, success for ready) —; the leading Status column reads each row's `status`.
- Callout buttons: primary is `action/sendMessage` with a first-person prompt (`{{primaryButtonMsg}}`), secondary is `action/openLink` with `{{salesforceUrl}}` (an Event record URL), opening a new tab.
- Callout `variant` is tokenized (`{{calloutVariant}}`), typically "error" for urgent prep needs.


## 5. Markdown — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

One table per day, times in the resolved local timezone (label `(times in UTC)` if it fell back):

```
# Calendar - [Date Range] (times in [TZ label])

## [Day Name], [Mon DD]
| Time | Event | Location |
|------|-------|----------|
| [Start]–[End] | [Subject] | [Location] |
| All day | [Subject] | — |

**Total events:** [N]
```

Group by day (`##` heading, one table each); all-day rows show `All day`; empty location → `—`; no events → `No events found for [range].`; times `10:00 AM` / `2:30 PM` (12-hour).

## [CUSTOMIZE]

- **Time format:** 12-hour default; switch to 24-hour if preferred.
- **What/Who members:** Step 3 spans `Account`/`Opportunity` (What) and `Contact`/`Lead` (Who) — the common cases. Add another member's inline fragment (e.g. `... on Campaign`) if your org uses it on Event.
