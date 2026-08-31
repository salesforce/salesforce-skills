---
name: deal-signals
description: Proactive watch over your book - deals gone quiet, close dates slipping into view, champion changes, renewal windows opening, competitor mentions - surfaced as a short alert digest you can act on. Use when the user asks "what changed in my book", "what changed in my pipeline", "any deals gone quiet", "what should I be worried about", "show me deal signals", "what moved", "what's at risk", "run my deal signals", or sets it up as a recurring scheduled task. This skill detects CHANGES and THRESHOLD CROSSINGS, not static pipeline state.
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

# Deal Signals

Ground → (read + evidence, one turn) → check thresholds → digest. Scope: my book (default), or a tier/team if asked. Since: last run, else 7 days.

## 1. Ground (hardcoded — Opportunity only)

Opportunity always exists; naming a missing object fails the whole call. Its fields reveal this org's custom signal fields — don't assume names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

Note scalar `__c` fields relevant to signals (renewal date, competitor, champion, deal-desk/legal-hold). Use exact names from this result.

## 2. Read the open book (one call, scope: MINE)

`scope: MINE` = the running user's book (no user lookup needed). Add confirmed `__c { value }` fields into `<OPP_CUSTOM>`. For a tier/team scope, drop `scope: MINE` and filter on owner/team instead.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(scope: MINE, where: { IsClosed: { eq: false } }, first: 100) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } NextStep { value } LastActivityDate { value } LastModifiedDate { value } ForecastCategory { value } <OPP_CUSTOM> Account { Name { value } } } } } } } }\"}" })
```

## 2b. Evidence (same turn, only for CRM-flagged accounts — keeps the sweep fast)

After threshold checks flag accounts, in ONE turn fire (parallel, if tools present): **email** (last reply from us / **inbound from them with no reply from us in 3+ business days** / bounce / OOO / departure), **docs/transcripts** (competitor mention), **slack** (deal-desk/exec concerns). Keyed on the flagged account names. No tools present → skip silently.

**No extra Salesforce reads.** Step 2 already returned every CRM field the thresholds need (LastActivityDate, CloseDate, LastModifiedDate, NextStep, ForecastCategory, `__c` signals). Do NOT dispatch per-opp SF follow-ups (EmailMessage / Task / OpportunityFieldHistory / activity queries) — each is a serial round-trip. Evidence here is ONLY the external email/doc/slack connectors above; if those aren't present, skip.

## 3. Check thresholds (compute explicit dates from today — never quarter-relative)

Per open opp, fire a signal only when the record shows the trigger:
- **Gone quiet** — LastActivityDate >14d ago (or null) AND CloseDate within 90d
- **Inbound waiting** — customer emailed us and we haven't replied in 3+ business days (email evidence; the ball is on our side)
- **Danger zone** — CloseDate ≤21d out and stage still early
- **Overdue** — CloseDate < today
- **Slipped** — CloseDate moved out / recent LastModifiedDate date change
- **Stale commitment** — NextStep unchanged 21d+
- **Champion risk** — primary contact left/quiet (email/OOO evidence)
- **Renewal opening** — renewal entering lead-time window
- **Competitor mention** — named in recent email/transcript

## 4. Widget (default output when `display_widget` is present: Cowork/desktop/web)

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

The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (chart/meter/datagrid arrays) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text. Compute every leaf from data already fetched; no `{!…}` bindings, no fabrication (blank fields stay blank; drop signals with no data).

Synthesis-forward layout — header, two graphs, one datagrid, one callout:
- **Header** — activity icon, title (`{{title}}`), status badge (`{{headerStatus}}`), one-line caption (`{{subtitle}}`) summarizing score/trend/signal counts, and a second muted caption (`{{dealContext}}`) carrying this opp's shared deal facts — StageName label · Amount · CloseDate · next step · last activity — joined by ` · ` (constant across the signals below, so it sits once in the header, not per row).
- **Two graphs** — line chart of the 6-week signal-score trend (`{{chartCaption}}`, `{{chartCategories}}` = week labels, `{{chartSeries}}` = one `[{ name, data: [numbers] }]`); and a meter for the composite score (`{{meterLabel}}`, `{{meterValue}}` vs target `{{meterTarget}}` max `{{meterMax}}`, `valueFormat:"number"`, `{{meterValueLabel}}`, `{{meterTargetLabel}}`, `{{meterStatus}}`, and `{{meterBands}}` = ordered `[{ from, to, variant, label }]` covering 0→max for Cold/Warm/Hot, variants error/warning/success).
- **Signals datagrid** (`{{datagridCaption}}`, `{{datagridRows}}`) — one row per signal, strongest first: `signal` (name), `dir` (badge `{ value, badgeVariant }` — success Positive / warning Watch), `when` (ISO `YYYY-MM-DD`), `note` (detail), plus `_tone` (success/warning) and `_status` (Buy/Watch); the renderer auto-injects a leading Status column from `_status`.
- **One synthesis callout** (`variant:"success"`) closes the widget — `{{calloutTitle}}` (the single most important read) and `{{calloutDescription}}`, with two real buttons: primary `action/sendMessage` (`{{primaryButtonLabel}}` / first-person `{{primaryButtonContent}}`) and secondary "View in Salesforce" `action/openLink` to `{{oppUrl}}` (`https://<myDomain>/lightning/r/Opportunity/<Id>/view`; omit if you lack the Id). No decorative buttons.

Before calling, verify: no `{{…}}`/`{!…}` remain; `{{chartCategories}}`/`{{chartSeries}}`/`{{meterBands}}`/`{{datagridRows}}` are arrays and `{{meterValue}}`/`{{meterMax}}`/`{{meterTarget}}` numbers; both buttons wired (real sendMessage `content`, openLink `url`); two graphs present; the callout closes it. Tokens: title subtitle dealContext headerStatus meterLabel/Value/Max/Target/ValueLabel/TargetLabel/Status/Bands chartCaption/chartCategories/chartSeries datagridCaption/datagridRows calloutTitle/calloutDescription primaryButtonLabel/primaryButtonContent oppUrl.

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
                  { "definition": "tile/text", "attributes": { "text": "{{title}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{headerStatus}}", "variant": "success" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },
          { "definition": "tile/text", "attributes": { "text": "{{dealContext}}", "variant": "caption", "color": "muted" } },

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
                  "label": "{{meterLabel}}",
                  "value": "{{meterValue}}",
                  "min": 0,
                  "max": "{{meterMax}}",
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
              "caption": "{{datagridCaption}}",
              "appearance": "striped",
              "columns": [
                { "key": "signal", "header": "Signal", "type": "text" },
                { "key": "dir", "header": "Direction", "type": "badge" },
                { "key": "when", "header": "Detected", "type": "date" },
                { "key": "note", "header": "Detail", "type": "text" }
              ],
              "rows": "{{datagridRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "success",
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
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{oppUrl}}" } }
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

Per fired signal, surface the trigger value **plus one or two supporting facts** from the Step 2 record (all already fetched — no new read), separated by ` • ` so the evidence is scannable, not a single condensed fact. Blank line between the 🔴 and 🟡 groups.

```
# Deal Signals — <today> — <scope>

🔴 Act today
- **<Account / Opp>** — <signal> — <StageName label> • $<Amount> • close <CloseDate> • last activity <LastActivityDate> • next step <NextStep> → <action>

🟡 This week
- **<Account / Opp>** — <signal> — <trigger value> • <supporting fact> • <supporting fact> → <action>

✅ Nothing else crossed a threshold (<N> opps swept)
```
Link each record. CRM fix → offer `update-opportunity`; a touch → `draft-outreach`/`schedule-meeting`. Scheduled run: lead with count of new items since last run; a quiet digest is success.
