---
name: query-activity-history
description: Required when displaying activity history (tasks, events, calls, emails) visually for Account, Contact, Lead, or Opportunity records. Use whenever the user asks for "activity history", "recent activity", "what's happening on [record]", "summarize activity for [account/contact/lead/opp]", or wants to see a timeline of interactions. Returns activity in either an interactive HTML timeline widget (Cowork/desktop/web) or clean markdown table (Claude Code).
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

If `display_widget` is available (Cowork/desktop/web), the widget IS the output — call it immediately. Produce the markdown below only if `display_widget` is unavailable (e.g. a terminal); don't also dump it when the widget renders. The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (`heatmapDomain`, `heatmapDays`, `datagridRows`, `datagridTotalRows`) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text.

Tokens: `pageTitle` (e.g. "Activity history — <RecordName>") · `pageSubtitle` (one line: window · N touches · last contact) · **calendar heatmap** `heatmapCaption`, `heatmapDomain` (2-element `[min,max]` number array, e.g. `[0,4]`), `heatmapDays` (array of `{date: "YYYY-MM-DD", value: number}` — one per day, touch cadence over the last ~12 weeks) · **datagrid** `datagridCaption`, `datagridTotalRows` (number = `ActivityHistories.totalSize`), `datagridRows` (array of the most recent ~5: `{date: "YYYY-MM-DD", type: {value, badgeVariant}, who, note}` — `type.value` is `ActivitySubtype` (Call/Email/Task/Event/Meeting), `who` is `Who.Name` or "—", `note` is `Subject`) · **callout** `calloutVariant` (info), `calloutTitle`/`calloutDescription` (the engagement read + the gap), `primaryButtonLabel`/`primaryButtonMsg` (`action/sendMessage`, first-person next-step prompt), `viewRecordUrl` (the record's Lightning URL for "View in Salesforce").

Every token is backed by the Step 3 subquery: `ActivityDate` drives both the heatmap day buckets and each datagrid `date`; `ActivitySubtype` → the type badge; `Subject` → `note`; `Who.Name` → `who`; `ActivityHistories.totalSize` → `datagridTotalRows`. The heatmap domain, cadence buckets, and the synthesis callout are computed in-prompt from those rows. `viewRecordUrl` is `https://<myDomain>/lightning/r/<ObjectName>/<recordId>/view`. `TotalCount = 0` → skip the widget and render only the empty-state markdown below. Never fabricate activities.

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
                  { "definition": "tile/icon", "attributes": { "name": "activity", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{pageTitle}}", "variant": "page-title" } }
                ]
              }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{pageSubtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "lg", "align": "start", "isWrapped": false },
            "children": [
              {
                "definition": "tile/heatmap",
                "attributes": {
                  "width": "md",
                  "layout": "calendar",
                  "caption": "{{heatmapCaption}}",
                  "encode": "color",
                  "scale": "sequential",
                  "valueFormat": "number",
                  "domain": "{{heatmapDomain}}",
                  "days": "{{heatmapDays}}"
                }
              },
              {
                "definition": "tile/callout",
                "attributes": {
                  "width": "stretch",
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
                          "onClick": { "definition": "action/openLink", "attributes": { "url": "{{viewRecordUrl}}" } }
                        }
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
                { "key": "date", "header": "Date", "type": "date" },
                { "key": "type", "header": "Type", "type": "badge" },
                { "key": "who", "header": "With", "type": "text" },
                { "key": "note", "header": "Summary", "type": "text" }
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



> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.
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
