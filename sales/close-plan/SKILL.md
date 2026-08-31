---
name: close-plan
description: Build the business case and mutual action plan for a deal - the why-buy/why-now story, the ROI framing, and the dated step-by-step path to signature shared with the customer. Use when the user says "build a close plan for [deal]", "mutual action plan for [account]", "business case for [opp]", or "what's the path to signature".
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


# Close Plan

Ground → read opp → gather evidence (all ONE turn) → draft business case + MAP.

## 1. Ground (hardcoded — Opportunity only)

Ground **only Opportunity** — it always exists. Its fields + childRelationships reveal this org's real custom schema; don't assume object names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

From the result: (a) scalar `__c` fields (business-case data, why-now, ROI, etc.) — take their `{ value }`; (b) each lookup field's exact `relationshipName` to span for a related record's Name; (c) each child `relationshipName`.

## 2. Read opp + evidence (issue ALL in one turn)

`%DEALNAME%` = 1–2 words. Reference-field rules: scalar → `Field__c { value }`; related name → span via the exact `relationshipName`: `<relationshipName> { Name { value } }`. Only span relationships Step 1 returned. If no usable relationshipName, take the `__c { value }` (the Id) and move on.

Insert `<OPP_CUSTOM>` = confirmed scalar `__c { value }` fields; `<REL_BLOCKS>` = one block per confirmed relationship. Standard fields + `OpportunityContactRoles` always work.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { Name: { like: \\\"%DEALNAME%\\\" } }, first: 1) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } NextStep { value } Description { value } <OPP_CUSTOM> Account { Name { value } } Owner { Name { value } } <REL_BLOCKS> OpportunityContactRoles { edges { node { Role { value } IsPrimary { value } Contact { Name { value } Title { value } } } } } } } } } } }\"}" })
```

Empty `edges` → broaden `%…%`.

**Evidence (in PARALLEL with step 2 — same turn):** Fire email/doc/Slack searches keyed on the deal/account name; these don't depend on the SF result. Use whatever tools are present; if none, skip silently.

- **Call transcripts / proposals:** customer's stated problems, success metrics, quantified pain, who said what.
- **Email:** commitments already made in writing, procurement/legal/security threads.
- **Slack:** internal deal-desk/exec mentions, concerns.
- **deal-advance-gap output** (if run this session): its known gaps feed the mutual action plan directly — don't re-derive them.

## 3. Draft business case

**Value prop, differentiators, required stakeholders for close, and internal approval chain are external knowledge — infer from the org's own data or ask the user once. Never invent it.**

In the customer's language, grounded in their own words (cite the call/email each point comes from):

1. **Current state and cost of it** - the problem as they described it, quantified where they gave numbers
2. **Desired outcome** - their success metrics, their timeline drivers (the why-now)
3. **Proposed solution** - what they're buying, mapped to each outcome
4. **Investment and return** - price vs. the quantified value; keep the math simple and attributable
5. **Risk of waiting** - what the delay costs in their terms
6. **Why us** - only differentiators they have actually reacted to

Flag every claim that has no customer evidence behind it — those are the points to validate on the next call, not assert in the doc.

## 4. Draft mutual action plan

Work backward from the target signature date (default: opportunity CloseDate) through both sides' steps: remaining validation, security review, legal redlines, procurement, signatures, plus any internal approvals the user mentions. Each row: step, owner (us / customer / named person), target date, status. Flag the steps whose dates make the CloseDate impossible.

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

The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (meter arrays, datagrid rows) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text. No fabricated content: blank fields stay blank, drop steps with no data.

Layout (editorial restraint, one chart): header (check-circle icon + serif title + status badge) → subhead caption → one meter (close-plan progress) → path-to-signature datagrid → one `variant:"error"` synthesis callout with two buttons.

Tokens: `planTitle` (header title, "Mutual close plan — [Account]") + `headerStatus` (header badge, e.g. "6 DAYS OUT") · `subtitle` (one line: amount, target close, days out, steps done) · meter — `progressValue`/`progressMax`/`progressTarget` (numbers), `progressValueLabel`/`progressTargetLabel`/`progressStatus` (strings), `progressBands` (array of `{ from, to, variant, label }`, variants warning/success, covering 0→max in order) · `pathRows` (datagrid array, one row per action-plan step, each `{ step, side:{value,badgeVariant}, owner (plain string — format as the person's display name (e.g. "R. Chen"); names must be plain strings, not objects: use `Contact.Name.value` or `User.Name.value` from the SF response), due (ISO YYYY-MM-DD), state:{value,badgeVariant}, _tone (error/warning/info/default), _status (Critical/At risk/On track/Target) }`; renderer auto-injects a leading Status column from `_status`; Side badgeVariant primary=Us / secondary=Them / info=Both; State badgeVariant error=Due today/Critical, warning=In review/Waiting/At risk, info=Scheduled, secondary=Target/On track) · callout — `calloutTitle` (headline blocker), `calloutDesc` (cost if it slips), primary button `ctaLabel`/`ctaMsg` (`action/sendMessage`, first-person prompt), secondary `oppUrl` (`action/openLink`, `https://<myDomain>/lightning/r/Opportunity/<Id>/view` — omit if no Id). Before calling: no `{{…}}`/`{!…}` remain, meter is the only chart, every button is `action/sendMessage` or `action/openLink` with real content.

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
                  { "definition": "tile/text", "attributes": { "text": "{{planTitle}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{headerStatus}}", "variant": "warning" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/meter",
            "attributes": {
              "label": "Close plan progress",
              "value": "{{progressValue}}",
              "min": 0,
              "max": "{{progressMax}}",
              "target": "{{progressTarget}}",
              "valueFormat": "number",
              "valueLabel": "{{progressValueLabel}}",
              "targetLabel": "{{progressTargetLabel}}",
              "status": "{{progressStatus}}",
              "size": "lg",
              "bands": "{{progressBands}}"
            }
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Path to signature, by date",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                { "key": "step", "header": "Step", "type": "text" },
                { "key": "side", "header": "Side", "type": "badge" },
                { "key": "owner", "header": "Owner", "type": "avatar" },
                { "key": "due", "header": "Due", "type": "date" },
                { "key": "state", "header": "State", "type": "badge" }
              ],
              "rows": "{{pathRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "error",
              "title": "{{calloutTitle}}",
              "description": "{{calloutDesc}}"
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
## 6. Text — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Close Plan: [Opp Name] - [Account]

## Business Case (customer-facing doc)

### Current State
[Problem as they described it, quantified where they gave numbers]

### Desired Outcome
[Their success metrics, their timeline drivers]

### Proposed Solution
[What they're buying, mapped to each outcome]

### Investment and Return
[Price vs. quantified value — simple math, attributable]

### Risk of Waiting
[What the delay costs in their terms]

### Why Us
[Only differentiators they reacted to]

**Claims to validate:** [Every claim with no customer evidence]

## Mutual Action Plan (shared table)

| Step | Owner | Target Date | Status |
|------|-------|-------------|--------|
| [Remaining validation] | [us/customer/name] | [date] | [status] |
| [Security review] | | | |
| [Legal redlines] | | | |
| [Procurement] | | | |
| [Signatures] | | | |
| [Internal approvals] | | | |

**Date conflicts:** [Steps whose dates make CloseDate impossible]

## Suggested SFDC updates
- NextStep → "[next dated step from the plan]"
- CloseDate → [if backward plan says current date not credible]
[Apply with `update-opportunity`, or manually if read-only.]

## Draft email to champion
[Sharing the action plan and asking them to confirm owners on their side]
```

**Offer to create the artifacts as shareable documents** if a docs connector is present (capability call, not an SF read — skip silently if absent): the business case as a customer-facing doc, and the mutual action plan as a co-ownable table. Degrade to the inline markdown above when no docs tool is available.
