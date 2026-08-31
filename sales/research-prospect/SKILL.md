---
name: research-prospect
description: Research a target company and optionally a specific contact - company overview, recent news, likely priorities, and fit against your ICP. Cross-references existing Salesforce records. Use when the user asks to "research [company]", "look into [company]", "prospect research on [company]", or "who is [person] at [company]". IMPORTANT: This is for NEW/PROSPECT companies you don't yet work with. If the user asks "tell me about [existing account]" or wants a 360 view of an EXISTING customer, use account-context instead.
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


# Research Prospect

Ground Account → CRM read + web research (ONE turn) → score fit → output. Grounding surfaces this org's custom ICP fields (tier/segment/territory) — fit scoring reads them, so don't skip it.

## 1. Inputs

- **Company name or domain** (required)
- **Contact name or title** (optional)

ICP (industries, size, titles, disqualifiers), value prop, competitors, differentiators are external knowledge — infer from org data or confirm with the user once. Never invent.

## 2. Ground Account (this turn), then CRM read + web research (ONE turn)

**Ground Account first** — its `__c` fields are this org's ICP schema (tier, segment, territory, employee band, etc.), and Step 3 scores fit against them. Account always exists, so this one call never fails on a missing object:
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
         queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Account\\\"]) { fields { ApiName label dataType } } } }\"}" })
```
Request only `fields { ApiName label dataType }` — no `childRelationships` or `relationshipName` (this skill's children/parents are hardcoded below, so those just bloat the payload into overflow). From the result, note the scalar `__c` fields whose label carries ICP/segment/tier/territory/employee-band signal — add each as `Field__c { value }` to `<ACCOUNT_CUSTOM>` in the read below.

**Just scan the result by eye — do not script the extraction** (no `cat` / `python3` / `jq` / `grep` over the response). The Account catalog is large and may not come back inline: if the host wrote it to a temp file, open that file with the **Read tool only** — its path is outside the shell sandbox, so `cat` / `ls` fail on it. If the Read fails or the payload is unwieldy, skip grounding and use the standard fields below only — don't retry.

**CRM read + web search — fire BOTH as tool calls in ONE turn (independent).**

**Salesforce** — read the matching Account over GraphQL (Account is UI-API-serviceable; no SOQL needed). Insert `<ACCOUNT_CUSTOM>` = the confirmed scalar `__c { value }` fields from grounding.

Match on **`Name` first**. Do **not** combine Name and Website with `or` — a two-clause `or` in a UI-API `where` 500s on this endpoint. Only if the name search returns no rows, run the Website-only fallback below.
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
         queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Name: { like: \\\"%COMPANY%\\\" } }, first: 5) { edges { node { Id Name { value } Website { value } Industry { value displayValue } NumberOfEmployees { value } Type { value displayValue } <ACCOUNT_CUSTOM> Owner { Name { value } } Opportunities(where: { IsClosed: { eq: false } }, first: 10) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } } } } Contacts(first: 10) { edges { node { Id Name { value } Title { value } Email { value } } } } } } } } } }\"}" })
```
- **Found** → note owner, open opps, known contacts. Output must say "already in CRM, owned by [Name]" prominently so the user doesn't step on a colleague.
- **No rows** → run the **Website-only fallback** (a `%DOMAIN%` match), still no `or`:
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
         queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Website: { like: \\\"%DOMAIN%\\\" } }, first: 5) { edges { node { Id Name { value } Website { value } Industry { value displayValue } NumberOfEmployees { value } Type { value displayValue } <ACCOUNT_CUSTOM> Owner { Name { value } } Opportunities(where: { IsClosed: { eq: false } }, first: 10) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } } } } Contacts(first: 10) { edges { node { Id Name { value } Title { value } Email { value } } } } } } } } } }\"}" })
```
- **Still no match** → "net new - no CRM record". Broaden `%…%` once if a partial name seems likely; don't retry the same shape.

**Web search** (same turn, independent of the SFDC result):
- Company basics: what they do, HQ, size, funding stage, leadership
- Recent signals (last 6 months): funding rounds, exec hires, product launches, layoffs, earnings, expansion
- Tech/operating context relevant to your product category
- Likely priorities, inferred from the signals (e.g. just raised → hiring + scaling; new CRO → pipeline overhaul)
- If a contact was specified: their role, tenure, prior companies, public talks/posts, and what they likely care about

## 3. ICP fit scoring

| Dimension | Fit | Evidence |
|---|---|---|
| Industry | ✅ / ⚠️ / ❌ | [from research] |
| Company size | ✅ / ⚠️ / ❌ | [employee count vs ICP range] |
| Buyer persona present | ✅ / ⚠️ / ❌ | [title found / inferred] |
| Disqualifiers | ✅ none / ❌ [which] | |
| Timing signal | ✅ / ⚠️ / ❌ | [recent trigger event or none] |

Overall: **Strong fit / Moderate fit / Poor fit** with one-sentence rationale.

## 4. Relevance hooks

2-3 specific, sourced hooks for outreach — things from the research that connect to your value prop. Not generic ("they're growing") but specific ("they posted 12 [relevant role] openings last month and their [exec title] spoke about [relevant pain] at [conf]").

## 5. Prospect brief widget (editorial layout)

When the `display_widget` tool is available (Claude Cowork, the desktop app, the web app), render the prospect brief as a visual widget instead of the section 6 text. When `display_widget` is unavailable (e.g. a terminal) the section 6 markdown is the whole output, so produce it only then.

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

- [ ] Every `{{token}}` placeholder replaced with a resolved literal — no `{{…}}` left, no `{!…}` expressions in the widget definition.
- [ ] Numeric attributes (meter `value`/`max`/`target`, meter band `from`/`to`) are numbers, not strings.
- [ ] The meter is in numeric units (value/target as raw scores 0-100), bands span `[0, 100]`, and `valueLabel`/`status` carry the score and fit read.
- [ ] Every `datagrid` signal row carries `_tone` + `_status`; `tag` is a badge object.
- [ ] The `tile/callout` carries a resolved `title`/`description` (the approach + the timing), not empty and not a recap.
- [ ] No fabricated content — blank fields omitted or quoted blank, not invented.
- [ ] The section 6 markdown is produced only when `display_widget` is unavailable (the terminal fallback) — not alongside a rendered widget.
- [ ] No prose written before or after this call — no input narration, no transition text, no summary (only applies when display_widget is available; if unavailable, produce the text fallback section below).
- [ ] I am producing zero prose before or after this call. If I am tempted to summarize findings, I must not.

The widget template is embedded below. Call `display_widget` in **dynamic** mode with it. It is a skeleton: replace every `{{token}}` with a fully-resolved literal computed from the data you researched and scored — this echo path does no expression compilation, so no `{!…}` bindings. See `sample-data.json` in this dir for a fully-worked example of every token.

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
                  { "definition": "tile/icon", "attributes": { "name": "search", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{prospectTitle}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{fitStatus}}", "variant": "success" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{prospectSubtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/meter",
            "attributes": {
              "label": "ICP fit",
              "value": "{{icpValue}}",
              "min": 0,
              "max": 100,
              "target": "{{icpTarget}}",
              "valueFormat": "number",
              "valueLabel": "{{icpValueLabel}}",
              "targetLabel": "{{icpTargetLabel}}",
              "status": "{{icpStatus}}",
              "bands": "{{icpBands}}"
            }
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "What we know — signals and openings",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                { "key": "topic", "header": "Signal", "type": "text" },
                { "key": "tag", "header": "Read", "type": "badge" },
                { "key": "note", "header": "Detail", "type": "text" }
              ],
              "rows": "{{signalRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "recommended",
              "title": "{{synthTitle}}",
              "description": "{{synthDetail}}"
            },
            "children": [
              {
                "definition": "tile/row",
                "attributes": { "gap": "sm", "align": "center", "isWrapped": true },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{ctaLabel}}",
                      "variant": "primary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{ctaMsg}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "View in Salesforce",
                      "variant": "secondary",
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{prospectUrl}}" } }
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

What each block shows, from data you already gathered:

- **Header** — an icon (search) + page-title text (`{{prospectTitle}}`, the prospect brief title) + a status badge (`{{fitStatus}}`, e.g. "STRONG FIT", variant by ICP verdict), with a one-line caption subhead (`{{prospectSubtitle}}`) summarizing firmographics (industry/employees/revenue/fit), and a separator.
- **One meter** — "ICP fit": `{{icpValue}}` against `{{icpTarget}}` (max 100), `valueFormat:"number"`, with `{{icpValueLabel}}`, `{{icpTargetLabel}}`, `{{icpStatus}}`, and `{{icpBands}}` (Weak/Fair/Strong). This is the single chart.
- **Signals and openings datagrid** (`{{signalRows}}`) — one row per signal. Columns: Signal (text), Read (badge), Detail (text). Every row carries `_tone` (success/info/warning) and `_status` (Buy/Fit/Watch); the renderer auto-injects a leading Status column from `_status`.
- **One synthesis callout** (`variant:"recommended"`) — `{{synthTitle}}` (the prospect's single most important read) and `{{synthDetail}}`. It carries two real buttons: a primary prompt button (`{{ctaLabel}}` / `{{ctaMsg}}`, `action/sendMessage`) and a secondary "View in Salesforce" (`{{prospectUrl}}`, `action/openLink`).

**Hydration rules:**
1. Start from the embedded template above — a valid-JSON widget-definition envelope whose leaf values carry `{{token}}` placeholders.
2. Resolve every `{{token}}`. A value that is **only** a `{{token}}` (meter `value`/`bands`, datagrid `rows`) becomes the resolved **typed** literal — numbers stay numbers, arrays stay arrays. A `{{token}}` **inside** a larger string is interpolated as text.
3. `{{signalRows}}` is an array of signal objects — each with `topic` (signal name), `tag` (`{ value, badgeVariant }`), `note` (detail text), `_tone` (success/info/warning), and `_status` (Buy/Fit/Watch).
4. The result is hydrated widget definition (no `{{…}}` placeholders remain). Then call:

```
display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated renderer.json> })
```

**Binding rules:**
- Resolve every `{{token}}` to a literal before calling — numbers stay numbers (`{{icpValue}}`, `{{icpTarget}}`), arrays stay arrays (`{{icpBands}}`, `{{signalRows}}`), strings stay strings.
- `{{icpBands}}` is an array of `{ from, to, variant, label }` (variants error/warning/success) covering the meter's full 0→100 range in order.
- `datagrid` rows: one per signal. The Read badge (`tag.badgeVariant`) reflects signal type — `"success"` (Opportunity), `"info"` (Signal), `"warning"` (Obstacle). `_status` drives the auto Status column.
- Callout buttons: the primary is `action/sendMessage` with a first-person `content` prompt (`{{ctaMsg}}`, e.g. "Draft a warm intro request…"); the secondary is `action/openLink` with `{{prospectUrl}}` — the account's Lightning URL (`https://<myDomain>/lightning/r/Account/<Id>/view`), opening a new tab. Omit the openLink button if you lack the Id.
- No fabricated content — quote blank fields as blank rather than inventing them; drop signals you have no data for.


> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.

## 6. Output

```
# Prospect Research: [Company]

## CRM Status
[Already in Salesforce - owned by [Name], [N] open opps | OR | Net new - no CRM record]

## Company Snapshot
- What they do: [one line]
- Size / stage: [employees, funding]
- HQ: [location]
- Leadership: [key names + titles]

## Recent Signals
- [Date] - [Signal] ([source])
...

## [Contact Name] (if specified)
- Role / tenure / background
- What they likely care about

## ICP Fit: [Strong / Moderate / Poor]
[Scoring table]
[One-sentence rationale]

## Relevance Hooks
1. [Specific hook] - ties to [your value prop angle]
2. ...

## Suggested Next Step
[e.g. "Run draft-outreach targeting [Contact]" or "Low fit - log as disqualified" or "Already owned by [Name] - coordinate before reaching out"]
```
