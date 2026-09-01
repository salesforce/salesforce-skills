---
name: customer-voice
description: Surface what customers are actually saying - pull direct quotes from call transcripts and email threads on a topic, across your accounts. Use when the user asks "what are customers saying about [topic]", "what are people saying about [X]", "customer feedback on [topic]", "pull quotes on [objection/feature/competitor]", "voice of customer on [X]", "what feedback are we getting", or "what's coming up in calls". This skill finds CUSTOMER quotes and feedback, grouped by theme.
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
# Customer Voice

Direct customer quotes on a topic, from transcripts + email threads across your accounts — verbatim with attribution, not summaries. Salesforce only *scopes* the search: which accounts, and who's internal vs. customer. Context (all in ONE turn) → search docs/email → extract quotes → group by theme.

Inputs: **topic** (theme/objection/feature/competitor, or open-ended "what's coming up"); **scope** (my accounts default / team / named list); **period** (30d default).

## 1. Context — 3 independent SF reads + the searches, all in ONE turn

These don't depend on each other, so fire them together (with the doc/email searches below). No schema grounding — fields are fixed.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(scope: MINE, first: 200) { edges { node { Name { value } Website { value } Owner { Name { value } } } } } } } }\"}" })

dispatch_readonly(method: "GET", url: "/services/data/v66.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { currentUser { Email { value } } } }\"}" })

dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT Name FROM Organization LIMIT 1" })
```

- **Accounts** = the domains/names to scope the search to (team/named-list scope: drop `scope: MINE`, filter on owner/list).
- **Internal domain** = the part after `@` in `currentUser.Email`; **org name** = `Organization.Name`. Anyone speaking from that domain/company is **internal** — everyone else is the customer.

## 2. Search sources (same turn — skip silently if a connector is absent)

- **docs**: transcripts / notes / meeting docs in the period, in account-named folders (team scope → team-shared too).
- **email**: threads in the period to/from the scoped account domains.

## 3. Extract quotes (strict — customer-only, on-topic, verbatim)

Per transcript/thread, pull passages where the **customer** (not your domain/org) speaks on the topic: verbatim quote (1–3 sentences) · speaker name + title + account · date + source · one-line context. Paraphrase is NOT voice-of-customer. Open-ended topic → cluster by theme, return top 3–5 by frequency.

## 4. Output

```
# Customer Voice: "<Topic>" — <N> quotes from <M> accounts (<period>)

## <Theme>
> "<Verbatim quote>"
> — <Name>, <Title> @ <Account> — <Date> (<source link>)

## Accounts represented
<Account> (<N>), …

## Gaps
- <N> accounts in scope had no transcript/thread in period
- Topic not mentioned in: <accounts>
```
