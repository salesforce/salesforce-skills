---
name: lead-triage
description: Score and route a single inbound lead against your ICP and qualification framework, then recommend a priority and next action. Use when the user asks "triage this lead", "is [company] a good lead", "qualify [lead]", or pastes lead info.
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


# Lead Triage

Ground → read Lead + Account → enrich → score → route. **No per-lead follow-ups** — the reads have the data.

## 1. Ground (hardcoded — Lead and Account)

Ground **Lead** and **Account** (for ICP fields). Both always exist. One call, both objects — `objectInfos` takes multiple roots, and the top-level `ApiName` tells the two catalogs apart in the response:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Lead\\\", \\\"Account\\\"]) { ApiName fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

**If it overflows**, the result auto-persists to a temp file **outside the bash mount** — don't shell to it (`cat`/`python3`/`ls` will fail, it's not on that mount). Read it back with the Read tool only, and go straight to that — don't retry bash first. If the Read tool can't load it either, skip custom-field grounding and proceed with standard fields only; don't keep retrying.

From the results: (a) scalar `__c` fields (segment, industry, employee count, lead score, MQL status, etc.) — take their `{ value }`; (b) each lookup field's exact `relationshipName` to span for a related record's Name; (c) each child `relationshipName`.

## 2. Read lead + matching account (templated, one turn)

Fire these as tool calls in **one turn** (independent). Insert `<LEAD_CUSTOM>` = confirmed scalar `__c` fields on Lead, `<ACCOUNT_CUSTOM>` = confirmed scalar `__c` fields on Account.

**Lead (by identifier user provided — Id, email, or name+company):**
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Lead(where: { <LEAD_FILTER> }, first: 1) { edges { node { Id Name { value } Company { value } Title { value } Email { value } LeadSource { value } Status { value } CreatedDate { value } <LEAD_CUSTOM> Owner { Name { value } } } } } } } }\"}" })
```

**Account (by company name or domain):**
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { or: [{ Name: { like: \\\"%<COMPANY>%\\\" } }, { Website: { like: \\\"%<DOMAIN>%\\\" } }] }, first: 5) { edges { node { Id Name { value } Type { value } <ACCOUNT_CUSTOM> Owner { Name { value } } } } } } } }\"}" })
```

`<LEAD_FILTER>` = build from user input: `Id: { eq: "<id>" }` OR `Email: { eq: "<email>" }` OR `and: [{ Name: { like: "%<name>%" } }, { Company: { like: "%<company>%" } }]`

If Account exists with Owner → existing relationship, routing = coordinate with that owner.

**Web research (parallel with SF reads):** Use web search/fetch if available to find company size, industry, funding, recent news. Fire in SAME turn as SF reads. If tools absent, skip silently.

**Email search (parallel):** Use email search if available to find prior threads from this domain. Fire in SAME turn. If tool absent, skip silently.

## 3. Score ICP fit

Against ICP (ask user once if not inferrable from org data):

| Dimension | Fit | Evidence |
|---|---|---|
| Industry | ✅ / ⚠️ / ❌ | [from Account/web] |
| Size | ✅ / ⚠️ / ❌ | [from Account custom/web] |
| Persona (title) | ✅ / ⚠️ / ❌ | [from Lead.Title] |
| Disqualifiers | ✅ none / ❌ [which] | [check against ICP] |

## 4. Score intent

| Signal | Strength |
|---|---|
| Source quality | High (demo request, referral) / Med (content, event) / Low (list, cold) |
| Message specificity | Specific use case / Generic interest / None |
| Prior engagement | Email thread / SFDC history / None |
| Timing trigger | Recent funding, hiring, exec change / None |

## 5. Assign priority

Calibration: P0 ≈ top 20%, P1 ≈ next 25%, P2 ≈ remaining.

- **P0:** Strong ICP fit AND high intent (specific ask, demo request, or hot trigger)
- **P1:** Strong fit with medium intent, OR moderate fit with high intent
- **P2:** Moderate fit with low intent, or fit unclear
- **DQ:** Hard disqualifier hit

Override: if Account exists with owner → routing = "coordinate with [owner]"


## 6. Render

Call `display_widget` now with the data you collected. Do not write markdown first — call immediately. Only fall back to markdown if the tool is unavailable.

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

The widget template is embedded below. Call `display_widget` in **dynamic** mode with it. It is a skeleton: replace every `{{token}}` placeholder with a fully-resolved literal computed from the leads you scored — this echo path does no expression compilation, so no `{!…}` bindings.

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
                  { "definition": "tile/icon", "attributes": { "name": "user", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{headerTitle}}", "variant": "page-title" } }
                ]
              }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{headerSubtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "lg", "align": "center", "isWrapped": false },
            "children": [
              {
                "definition": "tile/piechart",
                "attributes": {
                  "caption": "Leads by tier",
                  "variant": "donut",
                  "valueFormat": "number",
                  "showLegend": false,
                  "centerLabel": "New leads",
                  "centerValue": "{{centerValue}}",
                  "slices": "{{slices}}"
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
              "caption": "Leads by source",
              "categories": "{{categories}}",
              "series": "{{series}}",
              "valueFormat": "number",
              "showValues": true,
              "showLegend": false
            }
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Work these first — hot leads by score",
              "appearance": "striped",
              "defaultSort": { "key": "score", "direction": "desc" },
              "totalRows": "{{totalRows}}",
              "columns": [
                { "key": "lead", "header": "Lead", "type": "text" },
                { "key": "co", "header": "Company", "type": "text" },
                { "key": "score", "header": "Fit score", "type": "databar", "target": 100, "sortable": true },
                { "key": "src", "header": "Source", "type": "badge" },
                { "key": "next", "header": "Next step", "type": "text" }
              ],
              "rows": "{{hotRows}}"
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

What each block shows, from data you already have — a synthesis-forward layout: a header, two charts, one datagrid, and one recommendation. Not a dashboard.

- **Header** — an icon, page-title text (`{{headerTitle}}`), with a one-line caption subhead (`{{headerSubtitle}}`) summarizing the leads (scored by fit and intent · tier counts) and a separator.
- **Tier donut + its written breakdown** — a piechart (donut, "Leads by tier", `{{slices}}` with Hot/Warm/Nurture counts, center shows `{{centerValue}}` "New leads") paired in a row with a text column to its right (`{{donutAsideTitle}}` section-title + `{{donutAside}}` body). The donut runs with `showLegend:false`, so `{{donutAside}}` must name every slice with its count (and %) in prose — it replaces the legend, and a colorblind reader relies on it. Keep it to one sentence (~18–32 words) that leads with the insight, not a bare list.
- **Source column chart, full-width** — preceded by a caption pair (`{{chartAsideTitle}}` section-title + `{{chartAside}}` body, one-sentence takeaway), then the column chart itself full-width ("Leads by source", `{{categories}}` on x-axis, `{{series}}` data, `valueFormat:"number"`, `showValues:true`, `showLegend:false`). A column chart must be full-width to keep its axis, value labels, and bar height legible — never put it in a shared row.
- **Hot leads datagrid** (`{{hotRows}}`) — one row per hot lead. Columns: Lead (text), Company (text), Fit score (databar, target 100, sortable), Source (badge), Next step (text). Every row carries `_tone` (success) and `_status` (Hot); the renderer auto-injects a leading Status column from `_status`. `totalRows` shows the full lead count.
- **One synthesis callout** (`variant:"info"`) — `{{calloutTitle}}` (the queue's single most important read) and `{{calloutDescription}}`. It carries two real buttons: a primary "Draft outreach to both" (`{{ctaPrimaryLabel}}` / `{{ctaPrimaryMsg}}`, `action/sendMessage`) and a secondary "View in Salesforce" (`{{salesforceUrl}}`, `action/openLink`).

**Hydration rules:**
1. Start from the embedded template above — a valid-JSON widget-definition envelope whose leaf values carry `{{token}}` placeholders.
2. Resolve every `{{token}}`. A value that is **only** a `{{token}}` (piechart `slices`, chart `categories` and `series`, datagrid `rows`, `totalRows`, `centerValue`) becomes the resolved **typed** literal — numbers stay numbers, arrays stay arrays. A `{{token}}` **inside** a larger string is interpolated as text.
3. `{{slices}}` is an array of slice objects — each with `label`, `value`, and optionally `role:"highlight"` (for Hot). `{{categories}}` is an array of source names. `{{series}}` is an array with one series object carrying `name` and `data` (array of numbers).
4. `{{hotRows}}` is an array of lead objects — each with `lead` (name), `co` (company), `score` (number 0-100), `src` (`{ value, badgeVariant }`), `next` (next step text), `_tone` (success), and `_status` (Hot).
5. The result is hydrated widget definition (no `{{…}}` placeholders remain). Then call:

```
display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated renderer.json> })
```

**Binding rules:**
- Resolve every `{{token}}` to a literal before calling — numbers stay numbers (`{{totalRows}}`, `{{centerValue}}`, each row's `score`, each slice's `value`, chart `data` numbers), arrays stay arrays (`{{slices}}`, `{{categories}}`, `{{series}}`, `{{hotRows}}`), strings stay strings.
- Piechart `slices`: each slice has `label`, `value` (number), and optionally `role:"highlight"` for the Hot tier.
- Chart `series`: array with one object `{ name: "Leads", data: [array of numbers] }` matching the `categories` count.
- Aside text: `{{donutAsideTitle}}` / `{{donutAside}}` describe the tier donut (donutAside states each slice's count and % in words, since the legend is off); `{{chartAsideTitle}}` / `{{chartAside}}` sit above the source chart (chartAside interprets the shape — which sources dominate — rather than re-listing every bar). All four are plain strings computed from the same counts you charted. Do not repeat the callout's specific claims.
- `datagrid` rows: one per hot lead. `score` is a raw number (0-100) — the databar fills against `target:100`. The Source badge (`src.badgeVariant`) reflects source quality — `"success"` (Inbound demo, Referral), `"info"`, or `"secondary"` (Webinar, Event, Content). `_status` drives the auto Status column.
- Callout buttons: the primary is `action/sendMessage` with a first-person `content` prompt (`{{ctaPrimaryMsg}}`, e.g. "Draft outreach to Beacon Health..."); the secondary is `action/openLink` with `{{salesforceUrl}}` — the Leads list view Lightning URL (`https://<myDomain>/lightning/o/Lead/list`), opening a new tab.
- No fabricated content — quote blank fields as blank rather than inventing them; drop leads you have no data for.



> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.

## 7. Output

```
# Lead Triage: [Name] @ [Company]

**Priority: P[0/1/2/DQ]**
[One-sentence rationale]

## CRM Status
[Net new | OR | Account exists - owned by [Name], coordinate first]

## ICP Fit: [Strong / Moderate / Poor]
[fit table]

## Intent: [High / Medium / Low]
[intent table]

## Recommended Action
- **Route to:** [self / named owner / DQ queue]
- **Response SLA:** [P0: same day / P1: 48h / P2: this week]
- **First touch:** [e.g. "draft-outreach with [hook]" or "send qualification questions" or "DQ - reply with polite no"]

## Suggested SFDC updates
[Apply with write skills, or manually if read-only.]
- Lead Status → [value]
- Lead Owner → [name]
- [Notes field] → "[triage summary]"
```

If routing to teammate, offer to draft Slack message to lead-handoff channel (ask user for channel if not known).
