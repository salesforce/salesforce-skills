---
name: customer-health
description: Health check on a customer account and QBR-ready prep - relationship strength, engagement trend, risk signals, value delivered, and the agenda that makes the review worth their time. Use when the user asks "how healthy is [account]", "customer health check", "prep the [account] QBR", "prepare QBR", "business review prep", "quarterly business review", or "are we at risk with [customer]". IMPORTANT: This is for CUSTOMER HEALTH and QBR prep, NOT for prepping calls with prospects - that's call-prep.
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

- Resolve to ONE account before the deep read. When the name is ambiguous, ask the user to pick — don't probe candidates or guess.

# Customer Health

Two jobs, one data pass: the ongoing "are we okay here?" check, and the quarterly business review that proves value and sets up the next phase. Ground → (read + evidence, ONE turn) → score → output.

## Inputs

- **Account:** name or SFDC ID
- **Mode:** health check (default) or QBR prep
- **Period:** last quarter (default) for trend math

## 1. Ground (hardcoded — Account only)

Ground **only Account** — it always exists (naming a missing object fails the whole call). Its fields reveal this org's health/adoption/renewal/NPS `__c` schema; don't assume names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Account\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

Step 1 is the authority on names — use exact strings, never guess. Note scalar `__c` fields worth surfacing (health score, adoption/seat usage, renewal date, ARR, NPS, tier) — these are the same fields a health check might later offer to update, so ground them once and reuse. Standard fields, the `Owner`/`Opportunities`/`Cases` spans, and `LastActivityDate` are reliable across orgs; an org that doesn't use Cases just returns empty `edges`, not an error.

## 2. Read (fill from step 1)

`%ACCOUNT%` = the user's match (1–2 words); swap for `Id: { eq: \"...\" }` when an SFDC Id was given instead of a name. One call pulls the account plus its open-renewal-relevant opportunities and recent cases — no separate dispatch per object.

**Reference-field rule (avoids the retry loop):** a scalar/`__c` field → `Field__c { value }` (`{ value displayValue }` for currency/picklist). A related record's name → span the exact `relationshipName` from step 1 (`Owner { Name { value } }`); never append `{ … }` to a raw `Id`/`__c` field. Insert `<ACCT_CUSTOM>` = confirmed Account `__c { value }` fields.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Name: { like: \\\"%ACCOUNT%\\\" } }, first: 1) { edges { node { Id Name { value } Type { value } Industry { value } AnnualRevenue { value displayValue } LastActivityDate { value } CreatedDate { value } <ACCT_CUSTOM> Owner { Name { value } } Opportunities(first: 20, orderBy: { CloseDate: { order: DESC } }) { edges { node { Id Name { value } Type { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } IsWon { value } } } } Cases(first: 10, where: { CreatedDate: { gte: { literal: LAST_90_DAYS } } }, orderBy: { CreatedDate: { order: DESC } }) { edges { node { CaseNumber { value } Subject { value } Status { value } Priority { value } CreatedDate { value } } } } Tasks(first: 20, where: { ActivityDate: { gte: { literal: LAST_90_DAYS } } }, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Subject { value } ActivityDate { value } Type { value } } } } } } } } } }\"}" })
```

Empty `edges` on `Account` → broaden `%ACCOUNT%`, or ask the user for the right account. Empty `edges` on `Cases`/`Tasks` just means none in the window — don't retry, don't treat as an error. The `Tasks` child (last 90d) is the in-CRM activity cadence behind the Engagement-trend dimension (and the widget engagement chart) — read it even when no external calendar/email connector is present.

## 2b. Evidence (run IN PARALLEL with step 2 — same turn, issue all at once)

**Issue step 2 and all of step 2b as tool calls in a single turn — do not wait for the SF read to return before firing the searches.** They're independent (searches key on the account name from the request, not the SF result), so batch them together:
- **email**: threads with this account's contacts, last ~90d → cadence vs prior period, most recent exchange + topic
- **calendar**: meeting count/attendees last ~90d vs prior period — is the champion/exec still showing up
- **docs**: success plan, past QBR decks, recent notes → documented outcomes, open commitments
- **slack**: internal mentions → deal-desk/exec concerns, escalations

Use whatever email/calendar/doc/Slack tools are available; skip silently if none are present (SFDC-only is fine). Be explicit about what this skill can't see: product usage, support-ticket detail, and NPS only count if synced into a CRM field or a connected doc — otherwise mark that dimension "not visible from CRM" rather than guessing. Cite source + date for anything you use.

## 3. Score the health (cite every value; invent nothing)

| Dimension | Signal | Status |
|---|---|---|
| Relationship | champion/exec engagement (evidence), breadth of contacts active | 🟢🟡🔴 |
| Engagement trend | in-CRM `Tasks` cadence (step 2, last 90d) + meeting/email cadence (evidence) vs prior period | |
| Commercial | renewal proximity (open renewal opp `CloseDate`), open expansion, payment/contract issues | |
| Support | open Cases, aging/priority from step 2 | |
| Value delivery | documented outcomes vs the success plan (docs), if one exists | |

Overall verdict with the one or two dimensions driving it.

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

- [ ] No prose written before or after this call — no input narration, no transition text, no summary (only applies when display_widget is available; if unavailable, produce the text fallback section below).
- [ ] I am producing zero prose before or after this call. If I am tempted to summarize findings, I must not.

The widget template is embedded below — a widget-definition envelope whose leaf values carry {{token}} placeholders. Resolve every {{token}} to a literal (no {{…}}/{!…} left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a {{token}} becomes the typed literal — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string is interpolated as text.

Tokens: `headerTitle headerStatus` (header — account name; `headerStatus` is a plain string badge label e.g. "AT RISK" / "HEALTHY" / "NEEDS ATTENTION" — not a variant, the renderer maps the label to a variant automatically) `headerSubtitle` (subtitle with ARR · renewal days · health score+trend) · `chartCaption chartCategories chartSeries` (line chart — weekly engagement/usage trend over 6 weeks from evidence; omit the chart entirely if no cadence signal was gathered) · `meterValue meterTarget meterValueLabel meterTargetLabel meterStatus meterBands` (composite health meter 0–100, bands array with from/to/variant/label covering the full range) · `gridCaption gridRows` (health signals datagrid — `gridRows` is an array, one per Step 3 dimension: `{signal, now (plain string — always a formatted string, never a raw number; use context-appropriate formatting e.g. "322", "18 open", "0 / 90d", "5 of 12"), trend(number[6]), note, _tone(error/warning on 🔴/🟡), _status (plain string e.g. "Declining", "Rising", "Cold", "Stalled", "Softening")}`; renderer auto-injects Status column from `_status`) · `calloutTitle calloutDescription ctaPrimaryLabel ctaPrimaryMsg accountUrl` (synthesis callout with two buttons — primary is action/sendMessage with first-person prompt, secondary is action/openLink to the account Lightning URL). Omit any block whose data you lack rather than passing empty arrays.

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
                  { "definition": "tile/text", "attributes": { "text": "{{headerTitle}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{headerStatus}}", "variant": "error" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{headerSubtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "lg", "align": "stretch", "isWrapped": true },
            "children": [
              {
                "definition": "tile/chart",
                "attributes": {
                  "chartType": "line",
                  "caption": "{{chartCaption}}",
                  "categories": "{{chartCategories}}",
                  "series": "{{chartSeries}}",
                  "valueFormat": "number",
                  "showValues": false,
                  "showLegend": false
                }
              },
              {
                "definition": "tile/meter",
                "attributes": {
                  "label": "Composite health",
                  "value": "{{meterValue}}",
                  "min": 0,
                  "max": 100,
                  "target": "{{meterTarget}}",
                  "valueFormat": "number",
                  "valueLabel": "{{meterValueLabel}}",
                  "targetLabel": "{{meterTargetLabel}}",
                  "status": "{{meterStatus}}",
                  "size": "lg",
                  "bands": "{{meterBands}}"
                }
              }
            ]
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{gridCaption}}",
              "appearance": "striped",
              "columns": [
                { "key": "signal", "header": "Signal", "type": "text" },
                { "key": "now", "header": "Current", "type": "text", "align": "right" },
                { "key": "trend", "header": "6-wk trend", "type": "sparkline" },
                { "key": "note", "header": "Read", "type": "text" }
              ],
              "rows": "{{gridRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "error",
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
                      "label": "View in Salesforce",
                      "variant": "secondary",
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{accountUrl}}" } }
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

**Health check mode:**
```
# Health: <Account> — 🟢/🟡/🔴
<verdict sentence>
<dimension table with evidence>
## Watch items
- <specific signal, why it matters, suggested action>
## Suggested SFDC updates
- <health/status fields, if grounded> - these live on the Account record: show before/after and confirm before writing, or output as a checklist on a read-only connector
```

**QBR prep mode:** add the meeting kit —
1. **Value delivered** — outcomes since last review, in their metrics, with sources
2. **Adoption story** — what's working, what's underused (only CRM/document-visible facts)
3. **Open items** — Cases resolved/open, commitments from last QBR and their status
4. **Next phase** — the expansion plays (`expansion-whitespace`) and renewal framing (`renewal-radar`) worth raising
5. **Agenda + attendees** — who should be in the room from the stakeholder map, and the asks for their execs
Offer the agenda as a doc and the meeting via `schedule-meeting`.
