---
name: renewal-radar
description: Upcoming renewals with timing, risk, and uplift potential - and the renewal opportunity records to keep them honest. Use when the user asks "what renewals are coming up", "renewal radar", "is [account] going to renew", "prep the [account] renewal", or "which renewals are at risk".
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

- **Empty owned book → fail fast, then ask which scope.** If the my-book read (the `OwnerId` filter) returns zero renewals, **do not** drop the owner filter and go org-wide on your own. Stop, tell the user plainly that their own book came back empty, and ask which scope they want instead (org-wide, a named rep, or a named account) before re-running, then wait. Never invent records, and never silently widen to org-wide.

# Renewal Radar

The renewal you start 90 days out is a process; the one you notice 2 weeks out is a discount. Keep the renewal calendar visible, flag the risky ones early, prep each renewal motion.

**Inputs:** my book (default), named rep, named account, or the team. Window: next N days (default 120), or specific quarter (Q1/Q2/Q3/Q4 FY26 → compute start/end dates).

## 1. Resolve scope (if named rep)

- **"my renewals"** (default) → skip to step 2, use currentUserId for OwnerId filter
- **"[Rep]'s renewals"** → resolve one User. Shared/demo orgs collide (one name → base user + regional variants like `(AM)`/`(BK)`). Pull enough to disambiguate:
  ```
  dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
    queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { User(where: { Name: { like: \\\"%REP%\\\" } }, first: 10) { edges { node { Id Name { value } Email { value } IsActive { value } } } } } } }\"}" })
  ```
  **One match** → take its Id for OwnerId filter in step 3. **Several** → list them (Name · Email · active? · Id) and ask user to pick. **Zero** → ask user to clarify.
- **Named account** → resolve Account by name, use AccountId filter in step 3
- **Team** (default) → no owner filter

## 2. Ground (hardcoded — Opportunity only)

Ground **only Opportunity** — it always exists. Its fields + childRelationships reveal this org's opp/account schema.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

From the result: (a) scalar `__c` fields (ARR, renewal type, usage signals, auto-renew flags) — take their `{ value }`; (b) each lookup field's exact `relationshipName` to span for a related record's Name; (c) each child `relationshipName`.

## 3. Pull renewal calendar (SOQL — fill from step 2)

Insert `<OPP_CUSTOM>` = confirmed scalar `__c` fields (comma-separated, e.g. `ARR__c, AutoRenew__c`) from Step 2. **Nest Account.Name and Owner.Name in one query.**

**Date filter:** user can specify window as "next N days" (default 120) or "Q1 FY26" / "Q2 FY26" etc.
- **"next N days"** → use `NEXT_N_DAYS:120`
- **"Q1 FY26"** → compute quarter ISO dates, use `CloseDate >= 2026-02-01 AND CloseDate <= 2026-04-30`

**Primary query (SOQL `LIKE` pattern — catches both Type picklist values and Name patterns):**

```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT Id, Name, Type, Amount, CloseDate, StageName, NextStep, LastActivityDate, Account.Name, Account.Industry, Account.Type, Owner.Name<OPP_CUSTOM> FROM Opportunity WHERE IsClosed = false AND CloseDate = NEXT_N_DAYS:120 AND (Type LIKE '%renew%' OR Name LIKE '%renew%') ORDER BY CloseDate LIMIT 50" })
```

Replace `NEXT_N_DAYS:120` with the computed date filter. Insert `<OPP_CUSTOM>` as `, ARR__c, AutoRenew__c` (comma-prefixed) if custom fields exist, or omit if none.

**Scope filters:**
- **My book** (default): add `AND OwnerId = '<currentUserId>'` (resolve currentUserId first via `/services/data/v63.0/query?q=SELECT Id FROM User WHERE Id = '<running-user-id>'` or use GraphQL `scope: MINE` equivalent)
- **Named rep**: add `AND OwnerId = '<resolvedUserId>'` (from step 1)
- **Named account**: add `AND AccountId = '<accountId>'`
- **Team**: omit owner filter

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

The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left — this echo path does no expression compilation), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (meter `value`/`bands`, piechart `slices`, datagrid `rows`) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text.

Blocks, all from data already fetched: header icon + `{{pageTitle}}` title + `{{headerStatus}}` warning badge, then `{{subtitle}}` caption; a meter ("At-risk ARR share": `{{riskValue}}` vs `{{riskTarget}}` over a fixed 0–100 range, with `{{riskValueLabel}}`/`{{riskTargetLabel}}`/`{{riskStatus}}`/`{{riskBands}}`) and a donut piechart ("Renewal ARR by risk verdict": `{{pieCenter}}` center, `{{pieSlices}}`) in a wrapped row; a renewals datagrid (`{{gridRows}}`, count `{{totalRenewals}}`) with columns Account, ARR (currency), Renews (date), Usage trend (sparkline), Verdict (badge), Play; one error callout (`{{synthTitle}}`/`{{synthDescription}}`) with a primary sendMessage button (`{{primaryLabel}}`/`{{primaryPrompt}}`) and a secondary openLink button ("View in Salesforce", `{{criticalRenewalsUrl}}`).

Binding:
- Numbers stay numbers (`{{riskValue}}`, `{{riskTarget}}`, each row's `arr`, `usage` arrays); arrays stay arrays (`{{riskBands}}`, `{{pieSlices}}`, `{{gridRows}}`).
- `{{riskBands}}`: array of `{ from, to, variant, label }` covering 0→100 in order — success (0–15 Healthy), warning (15–30 Elevated), error (30–100 High).
- `{{pieSlices}}`: array of `{ label, value, role? }`, one per verdict; mark the at-risk segment `"role": "highlight"`. `{{pieCenter}}` is total renewal ARR as a formatted currency string (e.g. "$4.7M"), not a raw number.
- `{{gridRows}}`: array of `{ account (plain string — format as the account name (e.g. "Cobalt Robotics"); names must be plain strings, not objects: use `Account.Name.value` from the SF GraphQL response or `Account.Name` from SOQL), arr (number), close (ISO YYYY-MM-DD), usage (number[]), verdict ({ value, badgeVariant }), action, _tone (error|warning), _status (Critical|At risk) }`. Verdict badge: error=Critical, warning=At risk, success=On track. Risky rows carry `_tone`+`_status`; healthy rows omit both. Rank Critical first, then by close date. `{{totalRenewals}}` = row count.
- Callout: `{{primaryPrompt}}` is first-person (e.g. "Draft an executive save plan for…"); `{{criticalRenewalsUrl}}` = `https://<myDomain>/lightning/o/Opportunity/list?filterName=Critical_Renewals`, or the account record URL for a single renewal.

Verify before calling: no `{{…}}`/`{!…}` remain; exactly 2 graphs (meter + piechart); datagrid `arr`/`usage` are numbers/arrays, `close` is ISO, risky rows carry `_tone`+`_status` and healthy rows omit both; callout has 2 real buttons (sendMessage, openLink); section 6 text is produced only when `display_widget` is unavailable.

Tokens: `{{pageTitle}}` (e.g. "Renewal radar — next 90 days"), `{{headerStatus}}` (e.g. "$1.4M AT RISK"), `{{subtitle}}` (window summary); meter `{{riskValue}}`/`{{riskTarget}}`/`{{riskValueLabel}}`/`{{riskTargetLabel}}`/`{{riskStatus}}`/`{{riskBands}}`; piechart `{{pieCenter}}` (formatted currency string e.g. "$4.7M")/`{{pieSlices}}`; datagrid `{{gridRows}}`/`{{totalRenewals}}`; callout `{{synthTitle}}`/`{{synthDescription}}`/`{{primaryLabel}}`/`{{primaryPrompt}}`/`{{criticalRenewalsUrl}}`.

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
                  { "definition": "tile/icon", "attributes": { "name": "refresh", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{pageTitle}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{headerStatus}}", "variant": "warning" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "lg", "align": "stretch", "isWrapped": true },
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
              },
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
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Renewals in the next 90 days, soonest and riskiest first",
              "appearance": "striped",
              "defaultSort": { "key": "close", "direction": "asc" },
              "columns": [
                { "key": "account", "header": "Account", "type": "text" },
                { "key": "arr", "header": "ARR", "type": "currency", "align": "right", "sortable": true },
                { "key": "close", "header": "Renews", "type": "date", "sortable": true },
                { "key": "usage", "header": "Usage trend", "type": "sparkline" },
                { "key": "verdict", "header": "Verdict", "type": "badge" },
                { "key": "action", "header": "Play", "type": "text" }
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
                "attributes": { "gap": "sm", "align": "center", "isWrapped": true },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{primaryLabel}}",
                      "variant": "primary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{primaryPrompt}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "View in Salesforce",
                      "variant": "secondary",
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{criticalRenewalsUrl}}" } }
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
