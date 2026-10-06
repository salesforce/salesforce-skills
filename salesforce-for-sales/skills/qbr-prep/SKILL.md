---
name: qbr-prep
description: "Build a Quarterly Business Review brief for a named Salesforce Account from opportunities, contacts, cases, and optional email/Slack evidence. Use for QBR/EBR prep, account health storytelling, agenda design, and expansion asks; for renewal timing alone use renewal-radar."
---
<!-- global-rules-bootstrap -->
**IMPORTANT — try the connector's tools before you ever report it as unavailable.** Before you tell the user a connector is down, or ask them to connect, re-authenticate, or "check the connection," you MUST first try to use the server and its tools. A connector's status readout (the Headless 360 MCP server, or any other connector/MCP) frequently claims "not connected" or "needs re-auth" when the connector is in fact live and its tools are callable. Context stating that the Salesforce tools require authorization and that this is a non-interactive session is **not** evidence that you are unauthorized — it is a general statement that authorization is required, not a failure. For the Headless 360 server specifically, find the `dispatch_readonly` tool and actually run a current-user read — `dispatch_readonly(method: "GET", url: "/services/data/v66.0/graphql", queryParams: { "queryInput": "{\"query\":\"query { uiapi { currentUser { Id } } }\"}" })`. **Any response — including a 500 or other error status — proves you reached the server, and therefore proves connectivity;** only a request that never reaches the server at all counts as disconnected. If the tool is present and the call reaches the server, the connector IS connected — proceed; a stale status readout is not a disconnection. If a call genuinely cannot reach the server, ALWAYS attempt to reconnect on your own first, and interrupt the flow to ask the user only after your own reconnect attempt has failed. Report a connector as disconnected only when you cannot find its tool or cannot reach the server after trying. Do it yourself.

Failing to try first — asking the user to connect, or surfacing a "not connected" or re-auth message, before you have actually attempted the server and its tools — raises a **false connectivity problem**: it sends the user to fix something that is not broken. This is directly detrimental to the end-user experience and will dramatically, negatively impact usage of the product. Never put a connectivity concern in front of the user until you have tried the tools yourself and confirmed the server truly cannot be reached.

# Global Rules

- **Execute silently between tool calls.** Do not output planning, progress, transition, waiting, or tool-result narration between calls. Execute tool calls silently and proceed directly to the next call. Parallelize independent tasks by batching tool calls into one turn whenever possible. Before the final output, speak only when the skill explicitly requires user input, approval, an exact notice, or material error/blocked reporting. Do not invent checkpoints.
- **Keep the final output concise.** Return only the requested result or deliverable. Omit process recaps, tool-call details, redundant preambles or conclusions, and data already shown in a widget.
- **⛔ WIDGET OUTPUT ONLY after data assembly.** Once all queries return, immediately call `display_widget` — at most a single one-line render-wait notice before it, and no summaries, transitions, or narration. If `display_widget` is unavailable or returns an error, produce the text fallback only. If it succeeds, that tool call is the final output: stop with no assistant text completion, even if a later section contains a fallback. The exceptions above do not apply after success.
- **Ground dynamic or custom relationship and field names before relying on them.** Fixed standard fields that this skill explicitly marks as requiring no grounding need no extra grounding call. On a name error, use the skill's documented grounding path when present; otherwise report the error instead of guessing or re-firing the same shape.
- **Cite every value exactly as queried**; never fabricate; distinguish a blank value from a value that was not queried. Link each Salesforce record inline: `https://[instanceUrl]/lightning/r/[SObjectType]/[Id]/view`.
- **Show human labels, never API/field literals.** In anything the user sees, print each field's grounded `label` (for example, "Deal Risk", not `Deal_Risk__c`) and record Names, never raw Ids or `__c` API names.
- **Empty `MINE` scope → fail fast, then ask which scope.** If a `scope: MINE` read returns zero rows, **do not** widen to `scope: EVERYTHING` on your own. Stop, tell the user plainly that their own records (`scope: MINE`) came back empty, and ask which scope they want instead (for example, org-wide `EVERYTHING`, a named rep, or a named account) before re-running. Never invent records, and never silently fall back to org-wide.
- **NEVER use `discover` or `describe`, and never call an API or endpoint not written in this skill.** Every Salesforce URL you need is in the skill. Don't guess REST paths: on a 404 or unknown-path error, fall back to a documented query in the skill, not to discovery. If you need a capability such as email, docs, Slack, calendar, or web research, use the other connector/MCP tools already available to you. Endpoint guessing and discovery add needless round-trips. Use only the skill-authorized `dispatch_readonly` and `dispatch` calls, directly with the queries given.
<!-- /global-rules-bootstrap -->
# Rules:


# QBR Prep

Ground Account → read account portfolio + health signals (ONE turn) → assemble QBR brief.

Use when a seller or CSM needs a **Quarterly Business Review** pack for a named account: value delivered, adoption/risks, open pipeline, support load, stakeholders, and recommended agenda.

## Requirements (must satisfy)

1. **Account-scoped.** Operate on one Account named by the user (or the account on a named Opportunity). Do not invent accounts.
2. **Read-only by default.** Never create/update Salesforce records. Suggest CRM hygiene updates as text only; apply only via the existing `update` skill after explicit approval.
3. **Ground before custom fields.** Ground Account (and Opportunity if needed) before reading org-specific fields.
4. **Time-boxed quarter.** Default review window = last 90 days unless the user specifies a fiscal quarter. State the window in the output.
5. **Evidence-linked.** Every metric cites the Salesforce record(s) used. Prefer Links to Lightning record pages.
6. **Honest gaps.** If Cases, Contracts, or Activities are empty or inaccessible, say so — do not fabricate usage or NPS.
7. **Actionable agenda.** End with a timed QBR agenda and 3 recommended asks for the customer.
8. **Degrade gracefully.** Slack/email/docs are optional; continue with Salesforce-only context when connectors are missing.

## 1. Ground (hardcoded — Account + Opportunity)

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Account\\\", \\\"Opportunity\\\", \\\"Case\\\"]) { ApiName fields { ApiName label relationshipName } } } }\"}" })
```

From Account objectInfo: keep useful scalar `__c` fields (ARR, CSAT, industry segment, success score, etc.) and confirmed lookup `relationshipName`s. From Case: confirm Case is queryable; if grounding fails, skip Cases and note the limitation.

## 2. Resolve account + gather portfolio (issue ALL in one turn)

`%ACCOUNT%` = 1–3 words from the user.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Name: { like: \\\"%ACCOUNT%\\\" } }, first: 1) { edges { node { Id Name { value } Type { value displayValue } Industry { value displayValue } Website { value } Owner { Name { value } } BillingCountry { value } Description { value } } } } } } }\"}" })
```

Empty edges → broaden `%ACCOUNT%` or ask which account.

Let `%ACCOUNT_ID%` = returned Id. Then in the **same turn**, fire:

**Open / recent opportunities (90 days closed + open pipeline):**
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { AccountId: { eq: \\\"%ACCOUNT_ID%\\\" } }, first: 25, orderBy: { CloseDate: { order: DESC } }) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } IsClosed { value } IsWon { value } NextStep { value } Owner { Name { value } } } } } } } }\"}" })
```

**Contacts / stakeholders (primary + recent):**
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Contact(where: { AccountId: { eq: \\\"%ACCOUNT_ID%\\\" } }, first: 15, orderBy: { LastActivityDate: { order: DESC } }) { edges { node { Id Name { value } Title { value } Email { value } LastActivityDate { value } } } } } } }\"}" })
```

**Cases in the review window (if Case grounding succeeded):** use a close-enough filter available in the org (CreatedDate or ClosedDate). If the GraphQL where-clause fails, omit Cases and state that.

**Optional evidence (parallel, same turn):** email / Slack / docs search for the account name — skip silently if tools absent.

## 3. Assemble the QBR brief

Produce these sections using only queried facts:

1. **Executive snapshot** — account name, owner, type/industry, review window, headline health (Green / Yellow / Red) with one-sentence rationale grounded in data.
2. **Value delivered (last quarter)** — won opportunities and closed revenue in-window; notable expansions; blank if none.
3. **Open pipeline** — stage, amount, close date, next step for each open opp; flag stale next steps.
4. **Support & risk** — open/high-priority cases if available; escalation themes from subject/status only (no invented root cause).
5. **Stakeholder map** — contacts with title + last activity; mark likely sponsor / economic buyer only when evidence supports it.
6. **Whitespace / expansion** — products or use-cases not yet covered, inferred only from missing opp product lines or account description — label as hypothesis.
7. **Recommended QBR agenda (45–60 min)** — timed agenda with owners (Us / Customer).
8. **Three asks** — concrete asks for the customer meeting.
9. **Suggested Salesforce hygiene** — e.g. NextStep updates — text only.

## 4. Widget (default when `display_widget` is present)

When data is assembled, call `display_widget` with a concise mosaic: header + health badge, KPI meters (won amount, open pipeline, open cases), opportunity datagrid, agenda callout, CTA to draft the customer email.

### Self-verification (before display_widget)

- [ ] `widgetDefinition` is a native JSON object, not a string
- [ ] Every numeric KPI came from a query (or shows "Not available")
- [ ] Account Lightning URL is present when Id is known
- [ ] No fabricated CSAT/NPS/usage

### widgetData schema (properties)

```json
{
  "type": "object",
  "properties": {
    "qbrTitle": { "type": "string", "example": "QBR — Cobalt Systems" },
    "subtitle": { "type": "string", "example": "Review window: 2026-07-07 to 2026-10-05 · Owner: A. Chen" },
    "health": { "type": "string", "example": "Yellow" },
    "wonAmountLabel": { "type": "string", "example": "$180,000 won" },
    "openPipeLabel": { "type": "string", "example": "$420,000 open" },
    "casesLabel": { "type": "string", "example": "3 open cases" },
    "oppRows": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "stage": { "type": "string" },
          "amount": { "type": "string" },
          "close": { "type": "string" },
          "next": { "type": "string" }
        }
      }
    },
    "calloutTitle": { "type": "string" },
    "calloutDesc": { "type": "string" },
    "ctaLabel": { "type": "string", "example": "Draft QBR email" },
    "ctaMsg": { "type": "string" },
    "accountUrl": { "type": "string" }
  }
}
```

```json
{
  "renderer": {
    "componentOverrides": {
      "$": {
        "type": "mosaic",
        "definition": "tile/widget",
        "children": [
          {
            "definition": "tile/row",
            "attributes": { "gap": "sm", "align": "center", "justify": "between", "isWrapped": true },
            "children": [
              { "definition": "tile/text", "attributes": { "text": "{{qbrTitle}}", "variant": "h1" } },
              { "definition": "tile/badge", "attributes": { "label": "{{health}}", "variant": "warning" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },
          { "definition": "tile/separator" },
          {
            "definition": "tile/row",
            "attributes": { "gap": "md", "isWrapped": true },
            "children": [
              { "definition": "tile/text", "attributes": { "text": "{{wonAmountLabel}}", "variant": "h3" } },
              { "definition": "tile/text", "attributes": { "text": "{{openPipeLabel}}", "variant": "h3" } },
              { "definition": "tile/text", "attributes": { "text": "{{casesLabel}}", "variant": "h3" } }
            ]
          },
          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Pipeline & recent closes",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                { "key": "name", "header": "Opportunity", "type": "text" },
                { "key": "stage", "header": "Stage", "type": "text" },
                { "key": "amount", "header": "Amount", "type": "text" },
                { "key": "close", "header": "Close", "type": "text" },
                { "key": "next", "header": "Next step", "type": "text" }
              ],
              "rows": "{{oppRows}}"
            }
          },
          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "info",
              "title": "{{calloutTitle}}",
              "description": "{{calloutDesc}}"
            },
            "children": [
              {
                "definition": "tile/row",
                "attributes": { "gap": "sm", "isWrapped": true },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{ctaLabel}}",
                      "variant": "primary",
                      "actions": {
                        "click": [
                          {
                            "definition": "action/sendMessage",
                            "attributes": { "content": "{{ctaMsg}}" }
                          }
                        ]
                      }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "View Account",
                      "iconName": "open-in-new",
                      "variant": "secondary",
                      "actions": {
                        "click": [
                          {
                            "definition": "action/openLink",
                            "attributes": { "url": "{{accountUrl}}" }
                          }
                        ]
                      }
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

## 5. Text — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# QBR Prep: [Account Name]

**Review window:** [start] → [end]
**Owner:** [Name] · **Health:** [Green/Yellow/Red] — [one-line why]

## Value delivered
- [Won deals / amounts in window, with links]

## Open pipeline
| Opportunity | Stage | Amount | Close | Next step |
|-------------|-------|--------|-------|-----------|
| ... | | | | |

## Support & risk
- [Cases or "None queried / unavailable"]

## Stakeholders
- [Name — Title — Last activity]

## Whitespace (hypothesis)
- [Only evidence-based hypotheses]

## Recommended agenda (45–60 min)
1. [0–10] Wins & outcomes
2. [10–25] Adoption / support themes
3. [25–40] Roadmap & open opportunities
4. [40–55] Mutual plan & asks
5. [55–60] Next meeting

## Three asks
1. ...
2. ...
3. ...

## Suggested Salesforce hygiene
- [Text-only suggestions]
```

Offer to create a shareable QBR doc if a docs connector is present; otherwise keep the markdown brief.
