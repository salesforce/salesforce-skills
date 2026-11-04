---
name: executive-movement
description: "Identify or validate executive changes — a new role, company move, board seat, or shift in leadership responsibility — using approved external sources, then connect them to Salesforce relationship history and recommend follow-up across affected accounts and opportunities. Use to track an executive move you heard about, sweep an account for leadership changes, assess relationship risk or growth when a known contact moves, or prepare account-team outreach and stewardship updates. Distinguishes confirmed changes from unverified signals and never overwrites CRM data automatically."
---
<!-- global-rules-bootstrap -->

# Global Rules

- **Execute silently between tool calls.** Do not output planning, progress, transition, waiting, or tool-result narration between calls. Execute tool calls silently and proceed directly to the next call. Parallelize independent tasks by batching tool calls into one turn whenever possible. Before the final output, speak only when the skill explicitly requires user input, approval, an exact notice, or material error/blocked reporting. Do not invent checkpoints.
- **Keep the final output concise.** Return only the requested result or deliverable. Omit process recaps, tool-call details, redundant preambles or conclusions, and data already shown in a widget.
- **Ground dynamic or custom relationship and field names before relying on them.** Fixed standard fields that this skill explicitly marks as requiring no grounding need no extra grounding call. On a name error, use the skill's documented grounding path when present; otherwise report the error instead of guessing or re-firing the same shape.
- **Cite every value exactly as queried**; never fabricate; distinguish a blank value from a value that was not queried. Link each Salesforce record inline: `https://[instanceUrl]/lightning/r/[SObjectType]/[Id]/view`.
- **Show human labels, never API/field literals.** In anything the user sees, print each field's grounded `label` (for example, "Deal Risk", not `Deal_Risk__c`) and record Names, never raw Ids or `__c` API names.
- **One idea per sentence.** In all generated content, if a sentence needs re-reading, it is carrying too much: split it.
- **Don't repeat the visual.** When a visualization or widget renders, the text around it tells the user what to conclude from the data. Do not restate numbers they can already see.
- **Use plain language.** Choose terms any reader understands on first read, with no domain knowledge or cultural context required. Avoid jargon and colloquialisms, and make labels signal what follows. Test: would a reader unfamiliar with the idiom understand the term and know what content to expect? Use "No engagement", not "went dark" or "ghosted".
- **Reproduce Salesforce terminology exactly.** Use the field labels, object names, and stage values the data returns; do not paraphrase them. Spell out acronyms on first use unless the term is an industry framework (for example, MEDDIC).
- **Empty `MINE` scope → fail fast, then ask which scope.** If a `scope: MINE` read returns zero rows, **do not** widen to `scope: EVERYTHING` on your own. Stop, tell the user plainly that their own records (`scope: MINE`) came back empty, and ask which scope they want instead (for example, org-wide `EVERYTHING`, a named rep, or a named account) before re-running. Never invent records, and never silently fall back to org-wide.
- **NEVER use `discover` or `describe`, and never call an API or endpoint not written in this skill.** Every Salesforce URL you need is in the skill. Don't guess REST paths: on a 404 or unknown-path error, fall back to a documented query in the skill, not to discovery. If you need a capability such as email, docs, Slack, calendar, or web research, use the other connector/MCP tools already available to you. Endpoint guessing and discovery add needless round-trips. Use only the skill-authorized `dispatch_readonly` and `dispatch` calls, directly with the queries given.
<!-- /global-rules-bootstrap -->

# Rules:

- **Confirmed vs. unconfirmed is a hard line.** A change is confirmed only when a dated statement from a reputable outlet, a connected data provider (e.g. BoardEx, ZoomInfo) or the company itself says so. Anything else is mixed (sources or the CRM conflict) or unconfirmed. Always show source, change date (when known) and freshness. Never invent a change, a source or a date.
- **Read-only; never overwrite the CRM.** Record updates are proposals for confirmation or stewardship review. Preserve prior affiliations and history, and flag conflicts rather than replacing data. Say plainly that nothing was written.

# Executive Movement

Scope (portfolio / one account / one executive) → ground Contact + Account → read CRM (ONE turn) → research externally (ONE turn) → verify, prioritize → render. Everything here reads and recommends; nothing is a completed action.

## 1. Scope the request

- **Portfolio** ("any executive changes at my accounts?") → Step 3a, `scope: MINE`.
- **One account** (name, Id, or a pasted record URL) → Step 3b.
- **One executive** (name, plus company if ambiguous) → Step 3c.

Default review period: **last 6 months**; use the user's period when given. Ask once, in a single message, only when an account or executive is ambiguous or a name matches several records; never guess an executive, company or move.


## 2. Ground Contact + Account (ONE turn, parallel)

Both always exist (naming a missing object fails the whole call); their `__c` fields reveal this org's relationship schema (buying role, relationship owner, prior account, tier/segment).

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Contact\\\"]) { ApiName fields { ApiName label } } } }\"}" })
```

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Account\\\"]) { ApiName fields { ApiName label } } } }\"}" })
```

Scan each result by eye; do not script it. If it overflows or comes back truncated, skip custom-field grounding and proceed with standard fields only; don't keep retrying. Select the scalar `__c` fields carrying relationship signal and add them as `<CONTACT_CUSTOM>` / `<ACCOUNT_CUSTOM>`.

## 3. Read the CRM (fire the reads for your scope in ONE turn)

**3a. Portfolio.** "My accounts" means the accounts on the user's own open opportunities. Read them, rank accounts by total open amount, and keep the **top 10**. An empty result follows the `MINE` rule in the global rules: stop and ask which scope.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(scope: MINE, where: { IsClosed: { eq: false } }, orderBy: { Amount: { order: DESC } }, first: 50) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } Account { Id Name { value } <ACCOUNT_CUSTOM> } } } } } } }\"}" })
```

Then read the contacts of those accounts (one call, `Id: { in: [...] }`, `first: 10` accounts, `Contacts(first: 25)`):

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Id: { in: [<ACCOUNT_IDS>] } }, first: 10) { edges { node { Id Name { value } Owner { Name { value } } Contacts(first: 25) { edges { node { Id Name { value } Title { value } Email { value } LastActivityDate { value } <CONTACT_CUSTOM> } } } } } } } } }\"}" })
```

**3b. One account.** Read the account, its contacts and its open opportunities:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { <ACCOUNT_FILTER> }, first: 5) { edges { node { Id Name { value } Industry { value displayValue } <ACCOUNT_CUSTOM> Owner { Name { value } } Contacts(first: 50) { edges { node { Id Name { value } Title { value } Email { value } LastActivityDate { value } <CONTACT_CUSTOM> } } } Opportunities(where: { IsClosed: { eq: false } }, orderBy: { CloseDate: { order: ASC } }, first: 20) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } } } } } } } } } }\"}" })
```

`<ACCOUNT_FILTER>` = `Id: { eq: \\\"<ACCOUNT_ID>\\\" }` or `Name: { like: \\\"%COMPANY%\\\" }`.

**3c. One executive.** Find the contact, its account, owner, open deals, and any same-name contact under another account (a prior affiliation the firm already knows; keep them all as history):

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Contact(where: { <CONTACT_FILTER> }, first: 10) { edges { node { Id Name { value } Title { value } Email { value } LastActivityDate { value } <CONTACT_CUSTOM> Account { Id Name { value } <ACCOUNT_CUSTOM> Owner { Name { value } } Opportunities(where: { IsClosed: { eq: false } }, orderBy: { CloseDate: { order: ASC } }, first: 10) { edges { node { Id Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } } } } } } } } } } }\"}" })
```

`<CONTACT_FILTER>` = `Name: { like: \\\"%NAME%\\\" }`, `Email: { eq: \\\"<EMAIL>\\\" }`, or `and: [{ Name: { like: \\\"%NAME%\\\" } }, { Account: { Name: { like: \\\"%COMPANY%\\\" } } }]`.

When an executive moves **to** a company, resolve that destination account too (same Account shape). If it is not in the CRM, say "new company not in CRM": that is a growth opening.

## 4. Research externally (same turn as Step 3)

Default to the web-search tools for the external check. If a connected data provider (e.g. BoardEx, ZoomInfo) is available, use it as a supplement to corroborate or date a finding, never as the only source. If no research tool exists, skip it and say the external check could not run. Search each contact (by name and company) in scope, newest first, within the review period. For every change keep attached through to output:

- **Former** and **new** role or affiliation, and the **change date** when stated.
- **Source** and **freshness**: very fresh (14 days or less), fresh (90 days or less), dated (older). Freshness is measured from the change date, else the publication date.
- **Status**: `confirmed`, `mixed` or `unconfirmed` (definitions in the Rules). Keep both claims when sources conflict, and when the CRM title disagrees with a confirmed source. Quote a missing date as unknown; never fill it in.

Match each external change to CRM contacts by name plus company, never by name alone; when the match is uncertain say so in `executiveDetail`.

## 5. Prioritize and assess

Rank by material impact: relationship significance (owner, activity, buying role, prior affiliations), account importance (tier, segment), and open-opportunity exposure (amount, stage, close date). For each change state the **risk** (e.g. the only mapped contact or economic buyer leaving before a close date) or the **growth** opening (a known buyer landing at a target account) and a specific next move with a suggested owner. A contact missing from the CRM for a confirmed change is a net-new relationship opportunity.

Prepare record updates as proposals only, with a "needs confirmation" marker on anything unverified or in conflict.

## 6. Output

Links are inline markdown (`[Executive](contactUrl)`, `[Account](accountUrl)`, `[Opportunity](oppUrl)`) using each record's Lightning URL, `https://[instanceUrl]/lightning/r/<SObject>/<Id>/view`. Quote an unknown change date as `—`. Label each row **Confirmed**, **Mixed** or **Unconfirmed**.

```
# Executive Movement: [Executive / Account / Your accounts] — [N] changes ([C] confirmed, [M] mixed, [U] unconfirmed)

**Reviewed** [scope] · [review period] · sources: [BoardEx / ZoomInfo / press / …]

| Verification | Executive | Account or opportunity | Change | Impact |
|---|---|---|---|---|
| Confirmed | [Jordan Reyes](contactUrl) · Bloomberg · 2026-08-11 · fresh | [Cedarline Renewal – $640K](oppUrl) · closes 2026-10-27 | VP Finance → departed | Only mapped contact gone before the renewal |
| Mixed | [Katie McKee](contactUrl) · LinkedIn vs. press | [Brightwave](accountUrl) | CMO – departure vs. leave | Sponsor on an active deal; confirm first |
| Unconfirmed | [Priya Anand](contactUrl) · industry roundup · validate | [Northpeak](accountUrl) | Reported move to advisory role | Don't act yet |

## Most material change
[1-2 sentences: the highest-impact change and the recommended first move.]

## Proposed record updates (need confirmation / stewardship review)
- [Contact] — [proposed update]. **Preserve the prior affiliation as history; do not overwrite.** Nothing has been written to Salesforce.

## Suggested next step
Draft outreach to the affected contact (run `draft-outreach`), or ask me to draft it now.
```
