---
name: stakeholder-map
description: Map the people in a deal or account - roles, influence, sentiment, who's missing, and your best access path to the people you haven't reached. Use when the user asks "who are the players at [account]", "who should I talk to at [account]", "stakeholder map", "who's my way in", "am I single-threaded on [deal]", "map the stakeholders", "who's involved", or "who else should I be talking to". This skill creates a DECISION-MAKER MAP with roles and influence.
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

# Stakeholder Map

`account-context` lists contacts; this skill models the deal. Ground → (read + evidence, all in ONE turn) → classify → analyze.

## 1. Ground (hardcoded — Contact only)

Ground **only Contact** — it always exists (naming a missing custom object fails the whole call). Its fields reveal this org's role/sentiment/influence schema; don't assume names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Contact\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

Step 1 is the authority on names — use exact strings from it, never guess. From the result, note: (a) scalar `__c` fields (role, sentiment, influence, seniority, etc.) — take their `{ value }`; (b) any org-specific lookup's exact `relationshipName` to span for a related record's name; (c) any org-specific child `relationshipName` on Contact.

## 2. Read (fill from step 1) — pick ONE template by scope

**Reference-field rules (avoids the retry loop):**
- A scalar/`__c` field → `Field__c { value }`. `displayValue` is null for Id fields here — don't rely on it.
- To get a **related record's name**, span via the exact `relationshipName` from Step 1. Do NOT append `{ ... }` to a raw `Id`/`__c` field.
- Only span relationships Step 1 actually returned. No usable relationshipName → take the `__c { value }` (the Id) and move on — **do not retry**. `ReportsTo` (standard self-lookup) and the `OpportunityContactRoles`/`Contacts` child relationships below are standard — always available, no grounding needed.

Insert `<CONTACT_CUSTOM>` = confirmed scalar `__c { value }` fields; `<REL_BLOCKS>` = one block per confirmed org-specific relationship.

**Deal scope** (`%DEALNAME%` = 1-2 words from the opp name) — one read returns BOTH the deal's contact-role contacts AND the full account roster (`Account.Contacts`), so Step 4 can spot missing roles, single-threading, and who-else-to-talk-to across the whole account, not just the OCR handful:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { Name: { like: \\\"%DEALNAME%\\\" } }, first: 1) { edges { node { Id Name { value } Account { Id Name { value } Contacts(first: 50, orderBy: { Title: { order: ASC } }) { edges { node { Id Name { value } Title { value } Email { value } Phone { value } ReportsTo { Name { value } Title { value } } <CONTACT_CUSTOM> } } } } OpportunityContactRoles { edges { node { Role { value } IsPrimary { value } Contact { Id Name { value } Title { value } Email { value } Phone { value } ReportsTo { Name { value } Title { value } } <CONTACT_CUSTOM> <REL_BLOCKS> } } } } } } } } } }\"}" })
```

**Account scope** (`%ACCOUNTNAME%` = 1-2 words from the account name):

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Name: { like: \\\"%ACCOUNTNAME%\\\" } }, first: 1) { edges { node { Id Name { value } Contacts { edges { node { Id Name { value } Title { value } Email { value } Phone { value } ReportsTo { Name { value } Title { value } } <CONTACT_CUSTOM> <REL_BLOCKS> } } } } } } } } } }\"}" })
```

Empty `edges` → broaden `%DEALNAME%`/`%ACCOUNTNAME%`, or ask the user for the right identifier.

## 2b. Evidence (run IN PARALLEL with step 2 — same turn, issue all at once)

**Issue step 2 and all of step 2b as tool calls in a single turn.** They key on the deal/account name from the request, not on the SF result, so batch them together:
- **email**: per contact, last exchange date and direction (did they reply?)
- **calendar**: who has actually attended meetings
- **docs**: call transcripts — who spoke, what stance they took
- **slack**: colleagues who have their own relationships at this account

Use whatever email/calendar/doc/Slack tools are available; skip silently if none are present (SFDC-only is fine). Cite source + date for anything you use.

## 3. Classify each person (cite every claim; invent nothing)

| Person | Title | Deal role | Engagement | Stance | Evidence |
|---|---|---|---|---|---|
| [name] | [title] | Champion / Economic buyer / Evaluator / Influencer / Blocker / Unknown | Active (met <14d) / Warm / Cold / Never met | 🟢 / 🟡 / 🔴 / ? | [last meeting, email reply, transcript quote] |

Rules: a "champion" must have done something for you (made an intro, shared internal info, pushed a meeting) - advocacy in one call doesn't qualify. Mark "Unknown" honestly rather than guessing stance. Required stakeholders for close and target buyer titles are external knowledge — infer from the org's own data or ask the user once, never invent.

## 4. Find the gaps and the paths

- **Missing roles:** which required stakeholders have no identified person (no economic buyer, no security/legal contact, no exec sponsor)
- **Single-thread risk:** how many people have actually engaged in the last 30 days
- **Access paths to the missing people:** who on the map reports to or works with them (via `ReportsTo`, titles), which colleague has a relationship (from Slack), whether a past champion moved into that org, what a warm intro would look like
- **Dark contacts:** people who attended meetings or appear in email threads but aren't in SFDC at all - list them for creation

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

The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left — this echo path compiles no bindings), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (`xLabels`/`yLabels`/`domain`/`cells`/`rows`) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text. Spirit layout: header + muted one-line subhead, one heatmap (stakeholders by power × support), one stakeholders datagrid, one synthesis callout with two buttons. Cite every value; fabricate nothing — quote a blank field as blank, drop contacts you have no data for. Tokens: `{{title}}` header page-title (e.g. "Stakeholder map — Cobalt Robotics"); `{{subtitle}}` muted caption summarizing the map (8 contacts · 2 champions, 1 detractor · buyer engaged); `{{heatmapCaption}}` heatmap caption; `{{xLabels}}`/`{{yLabels}}` heatmap axes (x ["Detractor","Neutral","Supporter"], y ["High power","Mid power","Low power"]); `{{cells}}` array of `{ x, y, value, valueLabel }`, one per occupied cell (diverging scale, midpoint 0) — **`valueLabel` = abbreviated title or role for a single occupant (e.g. "CEO", "CIO", "Dir Ops", "CFO+VP" when two people share a cell). For cells with 3+ people use a count label ("3 users"). Heatmap is for spatial scan (where are supporters/detractors/gaps?), datagrid below has full names/roles/detail.**; `{{domain}}` 2-element `[min, max]` for that scale (e.g. [-2, 2]); `{{datagridCaption}}` datagrid caption; `{{rows}}` array of stakeholder objects — `name` (plain string — format as the person's display name (e.g. "Dana Kwon"); names must be plain strings, not objects: use `Contact.Name.value` from the SF response), `role` (text), `stance` `{ value, badgeVariant }` (success Champion, error Detractor, secondary Neutral, info Supporter), `last` (ISO `YYYY-MM-DD`), `next` (text), `_tone` (success/error/warning/info/default), `_status` (Mobilized/Risk/Uncovered/Covered — drives the auto Status column); `{{calloutTitle}}`/`{{calloutDescription}}` synthesis callout (variant error); `{{ctaPrimaryLabel}}`/`{{ctaPrimaryMsg}}` primary button (`action/sendMessage`, first-person prompt e.g. "Draft an exec-to-exec meeting invite for…"); `{{salesforceUrl}}` secondary "View in Salesforce" button (`action/openLink`, the account's Lightning URL `https://<myDomain>/lightning/r/Account/<Id>/view` — omit this button if you lack the Id). Verify before calling: no `{{…}}`/`{!…}` remain; arrays are arrays and numbers numbers; every row cites real data.

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
                  { "definition": "tile/text", "attributes": { "text": "{{title}}", "variant": "page-title" } }
                ]
              }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/heatmap",
            "attributes": {
              "layout": "matrix",
              "caption": "{{heatmapCaption}}",
              "xLabels": "{{xLabels}}",
              "yLabels": "{{yLabels}}",
              "encode": "color",
              "scale": "diverging",
              "midpoint": 0,
              "valueFormat": "number",
              "domain": "{{domain}}",
              "cells": "{{cells}}"
            }
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{datagridCaption}}",
              "appearance": "striped",
              "columns": [
                { "key": "name", "header": "Stakeholder", "type": "avatar" },
                { "key": "role", "header": "Role", "type": "text" },
                { "key": "stance", "header": "Stance", "type": "badge" },
                { "key": "last", "header": "Last touch", "type": "date" },
                { "key": "next", "header": "Next move", "type": "text" }
              ],
              "rows": "{{rows}}"
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
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{salesforceUrl}}" } }
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
## 6. Output — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Stakeholder Map: [Opp / Account]

## The map
[classification table from Step 3]

## Coverage verdict
[e.g. "Engaged with 2 of 5 required roles. Economic buyer identified but never met. Single-threaded through [name]."]

## Missing people and how to reach them
1. [Role we're missing] - likely [name/title if known] - path: [warm intro via X / champion ask / direct outreach angle]
2. ...

## Not in SFDC yet
- [Name, title, where they appeared] - offer to create as Contacts: show exactly what will be saved (name, title, email, account), write only after an explicit yes, link the created records. On a read-only connector, list them for manual add.

## This week
- [The single highest-leverage relationship action]
```
