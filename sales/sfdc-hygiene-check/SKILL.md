---
name: sfdc-hygiene-check
description: Read-only audit of your Salesforce opportunities for missing fields, stale dates, and stage mismatches - outputs a fix checklist you apply yourself. Use when the user asks "check my SFDC hygiene", "audit my opps", "what's missing in Salesforce", or "clean up my pipeline".
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


# SFDC Hygiene Check

Read-only audit of open opps → fix checklist you apply yourself (nothing is written). Ground → one read → run checks → output.

## 1. Ground (hardcoded — Opportunity only)

Opportunity always exists; naming a missing object fails the whole call. Its fields reveal this org's `__c` hygiene fields (competitor, required-per-stage, next-step trackers) — use exact names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } } } }\"}" })
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

The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (chart/piechart/datagrid arrays) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text. Layout note: the hygiene-state donut runs with `showLegend:false` and sits in a row beside a text column (`donutAsideTitle` + `donutAside`); the issue-frequency column chart is full-width, preceded by a caption pair (`chartAsideTitle` + `chartAside`). A column chart must be full-width to keep its axis, value labels, and bar height legible — do not put it in a shared row.

Tokens: `hygieneTitle` (plain string — e.g. "Pipeline hygiene — Dana Ruiz") · `oppCountBadge` (plain string — e.g. "18 OPEN OPPS") · `hygieneSubtitle` (plain string — one-line summary e.g. "18 open opps · 4 critical, 5 need attention, 9 clean") · `totalOpps` (plain string — formatted count e.g. "18") · `donutAsideTitle donutAside` (short title + one-sentence breakdown beside the hygiene-state donut; because the legend is off, `donutAside` must name every slice — clean/needs-attention/critical — with its count and % in prose) · `hygieneSlices` (donut slices `{label,value,role?}`, drop zero-count, `role:"highlight"` on Critical) · `chartAsideTitle chartAside` (short title + one-sentence takeaway above the full-width issue chart; interpret which issues dominate rather than re-listing every bar) · `issueCategories`/`issueSeries` (bar, most-common first, matching order, drop zeros; `issueSeries` is one object `{name:"Opps", data:[...numbers...]}`) · `flaggedRows` (`{name (plain string — format as the opportunity name (e.g. "Meridian Health platform"); names must be plain strings, not objects: use `Opportunity.Name.value` from the SF response), amount(num), close(YYYY-MM-DD), issue:{value,badgeVariant}, fix, _tone, _status}` — `error`/"Critical" for past-close or no-next-step-near-close, `warning`/"Needs attention" for stale/missing-amount; clean rows omit `_tone`/`_status`) · footer `flaggedCount` `totalAtRisk`. Callout: `synthTitle` (plain string — e.g. "Two fixes can't wait") · `synthDetail` (plain string — one to two sentences) · `ctaLabel` (plain string — button label) · `ctaMsg` (plain string — first-person prompt for the action button) · `hygieneUrl` (plain string — Lightning list URL for "View in Salesforce").

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
                  { "definition": "tile/icon", "attributes": { "name": "check-circle", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{hygieneTitle}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{oppCountBadge}}", "variant": "info" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{hygieneSubtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "lg", "align": "center", "isWrapped": false },
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
              },
              {
                "definition": "tile/row",
                "attributes": { "gap": "xs", "align": "start", "direction": "column", "width": "stretch" },
                "children": [
                  { "definition": "tile/text", "attributes": { "text": "{{donutAsideTitle}}", "variant": "section-title" } },
                  { "definition": "tile/text", "attributes": { "text": "{{donutAside}}", "variant": "body", "color": "muted" } }
                ]
              }
            ]
          },

          { "definition": "tile/text", "attributes": { "text": "{{chartAsideTitle}}", "variant": "section-title" } },
          { "definition": "tile/text", "attributes": { "text": "{{chartAside}}", "variant": "body", "color": "muted" } },

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
              "defaultSort": { "key": "amount", "direction": "desc" },
              "columns": [
                { "key": "name", "header": "Opportunity", "type": "text" },
                { "key": "amount", "header": "Amount", "type": "currency", "align": "right", "sortable": true },
                { "key": "close", "header": "Close", "type": "date" },
                { "key": "issue", "header": "Issue", "type": "badge" },
                { "key": "fix", "header": "Suggested fix", "type": "text" }
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
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{hygieneUrl}}" } }
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

Validate bucket counts: critical + attention + clean = total open.

```
# SFDC Hygiene Check — <N> open opps
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
