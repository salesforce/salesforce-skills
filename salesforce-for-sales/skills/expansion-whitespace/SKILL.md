---
name: expansion-whitespace
description: Find the expansion whitespace in an account or a book - what they own vs. what they could own, the evidence for each play, and the open opps to create. Use when the user asks "what's the whitespace at [account]", "where can I expand [account]", "upsell opportunities in my book", or "which customers should I be growing".
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

Tokens: `title` (account name in heading) · `subtitle` (one-line ARR summary) · `heatmapCaption heatmapXLabels heatmapYLabels` (product adoption matrix: X=products from won Opps, Y=business units from ChildAccounts or Contact departments) · `heatmapDomain` (array `[0, maxValue]`) · `heatmapCells` (array, one per owned product×BU combo: `{x, y, value, valueLabel}` — omit whitespace combos so they render dashed/empty) · `piechartCaption piechartCenterLabel piechartCenterValue piechartSlices` (live ARR breakdown: array of `{label, value, role?}`, with `role:"highlight"` on largest slice) · `datagridCaption datagridRows` (expansion plays: array of `{play, unit, fit, arr, motion:{value,badgeVariant}, _tone?, _status?}`) · `calloutTitle calloutDescription` (top play synthesis) · `primaryButtonLabel primaryButtonContent` (draft-plan button + sendMessage prompt) · `accountUrl` (Lightning URL `https://<myDomain>/lightning/r/Account/<Id>/view`).

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
            "definition": "tile/row",
            "attributes": { "gap": "lg", "align": "stretch", "isWrapped": false },
            "children": [
              {
                "definition": "tile/heatmap",
                "attributes": {
                  "width": "lg",
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
              },
              {
                "definition": "tile/piechart",
                "attributes": {
                  "width": "stretch",
                  "caption": "{{piechartCaption}}",
                  "variant": "donut",
                  "valueFormat": "currency",
                  "centerLabel": "{{piechartCenterLabel}}",
                  "centerValue": "{{piechartCenterValue}}",
                  "slices": "{{piechartSlices}}"
                }
              }
            ]
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{datagridCaption}}",
              "appearance": "striped",
              "defaultSort": { "key": "arr", "direction": "desc" },
              "columns": [
                { "key": "play", "header": "Play", "type": "text" },
                { "key": "unit", "header": "Business unit", "type": "text" },
                { "key": "fit", "header": "Fit", "type": "number", "align": "right" },
                { "key": "arr", "header": "ARR", "type": "currency", "align": "right", "sortable": true },
                { "key": "motion", "header": "Next step", "type": "badge" }
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
                "attributes": { "gap": "sm", "align": "center", "isWrapped": true },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{primaryButtonLabel}}",
                      "variant": "primary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{primaryButtonContent}}" } }
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

Self-verification before calling:
- [ ] Every `{{token}}` replaced with a resolved literal — no `{{…}}` left.
- [ ] Numeric attributes (heatmap cell `value`/`domain`, `datagrid` `arr`/`fit`, piechart slice `value`) are numbers, not strings.
- [ ] Heatmap has a cell only for owned combos (whitespace omitted → dashed/empty); axis labels short; `heatmapDomain` = `[0, largestCellValue]`.
- [ ] `datagrid` plays with warm access or ready motion carry both `_tone` and a `_status`; speculative plays carry neither.
- [ ] Donut slices sum to the `centerValue` live ARR; zero-ARR products dropped; largest slice `highlight`ed.



> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.
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
