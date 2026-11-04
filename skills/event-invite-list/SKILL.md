---
name: event-invite-list
description: "Build a prioritized customer invite list for an event from Salesforce Contact, Account and Opportunity data, ranked by location and ideal-customer-profile fit. Use to plan an event guest list, choose which customers to invite near a city or region, or prioritize contacts by title, segment, revenue or open-opportunity signal."
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

- Resolve inputs BEFORE the read. Event location and the ideal customer profile (ICP) drive both the query filter and the ranking — if either is missing from the prompt, ask once (Step 1) before querying. Don't guess a city or invent an ICP.

# Event Invite List

Inputs (ask if missing) → ground Contact + Account → read Contacts near the location, then Opportunities for those accounts (TWO sequential queries) → score ICP fit → rank → render. Default list size: **10 contacts** unless the prompt specifies a number.

## 1. Inputs (ask once if not in the prompt)

Two inputs drive everything. If either is absent from the prompt, ask for both in a single message, then proceed — don't ask again:

- **Event location** (required) — a city, metro, state, or region. Becomes the mailing-address filter in Step 3.
- **Ideal customer profile** (required) — any mix of: title / role, job function, job level, customer segment, account industry, account size, account revenue, open-opportunity status, opportunity amount or close date, recent activity. Whatever the user gives is the ranking rubric in Step 4.

Also honor an explicit **list size** if given (e.g. "give me 25"); otherwise default to **10**. The ICP itself is the user's to define — infer unstated dimensions from the org's own data only when reasonable, never invent a disqualifier the user didn't state.

## 2. Ground (hardcoded — Contact and Account)

Ground **Contact** and **Account** — both always exist (naming a missing object fails the whole call), and their `__c` fields reveal this org's real segment/industry/revenue/job-level schema, which Step 4 ranks against. Issue these independent requests in the **same tool turn** so they run in **parallel**:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Contact\\\"]) { ApiName fields { ApiName label } } } }\"}" })
```

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Account\\\"]) { ApiName fields { ApiName label } } } }\"}" })
```

**If either overflows** or comes back truncated, skip custom-field grounding and proceed with standard fields only; don't keep retrying.

From each response, select by API name and label the scalar `__c` fields carrying ICP signal (job level, job function, persona, segment, industry, employee band, annual revenue, tier, etc.). Add Contact `__c` fields as `<CONTACT_CUSTOM>` and Account `__c` fields as `<ACCOUNT_CUSTOM>` in the read below. The `Account` and `Owner` spans are standard and hardcoded.

## 3. Read contacts near the location (fill from step 2, TWO sequential dispatches)

**GraphQL doesn't allow Opportunities nested under Account under Contact.** Read in two steps — contacts + accounts first, then opportunities for those account IDs.

### 3a. Read contacts with accounts

`%LOCATION%` filters on the contact's mailing address; use the field the location implies — city → `MailingCity`, state/region → `MailingState`. Insert `<CONTACT_CUSTOM>` and `<ACCOUNT_CUSTOM>` from Step 2. Pull a generous pool (`first: 200`) so Step 4 has room to rank down to the target count.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Contact(where: { <LOCATION_FILTER> }, first: 200) { edges { node { Id Name { value } Title { value } Email { value } Phone { value } MailingCity { value } MailingState { value } LastActivityDate { value } <CONTACT_CUSTOM> Account { Id Name { value } Industry { value displayValue } NumberOfEmployees { value } AnnualRevenue { value displayValue } Type { value } <ACCOUNT_CUSTOM> Owner { Name { value } } } } } } } } }\"}" })
```

`<LOCATION_FILTER>` — build from the Step 1 location:
- City: `MailingCity: { like: \\\"%<CITY>%\\\" }`
- State / region: `MailingState: { like: \\\"%<STATE>%\\\" }`
- Multiple cities in a metro: `or: [{ MailingCity: { like: \\\"%<CITY_A>%\\\" } }, { MailingCity: { like: \\\"%<CITY_B>%\\\" } }]`

Empty `edges` → say "No contacts found near [location]"; broaden the location once (city → surrounding state) only if the user's intent clearly allows it, else ask. Never widen to the whole org unasked. `first: 200` caps the pool — if the location is very broad, say so and ask the user to narrow it rather than silently truncating.

### 3b. Read open opportunities for those accounts

**Skip this step if 3a returned no contacts.** Collect unique Account IDs from 3a, then query their open opportunities. If there are many accounts (50+), batch the query into groups of 50 using `or: [{ AccountId: { eq: \"<ID1>\" } }, ...]`.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Opportunity(where: { and: [{ IsClosed: { eq: false } }, { or: [<ACCOUNT_ID_FILTERS>] }] }, orderBy: { CloseDate: { order: ASC } }, first: 200) { edges { node { Id Name { value } AccountId { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } } } } } } }\"}" })
```

`<ACCOUNT_ID_FILTERS>` is a comma-separated list: `{ AccountId: { eq: \"<ID1>\" } }, { AccountId: { eq: \"<ID2>\" } }, ...` for all unique Account IDs from 3a.

After both queries return, **enrich each contact** with its account's open opportunities (match by `AccountId`). A contact whose account has no open opportunities gets `opportunities: []`.

## 4. Score ICP fit and rank

Score each contact 0–10 against the ICP from Step 1, then rank and take the top N (default 10). Weight only the dimensions the user named; if they gave a loose ICP, use the default weighting below. Score from queried values only — a blank field scores 0 for that dimension, never a guess.

| Signal | Weight | Scoring |
|---|---|---|
| Title / role / job level match | 3 | target persona=3, adjacent=1, off=0 |
| Account segment / industry match | 2 | in ICP=2, adjacent=1, off=0 |
| Account size / revenue in range | 2 | in range=2, ±50%=1, outside=0 |
| Open opportunity on the account | 2 | open opp=2, none=0 |
| Recent activity (`LastActivityDate`) | 1 | <90d=1, else 0 |

Rank by total score descending; break ties by open-opportunity amount, then recency. Take the top N. Note anyone excluded only for a missing field (e.g. no Title) so the user can fix it in Salesforce.

**Record links (built here, used in Step 5/6).** For every contact, account, and open opportunity that lands on the list, build its Lightning URL from the Id and `instanceUrl` — `https://[instanceUrl]/lightning/r/Contact/[Id]/view`, `.../Account/[Id]/view`, `.../Opportunity/[Id]/view`. These become the `href` on the Name, Account, and Open-opportunity cells. A contact with no open opportunity gets a plain-text "No open opp" cell (no link).


## 5. Output (text-only)

Links are inline markdown — `[Name](contactUrl)`, `[Account](accountUrl)`, `[Open opportunity](oppUrl)` — using each record's Lightning URL. Quote a missing email/phone as `—`.

```
# Event Invite List: [Event / Location] — [N] contacts

**Ranked by ICP fit** — [location] · [one-line ICP summary]
Drawn from [M] contacts near the location.

| # | Name | Title | Location | Email | Phone | Account | Open opportunity |
|---|---|---|---|---|---|---|---|
| 1 | [Dana Reyes](contactUrl) | SVP Operations | Chicago, IL | dreyes@… | (312) 555-0142 | [Meridian Health](accountUrl) | [Negotiation · $1.2M](oppUrl) |
| 2 | [Marcus Lee](contactUrl) | VP IT | Evanston, IL | mlee@… | (847) 555-0199 | [Lakeside Medical](accountUrl) | [Discovery · $450K](oppUrl) |
| 3 | [Priya Anand](contactUrl) | Director of Procurement | Chicago, IL | panand@… | — | [Northshore Clinics](accountUrl) | No open opp |
...

## Who to prioritize
[1-2 sentences — the highest-value contacts and the recommended first move, e.g. personal invites from the account owner before the general send.]

## Excluded for missing data
- [N] contacts near [location] dropped — missing [Title / segment / revenue] (fix in Salesforce to score them)

## Suggested next step
Draft event invite outreach for this list — run `draft-outreach`, or ask me to draft the invitations now.
```
