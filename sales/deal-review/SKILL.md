---
name: deal-review
description: Deep-dive on a single opportunity - signal-adjusted health score, risks, gaps in qualification, and recommended next actions. Use when the user asks "review the [account] deal", "deal review on [opp]", "is [opp] going to close", or "what's the risk on [deal]".
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


# Deal Review

Ground → (read + evidence searches, all in ONE turn) → analyze.

## 1. Ground (hardcoded — Opportunity only)

Ground **only Opportunity** — it always exists (naming a missing object fails the whole call). Its fields + childRelationships reveal this org's risk/stakeholder schema; don't assume object names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

Step 1 is the authority on names — use exact strings from it, never guess. From the result, note: (a) scalar `__c` fields (health, stage, next-step, exec-sponsor, forecast, etc.) — take their `{ value }` **and keep each field's `label`**; (b) each lookup field's exact `relationshipName` (the `__r` name) to span for a related record's Name; (c) each child `relationshipName`. **Build an ApiName→label map now and use the `label` in ALL output** (e.g. render `Executive_Sponsor__c` as "Executive Sponsor", `Health_Score__c` as "Health Score") — never print a `__c` API name to the user.

## 2. Read (fill from step 1)

`%DEALNAME%` = 1–2 words. **Reference-field rules (this avoids the retry loop):**
- A scalar/`__c` field → `Field__c { value }`. `displayValue` is null for Id fields here — don't rely on it.
- To get a **related record's name**, span via the exact `relationshipName` from Step 1: `<relationshipName> { Name { value } }`. Do NOT append `{ ... }` to the raw `Id`/`__c` field — that fails; spanning uses the `__r`/relationship name.
- Only span relationships Step 1 actually returned. If a lookup has no usable relationshipName, take its `__c { value }` (the Id) and move on — **do not retry**.

Insert `<OPP_CUSTOM>` = confirmed scalar `__c { value }` fields; `<REL_BLOCKS>` = one block per confirmed relationship (`<relationshipName> { Name { value } … }` for a lookup; `<childRelationshipName> { edges { node { … } } }` for a child). Standard fields + `OpportunityContactRoles` always work.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { Name: { like: \\\"%DEALNAME%\\\" } }, orderBy: { CloseDate: { order: DESC } }, first: 1) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } CreatedDate { value } Type { value displayValue } Probability { value } ForecastCategory { value } NextStep { value } LastActivityDate { value } <OPP_CUSTOM> Account { Name { value } } Owner { Name { value } } <REL_BLOCKS> OpportunityContactRoles { edges { node { Role { value } IsPrimary { value } Contact { Name { value } Title { value } } } } } Tasks(first: 15, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Subject { value } ActivityDate { value } Status { value } Description { value } Type { value } } } } Events(first: 10, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Subject { value } ActivityDate { value } Description { value } } } } } } } } } }\"}" })
```

Empty `edges` → broaden `%…%`. The `orderBy: { CloseDate: { order: DESC } }` makes `first: 1` favor the active/current deal on a multi-match name (not an arbitrary stale closed-won). `Task.Description`/`Type` carry the "what happened" detail behind each timeline row. The `Tasks`/`Events` children carry the activity timeline — read them as **three separate states** (see next paragraph); a scalar `LastActivityDate` alone can't distinguish an open task or a future meeting from a completed touch.

**Deal history (always query this).** To ground *whether the CloseDate actually moved* and detect same-day stage jumps — pull this opp's field-change history (SOQL only; `OpportunityFieldHistory` has no GraphQL form). `<ID>` = the Id from the read above, or use `%DEALNAME%` in a WHERE clause with Name LIKE if the Id isn't yet available:
```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT Field, OldValue, NewValue, CreatedDate FROM OpportunityFieldHistory WHERE OpportunityId = '<ID>' AND Field IN ('CloseDate','StageName','Amount') ORDER BY CreatedDate DESC" })
```
CloseDate rows dated *this* cycle = real slippage (penalize); no recent CloseDate change with the current date holding = inherited history, not a current slip (context only). Same-day StageName jumps = signals to surface. Empty/unavailable → don't infer a slip.

## 2b. Evidence (run IN PARALLEL with step 2 — same turn, issue all at once)

**Issue step 2 and all of step 2b as tool calls in a single turn — do not wait for the SF read to return before firing the searches.** They're independent (searches key on the deal/account name, not the SF result), so batch them together. Keyed on the deal/account name:
- **email**: threads with the account/contacts, last ~60d → last exchange date + topic, objections, commitments
- **docs**: recent transcripts/notes on the account → decisions, objections, competitor mentions
- **slack**: internal mentions → deal-desk/exec/concerns

Use whatever email/doc/Slack search tools are available. If none are present, skip silently (SF-only is fine). Never block on these; cite source + date for anything you use.

## 3. Analyze (cite every value/source; invent nothing)

Signal-adjust from SFDC `Probability`, only on a shown trigger:
`+5` ≥3 contact roles · `+10` economic buyer role · `+10` champion engaged (multiple completed touches, email/Task) · `+10` mutual close plan / exec engaged (email/doc) · `−10` >14d since last **completed** touch · `−15` CloseDate past · `−15` open blocking risk · `−10` open High-sev risk · `−10` single-threaded · `−10` champion quiet 14d+ (email) · `−10` competitor named (doc/email) · `−10` current-cycle CloseDate slip (see guardrail). Floor 5, ceil 95. Show the math.

**Activity — three states, never conflated** (read from the Tasks/Events children, not `LastActivityDate` alone): *completed* = Task `Status` Completed or past-dated Event; *open* = Task not yet Completed; *scheduled* = any Task/Event dated after today. "Days dark", the `−10 >14d`, and `−10 champion quiet` triggers key on the last **completed** touch only — a future QBR or an open task is momentum, not a completed touch, and never resets the clock or counts as one. Surface open tasks and scheduled meetings as positive momentum, not silence.

**Match every adjustment to shown state; current-cycle only.** Apply a trigger only if the data you pulled shows it. Apply the slip penalty only when the deal-history query above shows the *current* CloseDate moved this cycle — a PushCount / stage-cycling count inherited from earlier cycles, with the current date holding, is **not** current slippage; don't penalize it (note it as historical context instead). Distinguish a confirmed blocking risk from one that's merely stale or unknown — don't score both as equally blocking.

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

If `display_widget` is available (Cowork/desktop/web), the widget IS the output; produce the text section below only as the fallback when `display_widget` is unavailable (e.g. a terminal). The widget template is embedded below — a widget-definition envelope whose leaf values carry {{token}} placeholders. Resolve every {{token}} to a literal (no {{…}}/{!…} left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a {{token}} becomes the typed literal — arrays stay arrays, numbers stay numbers; a {{token}} inside a larger string is interpolated as text. Tokens: `dealName headerStatus` (page header) · `healthLine` (one muted caption under the header — the composite health read: a `🟢/🟡/🔴` marker, `Health <X>/10`, and a one-clause verdict, e.g. "🟡 Health 6/10 — strong economics, but an unstarted paper process risks the close"; the emoji + text carry the state, never color alone) · `recMove recMoveDetail recMoveMsg recMoveChampMsg recMoveOpenMsg` (recommended-callout block) · `kpiAmountNum kpiAmountSub kpiStageNum kpiStageSub kpiCloseNum kpiCloseUnit kpiCloseSub kpiQualNum kpiQualUnit kpiQualSub` (KPI stat strip) · `qualBadge qualCaption qualRows` (MEDDIC datagrid — `qualRows` is an array, one per criterion: `{crit, state:{value,badgeVariant}, detail, _tone, _status}`) · `dealAccount dealStage dealTiming dealAmount dealUrl blockerTitle blockerDesc` (deal card).

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
                  { "definition": "tile/icon", "attributes": { "name": "briefcase", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{dealName}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{headerStatus}}", "variant": "error" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{healthLine}}", "variant": "caption", "color": "muted" } },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "recommended",
              "eyebrow": "THE PLAY",
              "title": "{{recMove}}",
              "description": "{{recMoveDetail}}"
            },
            "children": [
              {
                "definition": "tile/row",
                "attributes": { "gap": "sm", "align": "center", "isWrapped": true },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "Draft legal push",
                      "variant": "primary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{recMoveMsg}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "Reconfirm champion",
                      "variant": "secondary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{recMoveChampMsg}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "Open deal",
                      "variant": "secondary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{recMoveOpenMsg}}" } }
                    }
                  }
                ]
              }
            ]
          },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "sm", "align": "stretch", "isWrapped": true },
            "children": [
              {
                "definition": "tile/card",
                "attributes": { "variant": "outlined", "padding": "md", "width": "stretch", "minWidth": "md" },
                "children": [
                  {
                    "definition": "tile/column",
                    "attributes": { "gap": "xs" },
                    "children": [
                      { "definition": "tile/text", "attributes": { "text": "AMOUNT", "variant": "eyebrow", "color": "muted" } },
                      {
                        "definition": "tile/row",
                        "attributes": { "gap": "xs", "align": "baseline" },
                        "children": [
                          { "definition": "tile/text", "attributes": { "text": "{{kpiAmountNum}}", "variant": "display" } }
                        ]
                      },
                      { "definition": "tile/text", "attributes": { "text": "{{kpiAmountSub}}", "variant": "caption", "color": "muted" } }
                    ]
                  }
                ]
              },
              {
                "definition": "tile/card",
                "attributes": { "variant": "outlined", "padding": "md", "width": "stretch", "minWidth": "md" },
                "children": [
                  {
                    "definition": "tile/column",
                    "attributes": { "gap": "xs" },
                    "children": [
                      { "definition": "tile/text", "attributes": { "text": "STAGE", "variant": "eyebrow", "color": "muted" } },
                      {
                        "definition": "tile/row",
                        "attributes": { "gap": "xs", "align": "baseline", "isWrapped": true },
                        "children": [
                          { "definition": "tile/text", "attributes": { "text": "{{kpiStageNum}}", "variant": "display" } },
                          { "definition": "tile/text", "attributes": { "text": "{{kpiStageLabel}}", "variant": "section-title", "color": "muted" } }
                        ]
                      },
                      { "definition": "tile/text", "attributes": { "text": "{{kpiStageSub}}", "variant": "caption", "color": "muted" } }
                    ]
                  }
                ]
              },
              {
                "definition": "tile/card",
                "attributes": { "variant": "outlined", "padding": "md", "width": "stretch", "minWidth": "md" },
                "children": [
                  {
                    "definition": "tile/column",
                    "attributes": { "gap": "xs" },
                    "children": [
                      { "definition": "tile/text", "attributes": { "text": "CLOSE", "variant": "eyebrow", "color": "muted" } },
                      {
                        "definition": "tile/row",
                        "attributes": { "gap": "xs", "align": "baseline" },
                        "children": [
                          { "definition": "tile/text", "attributes": { "text": "{{kpiCloseNum}}", "variant": "display", "color": "error" } },
                          { "definition": "tile/text", "attributes": { "text": "{{kpiCloseUnit}}", "variant": "section-title", "color": "muted" } }
                        ]
                      },
                      { "definition": "tile/text", "attributes": { "text": "{{kpiCloseSub}}", "variant": "caption", "color": "muted" } }
                    ]
                  }
                ]
              },
              {
                "definition": "tile/card",
                "attributes": { "variant": "outlined", "padding": "md", "width": "stretch", "minWidth": "md" },
                "children": [
                  {
                    "definition": "tile/column",
                    "attributes": { "gap": "xs" },
                    "children": [
                      { "definition": "tile/text", "attributes": { "text": "QUALIFICATION", "variant": "eyebrow", "color": "muted" } },
                      {
                        "definition": "tile/row",
                        "attributes": { "gap": "xs", "align": "baseline" },
                        "children": [
                          { "definition": "tile/text", "attributes": { "text": "{{kpiQualNum}}", "variant": "display", "color": "warning" } },
                          { "definition": "tile/text", "attributes": { "text": "{{kpiQualUnit}}", "variant": "section-title", "color": "muted" } }
                        ]
                      },
                      { "definition": "tile/text", "attributes": { "text": "{{kpiQualSub}}", "variant": "caption", "color": "muted" } }
                    ]
                  }
                ]
              }
            ]
          },

          { "definition": "tile/separator" },

          {
            "definition": "tile/row",
            "attributes": { "gap": "sm", "align": "center", "justify": "between", "isWrapped": true },
            "children": [
              { "definition": "tile/text", "attributes": { "text": "MEDDIC qualification", "variant": "section-title" } },
              { "definition": "tile/badge", "attributes": { "label": "{{qualBadge}}", "variant": "warning" } }
            ]
          },
          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "{{qualCaption}}",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                { "key": "crit", "header": "Criterion", "type": "text" },
                { "key": "state", "header": "State", "type": "badge" },
                { "key": "detail", "header": "Detail", "type": "text" }
              ],
              "rows": "{{qualRows}}"
            }
          },

          { "definition": "tile/separator" },

          {
            "definition": "tile/card",
            "attributes": { "variant": "outlined", "padding": "md" },
            "children": [
              {
                "definition": "tile/column",
                "attributes": { "gap": "md" },
                "children": [
                  {
                    "definition": "tile/row",
                    "attributes": { "gap": "md", "align": "start", "justify": "between", "isWrapped": true },
                    "children": [
                      {
                        "definition": "tile/column",
                        "attributes": { "gap": "xs", "width": "stretch" },
                        "children": [
                          { "definition": "tile/text", "attributes": { "text": "{{dealAccount}}", "variant": "h4", "weight": "semibold" } },
                          {
                            "definition": "tile/row",
                            "attributes": { "gap": "xs", "align": "center", "isWrapped": true },
                            "children": [
                              { "definition": "tile/badge", "attributes": { "label": "{{dealStage}}", "variant": "secondary" } },
                              { "definition": "tile/badge", "attributes": { "label": "{{dealTiming}}", "variant": "error" } }
                            ]
                          }
                        ]
                      },
                      {
                        "definition": "tile/column",
                        "attributes": { "gap": "xs", "align": "end" },
                        "children": [
                          { "definition": "tile/text", "attributes": { "text": "{{dealAmount}}", "variant": "h3", "weight": "bold" } },
                          {
                            "definition": "tile/button",
                            "attributes": {
                              "label": "View in Salesforce",
                              "variant": "secondary",
                              "onClick": { "definition": "action/openLink", "attributes": { "url": "{{dealUrl}}" } }
                            }
                          }
                        ]
                      }
                    ]
                  },

                  { "definition": "tile/separator" },

                  {
                    "definition": "tile/callout",
                    "attributes": { "variant": "error", "title": "{{blockerTitle}}", "description": "{{blockerDesc}}" }
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

```
# Deal Review: <Name> — <Account>
## Health: 🟢/🟡/🔴 <X>/10 — <one-sentence verdict>
<Stage displayValue> · <Amount displayValue> · <Type> · close <CloseDate> · age <days since CreatedDate>d
Prob: SFDC <P>% → adjusted <Y>% (<±adj: evidence>…). If evidence is genuinely two-sided, say so rather than forcing a single precise number.

## Qualification (BANT/MEDDIC)
| Element | Status | Evidence |
|---|---|---|
| Budget | ✅/⚠️/❌ | <$X confirmed <date>, source / gap> |
| Authority | ✅/⚠️/❌ | <EB name, role, source / gap> |
| Need | ✅/⚠️/❌ | <driver, source / gap> |
| Timeline | ✅/⚠️/❌ | <customer close driver, source / gap> |
Cite the source per row; ❌ only when truly not pulled.

## Strengths
- 1–3 evidenced positives (confirmed BANT, prior wins, engaged champion, momentum) — always populate when present; don't drop positives while keeping risks.

## Activity Timeline
- <date> · <source> · <subject / what happened>  (newest first, from the Tasks/Events children)
- Last **completed** touch: <N>d ago · open tasks: <subject, due> · scheduled: <meeting, date>
Keep the three states separate; a scheduled/open item is not a completed touch.

## Risks
- <Primary confirmed gate (Sev, Status, owner)>; then each open risk <Name (Sev, Status, blocking?)>. Mark confirmed-blocking vs stale/unknown distinctly.

## Missing
- Qualification gaps, single-threading, no MAP, unnamed competitor, missing exec sponsor, procurement owner — whatever affects closure.

## Stakeholders
- <Name (Title, Role)>…

## Stage check
- <matches / ahead of evidence — why>

## Evidence
- <key email/doc/Slack signals w/ date+source, or "CRM only — email/docs/Slack not connected">

## Recommended Next Actions
1. 2–4 actions, each tied to a named gap/risk above with an owner or date

## Suggested SFDC updates
- StageName/NextStep/CloseDate if evidence differs from the record (apply with `update-opportunity`, or note if read-only)
```
