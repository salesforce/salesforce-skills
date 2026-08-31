---
name: call-follow-up
description: Turn a meeting transcript into a customer follow-up email (email draft) and an internal Slack summary. Use when the user says "follow up on my [company] call", "write the recap for [meeting]", "process this transcript", or pastes a transcript.
model: claude-sonnet-4-6
effort: medium
---
<!-- global-rules-bootstrap -->
# Global Rules

- **Execute silently between tool calls.** Do not output planning, progress, transition, waiting, or tool-result narration between calls. Execute tool calls silently and proceed directly to the next call. Parallelize independent tasks by batching tool calls into one turn whenever possible. Before the final output, speak only when the skill explicitly requires user input, approval, an exact notice, or material error/blocked reporting. Do not invent checkpoints.
- **Keep the final output concise.** Return only the requested result or deliverable. Omit process recaps, tool-call details, redundant preambles or conclusions, and data already shown in a widget.
- **Ground dynamic or custom relationship and field names before relying on them.** Fixed standard fields that this skill explicitly marks as requiring no grounding need no extra grounding call. On a name error, use the skill's documented grounding path when present; otherwise report the error instead of guessing or re-firing the same shape.
- **Cite every value exactly as queried**; never fabricate; distinguish a blank value from a value that was not queried. Link each Salesforce record inline: `https://[instanceUrl]/lightning/r/[SObjectType]/[Id]/view`.
- **Show human labels, never API/field literals.** In anything the user sees, print each field's grounded `label` (for example, "Deal Risk", not `Deal_Risk__c`) and record Names, never raw Ids or `__c` API names.
- **Empty `MINE` scope → fail fast, then ask which scope.** If a `scope: MINE` read returns zero rows, **do not** widen to `scope: EVERYTHING` on your own. Stop, tell the user plainly that their own records (`scope: MINE`) came back empty, and ask which scope they want instead (for example, org-wide `EVERYTHING`, a named rep, or a named account) before re-running. Never invent records, and never silently fall back to org-wide.
- **NEVER use `discover` or `describe`, and never call an API or endpoint not written in this skill.** Every Salesforce URL you need is in the skill. Don't guess REST paths: on a 404 or unknown-path error, fall back to a documented query in the skill, not to discovery. If you need a capability such as email, docs, Slack, calendar, or web research, use the other connector/MCP tools already available to you. Endpoint guessing and discovery add needless round-trips. Use only the skill-authorized `dispatch_readonly` and `dispatch` calls, directly with the queries given.
- **NEVER assume the MCP connector status is accurate without checking first**; MCP connector status often incorrectly reports that it is not connected or needs to re auth. ALWAYS check this on your own before surfacing to the user for action. ALWAYS attempt to reconnect on your own before interrupting the flow to ask the user to do it. Do it yourself.

# Rules:

- Gather thorough, contextual background before acting. Explain material errors and inference logic explicitly in the final output.

# Call Follow-Up

Get transcript → extract structure deeply → (draft email + draft Slack + SFDC read with historical context, all ONE turn) → output.

**Voice/tone, email signature, and team Slack channel are external knowledge** — infer from org data or ask once. Never invent.

## 1. Get transcript

**If link or "find it":** Use doc search tools (Google Workspace, etc.) to read the doc. Search by account name if needed.
**If pasted:** Use as-is.

Extract: attendees (internal + external), date, account name.

## 2. Extract structure (analyze transcript deeply)

From transcript, pull:
- **Decisions:** anything agreed/confirmed
- **Customer commitments:** what they'll do (send data, loop someone in, review proposal)
- **Our commitments:** what we'll do (send doc, schedule demo, answer question)
- **Open questions:** raised but unresolved
- **Objections/concerns:** pushback
- **Next meeting:** if scheduled
- **Qual signals:** budget/authority/timeline/pain mentions (BANT/MEDDIC default, or infer from org)
- **Specific human moments:** quotes, phrases, analogies customer used — for email personalization
- **Urgency signals:** timeline drivers, consequences of delay, events forcing decision

## 3. Draft email + Slack + read Opp (fire ALL in one turn)

**A. Draft customer email** (under 150 words):
- Thank-you opener (one line, **reference specific human moment from call** — their phrase/analogy/framing, not generic)
- Recap agreed next steps as short bullet list (their commitments + ours)
- Answers/links you committed to — if you don't have yet, `[ATTACH: description]` placeholder
- Propose or confirm next meeting
- Minimal signature: `[User name]` (or infer from org)

Tone: professional, warm, specific to this call (or match voice from org data). Create as email draft to external attendees. **Do not send.**

**B. Draft Slack summary** for team channel (ask which if not specified):
```
*[Account] - [Call type] - [Date]*
Stage: [Opp stage] $[Amount]
Attendees: [names]

*TL;DR:* [one sentence on where deal is]

*Key points:*
• [decision/signal]
• ...

*Risks / objections:*
• [concern raised]
• [flag urgency gaps: "No urgency anchor beyond X — timeline TBD" if no forcing event/deadline surfaced]

*Next steps:*
• [ ] Us: [commitment] - [owner] by [date]
• [ ] Them: [commitment]

*SFDC updates needed:* [stage change / next step / amount]
```

Post as draft message (or output if Slack draft unavailable — user copies in).

**C. Read SFDC context** (to fill Slack summary, check for existing account/opps, propose updates):

Ground Opportunity + Account first (hardcoded — both always exist):
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Opportunity\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })

dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Account\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

Then read **account + all opps (open + closed/historical)** by account name (1–2 word `%NAME%`):
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Name: { like: \\\"%NAME%\\\" } }, first: 1) { edges { node { Id Name { value } <ACCOUNT_CUSTOM> Owner { Name { value } } } } } } } }\"}" })

dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT Id, Name, StageName, Amount, CloseDate, IsClosed, IsWon, NextStep FROM Opportunity WHERE Account.Name LIKE '%ACCOUNTNAME%' ORDER BY CloseDate DESC LIMIT 50" })
```

Insert `<ACCOUNT_CUSTOM>` = confirmed scalar `__c { value }` fields from Account grounding. Insert `<OPP_CUSTOM>` = confirmed scalar `__c { value }` fields from Opportunity grounding if using GraphQL for opps.

**Historical context matters:** If no active opp found, note closed/dead opps exist — shows account is known, prevents duplicate account creation, surfaces prior relationship context.

Empty account match → broaden `%…%` or infer account doesn't exist yet in CRM (propose creation).

**If system errors (500, timeout, auth):** Log explicitly in output, explain what you inferred and why (e.g., "User lookup failed 500, inferring [name] as owner from transcript").

**Fire A, B, C as tool calls in ONE turn** (email draft, Slack draft, Account+Opp ground + reads) — they're independent except Slack needs Opp data, so issue grounds + reads together, drafts in parallel.

## 4. SFDC update checklist

Propose changes based on call (confirm before writing via `update-opportunity` or `log-activity`). On read-only connector, output as checklist.

**CRM hygiene checks:**
- If **account exists** (found in Step 3C historical search), note existing AccountId — don't create duplicate
- If **no account found**, propose Account creation with fields from transcript
- If **old closed/dead opps exist**, surface that prior relationship context in output

**Proposed updates:**
- NextStep → "[suggested from call]"
- StageName → [if progression warranted]
- Amount → [if discussed]
- CloseDate → [if timeline shifted]
- Log Activity: "[Call type] - [one-line summary]"

## 5. Output

```
# Call Follow-Up: [Account] - [Date]

## Customer Email
✉️ Drafted in email to [recipients]: [draft link]
---
[email body preview]
---

## Internal Summary
💬 Drafted to [#channel]
---
[slack message preview]
---

## Update Salesforce (via `log-activity` / `update-opportunity`, or manually)
- [ ] NextStep: "[value]"
- [ ] [other fields]
- [ ] Log Activity

## Our Commitments (don't drop these)
- [ ] [commitment] - by [date]
```
