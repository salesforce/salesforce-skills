---
name: deal-advance-gap
description: Forward-looking gap check on one opportunity - exactly what is missing to advance it to the next stage and to close, with who does what by when. Use when the user asks "what's missing to advance [deal]", "what do I need to move [opp] forward", "why is [deal] stuck", or "what's between [account] and a close".
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

- Apply the human-label rule to Opportunity child records too. State a risk as "Blocking: yes · Severity: High · Status: Mitigating", never `Is_Blocking__c = true`.

# Deal Advance Gap

Forward-looking: against the org's stage exit criteria, what has to happen for this deal to advance — and the shortest path to it. Ground → resolve to one Id (+ evidence, ONE turn) → detail read → map gaps → sequence → output.

## 1. Ground (hardcoded — Opportunity only)

Ground **only Opportunity** — it always exists (naming a missing object fails the whole call). Its fields + childRelationships reveal this org's stage/qualification/next-step schema; don't assume names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

Step 1 is the authority on names. Note: (a) scalar `__c` fields carrying stage-exit / next-step / blocker / qualification signal — take `{ value }` **and keep each field's `label`**; (b) each lookup's exact `relationshipName` for spanning a related name; (c) each child `relationshipName`. **Build an ApiName→label map now and use the `label` in ALL output** (e.g. "Executive Sponsor", not `Executive_Sponsor__c`; "Target Resolution Date", not `Target_Resolution_Date__c`) — never print a `__c` API name to the user.

## 2a. Resolve to ONE opportunity Id (before the detail read)

Given an SFDC **Id** already → skip to 2b with `Id: { eq: "<Id>" }`. Given a **name**, resolve it first — `first: 1` on a `Name like` only caps the response; it does **not** pick the right deal, so on a multi-match it returns an arbitrary one. Run a bounded, ordered candidate query (`%DEALNAME%` = 1–2 distinctive words):

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { Name: { like: \\\"%DEALNAME%\\\" } }, orderBy: { CloseDate: { order: ASC } }, first: 10) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } Account { Name { value } } } } } } } }\"}" })
```

- **Exactly one** candidate → take its `Id`, go to 2b.
- **Several** → list them (Account · Name · Stage · $ · close) and **ask which**; don't guess.
- **None** → broaden `%…%` and retry once.

## 2b. Read the resolved opp by Id (fill from step 1)

Filter by the **exact Id** from 2a (`first: 1` is correct here — the filter is a unique record Id). **Reference-field rules (avoids the retry loop):**
- Scalar/`__c` → `Field__c { value }`. `displayValue` is null for Id fields — don't rely on it.
- Related record's name → span the exact `relationshipName` from Step 1: `<relationshipName> { Name { value } }`. Do NOT append `{ … }` to a raw `Id`/`__c` field.
- No usable relationshipName → take the `__c { value }` (Id) and move on — **do not retry**.

Insert `<OPP_CUSTOM>` = confirmed scalar `__c { value }` fields; `<REL_BLOCKS>` = one block per confirmed relationship (`<relationshipName> { Name { value } … }` for a lookup; `<childRelationshipName> { edges { node { … } } }` for a child). Standard fields + `OpportunityContactRoles` always work.

**Before dispatching, double-check the query's braces balance** (count `{` vs `}` — they must be equal). Splicing `<OPP_CUSTOM>`/`<REL_BLOCKS>` is where a `}` gets dropped; keep the read flat (no unnecessary nesting).

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { Id: { eq: \\\"<OPP_ID>\\\" } }, first: 1) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } Probability { value } NextStep { value } ForecastCategory { value } LastActivityDate { value } <OPP_CUSTOM> Account { Name { value } } Owner { Name { value } } <REL_BLOCKS> OpportunityContactRoles { edges { node { Role { value } IsPrimary { value } Contact { Name { value } Title { value } } } } } Tasks(first: 15, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Subject { value } ActivityDate { value } Status { value } Description { value } Type { value } } } } Events(first: 10, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Subject { value } ActivityDate { value } Description { value } } } } } } } } } }\"}" })
```

Target = next stage (default) or "to close" if asked.

**Retry contract on `InvalidSyntax` / "offending token `<EOF>`" (the dynamic splice dropped a brace):** construct **one** corrected query and dispatch it **only if its text differs** from the failed one (add the missing `}` — never re-send byte-identical text; an identical retry just burns a round-trip for the same error). If that corrected retry still fails, **stop retrying the spliced shape** — fall back to the fixed, guaranteed-field query below (standard fields + contact roles only, no `<OPP_CUSTOM>`/`<REL_BLOCKS>`), then continue the analysis and note that optional custom risk signals were unavailable:
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { Id: { eq: \\\"<OPP_ID>\\\" } }, first: 1) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } Probability { value } NextStep { value } ForecastCategory { value } LastActivityDate { value } Account { Name { value } } Owner { Name { value } } OpportunityContactRoles { edges { node { Role { value } IsPrimary { value } Contact { Name { value } Title { value } } } } } } } } } } }\"}" })
```

## 2c. Evidence (run IN PARALLEL with 2a — same turn, issue all at once)

**Issue 2a and all of 2c in a single turn** — these searches key on the deal/account name from the *request* (not the SF read), so batch them with candidate resolution; only 2b's detail read waits on the resolved Id. Keyed on the deal/account:
- **email**: last exchange per contact, open commitments in both directions, silence/OOO/departure
- **docs**: latest transcript/notes → decisions, objections, open commitments, competitor mentions
- **slack**: internal blockers — deal desk, legal, security review, pricing approval

Use whatever email/doc/Slack tools are present; if none, skip silently (SF-only is fine). Cite source + date for anything used.

**No extra Salesforce reads.** 2b already returned the CRM state (stage, close, next step, probability, forecast, last-activity, contact roles, recent Tasks/Events, `__c` signals). Do NOT dispatch a **separate** per-opp SF follow-up (a standalone `ActivityHistory` / `OpportunityFieldHistory` / Task query) — recent activity already rides along as the `Tasks`/`Events` child edges in the 2b query (same round-trip, no extra call). Read those children as distinct states: a completed Task (Status Completed / past-dated Event) is a done touch; an open Task or a future-dated Task/Event is **🔶 In motion / scheduled**, not done — that's the signal behind "Already in motion". Deeper detail comes from the external evidence above.

## 3. Map gaps against exit criteria (cite every claim; invent nothing)

Exit criteria, qualification framework, and required-stakeholders-for-close are **external knowledge** — infer from the org's own data (StageName picklist, closed-won patterns) or ask the user once. Never invent. For the current stage's exit criteria (and every later stage if target is "to close"), mark each: **✅ Done / 🔶 In motion / ❌ Not started**, with the source and the specific gap. Then check the qualification framework the same way — flag only elements that **block advancement**, not every unknown.

## 4. Sequence the path

Order gaps into the shortest credible path: whose gap (Us / Customer / internal team), parallel vs. strictly sequential, and the single next action that unblocks the most downstream items. Critical-path length → earliest credible close; flag if that lands after the current CloseDate.

## 5. Output — widget FIRST (the rendered UI is the default)

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

The widget template is embedded below — a widget-definition envelope whose leaf values carry {{token}} placeholders. Resolve every {{token}} to a literal (no {{…}}/{!…} left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a {{token}} becomes the typed literal — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string is interpolated as text. Tokens: `headerTitle headerStatus headerSubtitle` (strings) · `meterValue meterMax meterTarget` (numbers — meter `value`/`max`/`target`) · `meterValueLabel meterTargetLabel meterStatus` (strings) · `meterBands` (array: `[{ from, to, variant, label }]` — variants error/warning/success, covering 0→max) · `gridCaption` (string) · `gridRows` (array, one per gap, blockers first: `[{item, owner (plain string — format as the person's display name (e.g. "You", "R. Chen"); names must be plain strings, not objects: use `User.Name.value` or `Owner.Name.value` from the SF response), due (YYYY-MM-DD), state: {value, badgeVariant}, _tone, _status}]` — `_tone` error/warning/info/success, `_status` "Blocker"/"At risk"/"On track"/"Done", `badgeVariant` error/warning/info/success; every row cites its source) · `calloutTitle calloutDescription` (strings) · `ctaPrimaryLabel ctaPrimaryMsg` (strings — `ctaPrimaryMsg` is the first-person prompt for action/sendMessage) · `oppUrl` (string — Lightning URL `https://<myDomain>/lightning/r/Opportunity/<Id>/view`).

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
                  { "definition": "tile/icon", "attributes": { "name": "trending-up", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{headerTitle}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{headerStatus}}", "variant": "warning" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{headerSubtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/meter",
            "attributes": {
              "label": "Exit criteria met",
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
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{gridCaption}}",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                { "key": "item", "header": "Exit criterion", "type": "text" },
                { "key": "owner", "header": "Owner", "type": "avatar" },
                { "key": "due", "header": "Due", "type": "date" },
                { "key": "state", "header": "State", "type": "badge" }
              ],
              "rows": "{{gridRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "warning",
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
# Advance Gap: <Name> — <current stage> → <target>
**Short answer:** <1–2 lines: advances when X and Y; critical path runs through Z>

## Gaps blocking advancement
| # | Gap | Owner (Us/Customer/team) | Blocking (gate/close req) | Evidence (source+date) |

## Already in motion
- <underway items + expected landing — don't re-ask>

## The path
1. <action — who — by when> (unblocks #n)
   Critical path ~<N> weeks → earliest credible close <date> (flag if after CloseDate)

## Suggested SFDC updates
- NextStep → "<the #1 action>" · CloseDate → <if path math says current date isn't credible>
[Apply with `update-opportunity`, or manually if read-only.]
```
