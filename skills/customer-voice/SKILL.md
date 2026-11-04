---
name: customer-voice
description: "Compile attributable customer quotes and themes from call transcripts and email threads across Salesforce-scoped accounts. Use to understand feedback on a feature, objection, competitor, or emerging issue, compare accounts, or surface recurring themes."
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
# Customer Voice

Direct customer quotes on a topic, from transcripts + email threads across your accounts — verbatim with attribution, not summaries. Salesforce only *scopes* the search: which accounts, and who's internal vs. customer. Context (all in ONE turn) → search docs/email/Slack → extract quotes → group by theme.

Inputs: **topic** (theme/objection/feature/competitor, or open-ended "what's coming up"); **scope** (my accounts default / team / named list); **period** (30d default).

## 1. Context — 3 independent SF reads + the searches, all in ONE turn

These don't depend on each other, so fire them together (with the doc/email/Slack searches below). No schema grounding — fields are fixed.

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

## 2. Search sources (same turn — skip a source whose connector is absent, and note it)

- **docs**: transcripts / notes / meeting docs in the period, in account-named folders (team scope → team-shared too).
- **email**: threads in the period to/from the scoped account domains.
- **Slack**: Slack Connect / external shared channels with the scoped accounts, messages in the period.

Narrow each search to the period and the scoped account names/domains (e.g. title contains "transcript" or an account name) instead of paging through every result. Skip shortcuts (`application/vnd.google-apps.shortcut`) and notes where every attendee is internal, and keep only files you can tie to a scoped account by title or folder. A search snippet can be cut off — read the full file before quoting from it.

Keep track of three buckets per source: **contributed** (yielded at least one quote), **searched, nothing relevant**, and **couldn't search** (connector not installed, connection failed, or a search that isn't enabled). The answer says which sources the quotes came from and which were empty or excluded, so the user knows what isn't reflected.

## 3. Extract quotes (strict — customer-only, on-topic, verbatim)

Per transcript/thread, pull passages where the **customer** (not your domain/org) speaks on the topic: verbatim quote (1–3 sentences) · speaker name + title + account · date + source · one-line context. Paraphrase is NOT voice-of-customer. Open-ended topic → cluster by theme, return top 3–5 by frequency.

- **Speaker side**: transcript labels read `Name (Title, Company)` — a Company equal to the org name is internal. Email: sender domain vs the internal domain.
- **Date** = when the customer said it (email sent date, the transcript's `Date:` line or title prefix) — never a file's created/modified time.
- **Source** = `Gmail`, `Slack Connect`, `Salesforce call`, or `Call transcript`, with its link (thread, permalink, call record, or the doc's `viewUrl`).

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
