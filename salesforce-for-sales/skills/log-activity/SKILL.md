---
name: log-activity
description: Log a call, meeting, or email exchange to Salesforce after the fact as a completed Task on the right account, opportunity, and contact - drafted from your description or a transcript, confirmed before anything is written. Use when the user says "log this call", "log my meeting with [account]", "log that I emailed [contact]", "track this conversation in Salesforce", or "what activities are logged on [account]".
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

- Resolve to ONE account before the deep read. When the name is ambiguous, ask the user to pick — don't probe candidates or guess.

# Log Activity

Ground + resolve (ONE turn, batched) → draft → confirm → write → report. Also answers the read side: "what's logged on [account]."

## 1. Write access (no call)

Needs a create-access connector. Read-only only → skip straight to drafting and hand the user paste-ready text instead of writing.

## 2. Ground Task + resolve records (batch — fire both in the SAME turn)

Independent — issue both in one turn, not sequentially.

**Ground Task** (root object, always exists — reveals Type's real picklist values and any custom required fields):

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(objectInfoInputs: [{apiName: \\\"Task\\\", recordTypeIDs: [\\\"012000000000000AAA\\\"]}]) { fields { ApiName label dataType required ... on PicklistField { picklistValuesByRecordTypeIDs { picklistValues { value label } } } } } } }\"}" })
```

**Resolve the account** (standard fields only, no grounding needed) — nest its open Opportunities and Contacts as children in the same call, not a separate round-trip:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Name: { like: \\\"%ACCOUNT%\\\" } }, first: 3) { edges { node { Id Name { value } Opportunities(where: { IsClosed: { eq: false } }, first: 10, orderBy: { CloseDate: { order: ASC } }) { edges { node { Id Name { value } StageName { value displayValue } CloseDate { value } } } } Contacts(first: 20) { edges { node { Id Name { value } Title { value } Email { value } } } } } } } } } }\"}" })
```

Skip the resolve call if the user already gave an unambiguous account/opp/contact Id. Multiple account matches, or an ambiguous opp/contact within one → ask, never guess which one a call belongs to. From Step 1's result, note Type's valid values and any `required` custom field on Task — those go in the write.

## 3. Draft (prompt only)

- **Subject:** "[Type]: [topic]" (e.g. "Call: pricing and security review timeline")
- **Type:** Call, Meeting, or Email — must match a value Step 2 confirmed
- **Date:** when it happened (default today)
- **Description:** 3-6 bullets — discussed, agreed, their commitments, ours. From the transcript if given, else the user's words.
- **Related to:** WhatId = the resolved Opportunity (or Account if no deal), WhoId = the resolved Contact
- **Follow-up:** if a clear next step came out of it, offer to also set the opportunity's NextStep (hand to `update-opportunity`)

## 4. Confirm, then write

Show before writing, always:

```
📋 Draft Activity Log

Subject: [subject]
Type: [Call/Meeting/Email]
Date: [date]
Related Account: [account name]
Related Opportunity: [opp name + stage + close date, or —]
Related Contact: [contact name]

Description:
• [bullet]…

Ready to log this to Salesforce?
```

Only after explicit yes:

```
dispatch(method: "POST", url: "/services/data/v63.0/sobjects/Task",
  body: { "Subject": "[subject]", "Status": "Completed", "ActivityDate": "[YYYY-MM-DD]", "Type": "[value]", "Description": "[bullets]", "WhatId": "[Opportunity or Account Id]", "WhoId": "[Contact Id]" <TASK_CUSTOM> })
```

`<TASK_CUSTOM>` = any Step 2 `required` custom fields on Task, filled from the draft/user. Creation fails (validation rule, required field) → report the exact error and output the entry as paste-ready text instead. Don't retry blind.

## 5. Report (no re-fetch — build from what you already have)

The create response returns the new Id; you already know every field you wrote. Don't re-query it back.

```
✅ Logged: "[Subject]" — [Date]
Related to: [Account] / [Opportunity] / [Contact]
Record: https://[instanceUrl]/lightning/r/Task/[returned Id]/view
```

## Read mode — "what's logged on [account/opp]"

Standard fields only, no grounding. Resolve the account (or opportunity, if opp-scoped) by name, nesting its Tasks as children — `Account.Tasks` / `Opportunity.Tasks` are standard child relationships, so this is one call, not a resolve-then-query chain:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Name: { like: \\\"%ACCOUNT%\\\" } }, first: 1) { edges { node { Id Name { value } Tasks(first: 20, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Subject { value } ActivityDate { value } Type { value } Status { value } Description { value } Owner { Name { value } } } } } } } } } } }\"}" })
```

Swap the root to `Opportunity(where: { Name: { like: \"%OPP%\" } }, first: 1) { edges { node { Tasks(...) {...} } } }` for an opp-scoped ask (same nested block).

Output as a dated list, newest first, one line each; note the last-touch gap if it's longer than 14 days.

## [CUSTOMIZE]

- **Required fields:** Step 2's grounding surfaces org-specific required custom fields on Task automatically — no hardcoded list needed.
- **Event vs Task:** this skill logs completed Tasks. If your org logs meetings as Events instead, switch Step 4's write to create an Event with start/end times from Calendar.
- **Description depth:** default is 3-6 bullets; adjust the target length in Step 3 if your team wants fuller notes.
