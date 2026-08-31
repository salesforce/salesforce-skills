---
name: schedule-meeting
description: Find a time, draft the invite, and book the meeting - then log it to Salesforce as an Event on the right account and opportunity. Use when the user says "schedule a follow-up with [contact]", "schedule a meeting", "book the demo with [account]", "find time with [name]", "set up a call", "get a meeting on the calendar", "book time with [contact]", or "arrange a follow-up". This skill BOOKS meetings via calendar.
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
# Goal:
Find a time, draft or book the invite, and log the meeting to Salesforce as an `Event` on the right account/opportunity — so activity history stays honest.

# Audience:
Sales reps booking a meeting. This skill **BOOKS via calendar** and **WRITES an Event** to Salesforce; the confirmation gates and correctness matter more than speed.

# Rules:

- The proposed slots, the invite preview, and the final confirmation block are the only required output.
- **Two confirmation gates, both explicit-yes:** (1) before creating any calendar invite / sending any email, show the full invite (title, time, attendees, agenda); (2) before writing the SFDC Event. Never book or write without showing it first.
- Source attendee emails from SFDC first; if a contact has no address on record, recover it from the email connector, and only if neither has it, say so.
- **Calendar and email are capabilities, not Salesforce APIs** — use the calendar/email connector or MCP tools already available to you for availability, invites, drafts, and recovering an attendee address SFDC lacks. Only the `Event` log and the record reads go through `dispatch`/`dispatch_readonly`.

# Schedule Meeting

**Inputs:** who (contact name(s) or "the [account] team") · what (demo, follow-up, QBR, security review…) · when (a window like "next week" or specific constraints) · duration (default 30 min; 60 for demos/QBRs).

## 1. Ground Event fields

Ground `Event` ObjectInfo for this org's required fields and picklist values before writing — write to grounded names, never guessed ones.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Event\\\"]) { fields { ApiName label dataType } } } }\"}" })
```

## 2. Resolve people + records (one turn)

Fire both reads together via UI-API GraphQL at `v65.0` — the account's matching contacts (via the Account's `Contacts` child span, narrowed by attendee name) and its open opps (take each picklist's `{ value displayValue }`):

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Id: { eq: \\\"[account id]\\\" } }, first: 1) { edges { node { Id Name { value } Contacts(where: { Name: { like: \\\"%[name]%\\\" } }, first: 10) { edges { node { Id Name { value } Email { value } Title { value } } } } } } } } } }\"}" })

dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { AccountId: { eq: \\\"[account id]\\\" }, IsClosed: { eq: false } }, first: 50) { edges { node { Id Name { value } StageName { value displayValue } } } } } } }\"}" })
```

Get attendee emails from SFDC; if a contact record has no address, recover it from the email connector. If neither has it, say so — never invent one. If multiple open opps, ask which one this meeting belongs to.

## 3. Find the time

Pull your calendar availability in the requested window (calendar tool). Propose 2–3 specific slots, avoiding existing meeting blocks and respecting working hours. Honor any stated customer preferences (timezone, no Fridays).

## 4. Draft or book — confirm which first

- **Propose-by-email:** draft an email offering the slots (use `voice-profile` tone if configured). Lands as a draft, never sent automatically.
- **Direct invite:** create the calendar event (attendees, agenda in the description, video link if the calendar adds one). Show the full invite and get an explicit yes **before** creating it.

## 5. Log it in Salesforce

After the invite exists, create the matching SFDC `Event` — confirm before writing:

```
dispatch(method: "POST", url: "/services/data/v63.0/sobjects/Event",
         body: { "Subject": "[title]", "StartDateTime": "[ISO8601]", "EndDateTime": "[ISO8601]", "WhoId": "[primary contact Id]", "WhatId": "[opportunity or account Id]" })
```

On a read-only connector, output the Event details as a paste-ready block instead of writing. Then confirm:

```
✅ Booked: [Title] - [date/time]
Calendar: [event created / draft email in email]
Salesforce: Event logged on [Account] / [Opportunity] - [link]
```
