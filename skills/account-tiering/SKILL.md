---
name: account-tiering
description: "Rank an account list or full book into action tiers from Salesforce ICP fit, engagement, activity, contact, and opportunity data. Use to score accounts, prioritize coverage, decide where to focus, or identify accounts to activate, qualify, or deprioritize."
---
<!-- global-rules-bootstrap -->

# Global Rules

- **Execute silently between tool calls.** Do not output planning, progress, transition, waiting, or tool-result narration between calls. Execute tool calls silently and proceed directly to the next call. Parallelize independent tasks by batching tool calls into one turn whenever possible. Before the final output, speak only when the skill explicitly requires user input, approval, an exact notice, or material error/blocked reporting. Do not invent checkpoints.
- **Keep the final output concise.** Return only the requested result or deliverable. Omit process recaps, tool-call details, redundant preambles or conclusions, and data already shown in a widget.
- **⛔ WIDGET OUTPUT ONLY after data assembly.** Once all queries return, immediately call `display_widget` — at most a single one-line render-wait notice before it, and no summaries, transitions, or narration. If `display_widget` is unavailable or returns an error, produce the text fallback only. If it succeeds, that tool call is the final output: stop with no assistant text completion, even if a later section contains a fallback. The exceptions above do not apply after success.
- **Ground dynamic or custom relationship and field names before relying on them.** Fixed standard fields that this skill explicitly marks as requiring no grounding need no extra grounding call. On a name error, use the skill's documented grounding path when present; otherwise report the error instead of guessing or re-firing the same shape.
- **Cite every value exactly as queried**; never fabricate; distinguish a blank value from a value that was not queried. Link each Salesforce record inline: `https://[instanceUrl]/lightning/r/[SObjectType]/[Id]/view`.
- **Show human labels, never API/field literals.** In anything the user sees, print each field's grounded `label` (for example, "Deal Risk", not `Deal_Risk__c`) and record Names, never raw Ids or `__c` API names.
- **One idea per sentence.** In all generated content, if a sentence needs re-reading, it is carrying too much: split it.
- **Don't repeat the visual.** When a visualization or widget renders, the text around it tells the user what to conclude from the data. Do not restate numbers they can already see.
- **Use plain language.** Choose terms any reader understands on first read, with no domain knowledge or cultural context required. Avoid jargon and colloquialisms, and make labels signal what follows. Test: would a reader unfamiliar with the idiom understand the term and know what content to expect? Use "No engagement", not "went dark" or "ghosted".
- **Reproduce Salesforce terminology exactly.** Use the field labels, object names, and stage values the data returns; do not paraphrase them. Spell out acronyms on first use unless the term is an industry framework (for example, MEDDIC).
- **Empty `MINE` scope → fail fast, then ask which scope.** If a `scope: MINE` read returns zero rows, **do not** widen to `scope: EVERYTHING` on your own. Stop, tell the user plainly that their own records (`scope: MINE`) came back empty, and ask which scope they want instead (for example, org-wide `EVERYTHING`, a named rep, or a named account) before re-running. Never invent records, and never silently fall back to org-wide.
- **ONLY use the local instructions in this skill file, ONLY call MCP tools mentioned in the skill file and NEVER call an API or endpoint not written in this skill file.** Every Salesforce URL you need is in the skill. Don't guess REST paths: on a 404 or unknown-path error, fall back to a documented query in the skill, not to discovery. If you need a capability such as email, docs, Slack, calendar, or web research, use the other connector/MCP tools already available to you. Endpoint guessing and discovery add needless round-trips. Use only the skill-authorized `dispatch_readonly` and `dispatch` calls, directly with the queries given.
<!-- /global-rules-bootstrap -->
# Rules:

- Resolve to ONE account before the deep read. When the name is ambiguous, ask the user to pick — don't probe candidates or guess.

# Account Tiering

Ground (its own turn) → (read + evidence, all in ONE turn) → score → tier. Scope: "my accounts", a named list, or a report/list view name. Default tier count: 3 (A/B/C).

## 1. Ground (hardcoded — Account only)

Ground **only Account** — it always exists (naming a missing object fails the whole call). Its fields reveal this org's real ICP/engagement schema (custom fit score, territory, renewal fields, etc.) — don't assume custom field names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Account\\\"]) { fields { ApiName label relationshipName } } } }\"}" })
```

**Field policy.** Step 2's standard fields and child spans are fixed — always read, never grounded. Custom fields are optional and come from THIS result only: use exact strings, never guess. Select relevant scalar `__c` fields carrying ICP-fit/engagement signals as `{ value }`, and each relevant custom lookup's exact `relationshipName` for a related record name. Build Step 2 only once this result is in hand — never fire the two together.

**Standard-field fallback.** If Step 1 errors, returns no `fields`, or was saved to a file you could not read in full (read failed, truncated, or token-capped), select NO custom fields — not from a preview, a partial read, or memory. Leave `<ACCOUNT_CUSTOM>` and the custom lookup blocks empty, fire Step 2 exactly as written, and disclose it (Step 5).

The ICP (industries, size, titles, disqualifiers) is set in Step 3 by a fixed rule — never invent it.

## 2. Read (fill from step 1, one dispatch)

`%SCOPE%` = `scope: MINE` for "my accounts"; `where: { Name: { in: [\\\"Acme\\\", ...] } }` for a named list. (A report/list-view scope needs its own name→Id resolve first — outside the common path; ask for a name list instead if one isn't already resolved.)

**Reference-field rule:** a confirmed scalar `__c` field → `Field__c { value }` (`displayValue` is null for Id fields here — don't rely on it). For a related record's name, span only the exact `relationshipName` from Step 1: `<relationshipName> { Name { value } }`. No usable `relationshipName` → take the `__c { value }` Id and move on; do not retry.

Insert `<ACCOUNT_CUSTOM>` = confirmed scalar `__c { value }` fields relevant to fit/engagement; `<REL_BLOCKS>` = one block per confirmed relevant custom lookup. `Owner`/`Opportunities`/`Contacts` always work.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(%SCOPE%, first: 200, orderBy: { Id: { order: ASC } }) { edges { node { Id Name { value } Industry { value } NumberOfEmployees { value } AnnualRevenue { value displayValue } Website { value } Type { value } LastActivityDate { value } <ACCOUNT_CUSTOM> Owner { Name { value } } <REL_BLOCKS> Opportunities(where: { IsClosed: { eq: false } }, first: 200, orderBy: { CloseDate: { order: ASC } }) { edges { node { Id Name { value } StageName { value } CloseDate { value } Amount { value } } } } ClosedWonOpportunities: Opportunities(where: { IsClosed: { eq: true }, IsWon: { eq: true } }, first: 200, orderBy: { CloseDate: { order: DESC } }) { edges { node { Id CloseDate { value } Amount { value } } } } Contacts(first: 10) { edges { node { Id Title { value } } } } } } pageInfo { hasNextPage } totalCount } } } }\"}" })
```

**Opportunity reads:**
- `Opportunities` (open): Changed `first: 1` to `first: 200` and added `Amount { value }` to calculate whitespace (sum of open opportunity amounts)
- `ClosedWonOpportunities` (alias): New read of closed-won opportunities to calculate ARR (sum of amounts from last 12 months)
- Step 4's "Open opportunity exists" = a non-empty `Opportunities.edges` (unchanged)
- Empty `Account` `edges` → for `scope: MINE`, follow the empty-`MINE` rule; for a named list, confirm the account names.

**Bounds.** `Account(first: 200)` is the whole book up to 200 accounts. `pageInfo.hasNextPage: true` → the book is larger (`totalCount` accounts): tier the 200 you have and disclose the partial book (Step 5) — never call them the whole book. `Contacts(first: 10)` is a bounded sample per account — enough for the 3+ contacts signal; a full 10 with no target title scores the persona check `maybe`, not `none`.

## 2b. Evidence (fired IN PARALLEL with step 2 — same turn)

Issue step 2 and step 2b together in one turn; don't wait for the SF read. Keyed on the account scope (names/domains), not the SF result:
- **email**: inbound threads from account domains in the last 90d → which accounts, last date
- **docs/slack**: any account mentions → triggers, concerns

Use whatever tools are available; skip silently if none (SFDC-only is fine). Never block on these; cite source + date for anything you use.

## 3. Score ICP fit (0-10)

**ICP source** — use the first that applies, and record which (Step 5):
1. **Stated** — the industries, size, titles, or disqualifiers the user gives in the request (or earlier in the conversation).
2. **Derived** — otherwise, from the accounts read in Step 2 that have an open opportunity (Step 4's signal), ignoring nulls: target industries = their 3 most common `Industry` values (ties alphabetical); size range = their min–max `NumberOfEmployees`. Persona = a Contact title containing VP, Director, Head, or Chief, or a C-level acronym (CEO, CFO, CRO, CIO, CTO, COO). Disqualifiers = none, so every account scores clean.
3. **Ask** — the ICP can't be derived: no account has an open opportunity, or none of those accounts has an `Industry` or none has a `NumberOfEmployees` value. Ask the user for the ICP once, and don't score until they answer — never derive with a missing criterion.

A criterion the user didn't state falls back to its derived value; if that value can't be derived, ask (3).

| Signal | Weight | Scoring |
|---|---|---|
| Industry match | 3 | exact=3, adjacent=1, off-ICP=0 |
| Size in range | 3 | in range=3, ±50%=1, outside=0 |
| Target persona present (Contact titles) | 2 | yes=2, maybe=1, none=0 |
| No disqualifiers | 2 | clean=2, soft DQ=1, hard DQ=0 |

## 4. Score engagement (0-10)

| Signal | Weight | Scoring |
|---|---|---|
| Open opportunity exists (Step 2) | 3 | yes=3, no=0 |
| LastActivityDate recency | 3 | <30d=3, 30-90d=2, 90-180d=1, >180d=0 |
| Inbound signal (Step 2b email, last 90d) | 2 | yes=2, no=0 |
| Multiple contacts engaged | 2 | 3+=2, 2=1, ≤1=0 |

## 4b. Calculate ARR, whitespace, and engagement % (HXL widgets only)

For each account, compute these display values from Step 2 data:

**ARR (Annual Recurring Revenue):**
- Sum `Amount.value` from `ClosedWonOpportunities` where `CloseDate` is within the last 12 months
- Format as compact currency: "$75K", "$1.2M" (K for thousands, M for millions)
- If no closed-won opportunities in last 12 months, set to "$0"

**Whitespace (expansion opportunity):**
- Sum `Amount.value` from open `Opportunities` (IsClosed = false)
- Format as compact currency: "$640K", "$2.3M"
- If no open opportunities, set to "$0"

**Engagement % (for display):**
- Convert the 0-10 engagement score from Step 4 to a percentage string
- Formula: `Math.round((engagementScore / 10) * 100)` + "%"
- Example: score of 6 → "60%"


## 5. Tier and recommend

Assign each account to **Tier A** (active pursuit), **Tier B** (nurture), or **Tier C** (monitor) based on **four factors**:
1. **ICP fit** (0-10 from section 3)
2. **Engagement** (0-10 from section 4)
3. **Annual Recurring Revenue (ARR)** — existing revenue relationship
4. **Whitespace** — expansion / upsell opportunity

**Tier assignment guidance:**
- **Tier A** (active pursuit): High ICP fit (≥6) AND high engagement (≥6) AND (ARR >$0 OR whitespace >$100K). These accounts warrant immediate, multi-threaded pursuit.
- **Tier B** (nurture): Exactly one strength — (ICP fit ≥6 XOR engagement ≥6). Keep warm with light touch; revisit when signals improve.
- **Tier C** (monitor): Both low — ICP fit <6 AND engagement <6. Periodic check-ins; escalate if conditions change.


**Disclosures** — carry each that applies into the output (the widget `subtitle`; in the text fallback, a line under the heading):
- Partial book (`hasNextPage: true`): "first 200 of [totalCount] accounts — narrow the scope to tier the rest". The widget `title` and the text heading also count "200 of [totalCount]", never just 200.
- Standard-field fallback: "custom fit fields unavailable — scored on standard fields".
- Derived ICP: "ICP derived from your [N] accounts with open deals: [industries], [min–max] employees". Omit when the user stated the ICP.

## 6. Output — HXL widget

**CRITICAL LAYOUT RULE: You MUST call display_widget with this EXACT format:**

```javascript
display_widget({ 
  resourceType: "dynamic", 
  widgetDefinition: { 
    widget: "account-tiering", 
    data: <object matching the schema below>, 
    renderer: { body: [] } 
  } 
})
```

- **DO NOT omit `resourceType: "dynamic"` or `widgetDefinition`** — the tool requires this envelope.
- **DO NOT construct tile layouts yourself** (tile/container, tile/row, tile/markdown, etc.) inside `widgetDefinition`.
- **Your job is DATA ONLY**: compute the `data` object per the schema below. The `renderer: { body: [] }` part stays empty.
- The `widget: "account-tiering"` value tells the renderer to use the pre-designed layout from renderer.json, which handles all visual structure (the segmented bar, collapsible Sources, datagrid, callouts, etc.).
- **If you send a different format or build custom tile layouts, the layout will be wrong.**

The schema below names every key (all optional except `title`, `answer`, `sources`), its type, and when to include it.

**Widget contract:**
- **Block order**: title, answer, tierBar (optional), accounts datagrid (optional), nextStep (optional), sources.
- **Always include**: `title`, `answer`, `sources`. Optional: `tierBar` (tier distribution counts), `labels`, `accounts`, `nextStep`.
- **Prompt scoping**: Include the accounts datagrid when the prompt calls for a detailed breakdown (not just tier counts). For a summary-level prompt ("How should I tier my accounts?"), include accounts. For a tier-count-only prompt, omit accounts.
- **tierBar — REQUIRED, SEGMENTED BAR ONLY**: Always populate as nested objects with three keys: `tierA`, `tierB`, `tierC`. Each has `value` (count as number) and `label` (display string, e.g., "Tier A - 4"). This renders a **horizontal segmented bar chart** showing tier distribution. **DO NOT use a donut/pie chart, circular chart, or any other chart type — the tierBar must always be a horizontal segmented bar.** This layout is fixed by design and must not be changed.
- **Tier badge variants** (semantic, HXL design system): Tier A = `"success"` (green, top priority), Tier B = `"info"` (blue, medium priority), Tier C = `"neutral"` (gray, low priority). Every tier badge in the accounts datagrid must include both `value` (the letter) and `badgeVariant` (the semantic color).
- **Account names**: Pass account names as plain text strings. DO NOT include Markdown link syntax like `[Name](URL)` in the account field — the datagrid renders it literally. Clickable account links belong in the `sources` array at the bottom.

```json
{
  "type": "object",
  "description": "HXL widget data contract for account-tiering. Block order: title, answer, accounts datagrid, nextStep (optional), sources. Only title, answer, and sources are required; omit accounts or nextStep and their blocks are not shown.",
  "properties": {
    "title": {
      "type": "string",
      "description": "Contextual title — the tier-count takeaway in one sentence (e.g., 'Your 10 accounts are sorted into 4 Tier A, 4 Tier B, and 2 Tier C — so you can pour your time into the 4 worth pursuing now.')."
    },
    "answer": {
      "type": "string",
      "description": "Answer in markdown format — 2-4 bullet items with **bold** facts. Explains how accounts were tiered (ICP fit, engagement, ARR, whitespace) and what each tier means (Tier A = active pursuit, Tier B = nurture, Tier C = monitor)."
    },
    "labels": {
      "type": "object",
      "description": "Fixed label text for card headings and table headers. Each has an English default.",
      "properties": {
        "accountsCaption": {
          "type": "string",
          "description": "Accounts table eyebrow.",
          "default": "Accounts"
        },
        "tierHeader": {
          "type": "string",
          "description": "Tier column header.",
          "default": "Tier"
        },
        "accountHeader": {
          "type": "string",
          "description": "Account column header.",
          "default": "Account"
        },
        "icpFitHeader": {
          "type": "string",
          "description": "ICP Fit column header.",
          "default": "ICP Fit"
        },
        "engagementHeader": {
          "type": "string",
          "description": "Engagement column header.",
          "default": "Engagement"
        },
        "arrHeader": {
          "type": "string",
          "description": "ARR column header.",
          "default": "ARR"
        },
        "whitespaceHeader": {
          "type": "string",
          "description": "Whitespace column header.",
          "default": "Whitespace"
        },
        "motionHeader": {
          "type": "string",
          "description": "Motion column header.",
          "default": "Motion"
        },
        "sourcesToggle": {
          "type": "string",
          "description": "Sources toggle label.",
          "default": "Sources"
        },
        "tierBarCaption": {
          "type": "string",
          "description": "Tier bar eyebrow caption.",
          "default": "Accounts by Tier"
        },
        "tierA": {
          "type": "string",
          "description": "Tier A legend detail (e.g., 'active pursuit').",
          "default": "active pursuit"
        },
        "tierB": {
          "type": "string",
          "description": "Tier B legend detail (e.g., 'nurture').",
          "default": "nurture"
        },
        "tierC": {
          "type": "string",
          "description": "Tier C legend detail (e.g., 'monitor').",
          "default": "monitor"
        }
      }
    },
    "tierBar": {
      "type": "object",
      "description": "OPTIONAL card 'ACCOUNTS BY TIER': segmented proportion bar showing tier distribution (A/B/C counts). Always populate with nested objects for each tier.",
      "properties": {
        "tierA": {
          "type": "object",
          "description": "Tier A segment data.",
          "properties": {
            "value": {"type": "number", "description": "Tier A count (e.g., 5)."},
            "label": {"type": "string", "description": "Display label (e.g., 'Tier A - 5')."}
          },
          "required": ["value", "label"]
        },
        "tierB": {
          "type": "object",
          "description": "Tier B segment data.",
          "properties": {
            "value": {"type": "number", "description": "Tier B count (e.g., 6)."},
            "label": {"type": "string", "description": "Display label (e.g., 'Tier B - 6')."}
          },
          "required": ["value", "label"]
        },
        "tierC": {
          "type": "object",
          "description": "Tier C segment data.",
          "properties": {
            "value": {"type": "number", "description": "Tier C count (e.g., 1)."},
            "label": {"type": "string", "description": "Display label (e.g., 'Tier C - 1')."}
          },
          "required": ["value", "label"]
        }
      },
      "required": ["tierA", "tierB", "tierC"]
    },
    "accounts": {
      "type": "array",
      "description": "OPTIONAL card 'ACCOUNTS'. One row per account, showing Tier, Account name, ICP Fit, Engagement %, ARR, Whitespace, and Motion. Include ONLY when the prompt calls for a detailed account breakdown. Omit the key otherwise; never an empty array.",
      "items": {
        "type": "object",
        "properties": {
          "tier": {
            "type": "object",
            "description": "Tier badge (A/B/C) with semantic variant.",
            "properties": {
              "value": {
                "type": "string",
                "description": "Tier letter: A, B, or C."
              },
              "badgeVariant": {
                "type": "string",
                "description": "Badge variant: 'success' (green, Tier A), 'info' (blue, Tier B), or 'neutral' (gray, Tier C).",
                "enum": ["success", "info", "neutral"]
              }
            },
            "required": ["value", "badgeVariant"]
          },
          "account": {
            "type": "string",
            "description": "Account name (display-ready)."
          },
          "icpFit": {
            "type": "number",
            "description": "ICP fit score (0-10 scale, display as integer)."
          },
          "engagement": {
            "type": "string",
            "description": "Engagement percentage derived from 0-10 score (display-ready, e.g., '60%'). Calculated as (score/10)*100%."
          },
          "arr": {
            "type": "string",
            "description": "Annual recurring revenue - sum of closed-won opportunity amounts from last 12 months (display-ready currency, e.g., '$75K', '$0' if none)."
          },
          "whitespace": {
            "type": "string",
            "description": "Whitespace / expansion opportunity - sum of open opportunity amounts (display-ready currency, e.g., '$640K', '$0' if none)."
          },
          "motion": {
            "type": "string",
            "description": "Recommended sales motion (e.g., 'Active pursuit', 'Nurture', 'Monitor')."
          }
        },
        "required": ["tier", "account", "icpFit", "engagement", "arr", "whitespace", "motion"]
      }
    },
    "nextStep": {
      "type": "object",
      "description": "OPTIONAL next-step recommendation. Include when there's a suggested move or follow-up action.",
      "properties": {
        "lead": {
          "type": "string",
          "description": "Optional bold lead-in (e.g., 'Put this week's energy into the 4 Tier A accounts.'). Omit when the recommendation has no bold lead."
        },
        "text": {
          "type": "string",
          "description": "Main recommendation text. Ends with a follow-up question to hand the turn back to the user."
        }
      },
      "required": ["text"]
    },
    "sources": {
      "type": "array",
      "description": "Source citations — where the answer came from (Account records, list views). Required.",
      "items": {
        "type": "object",
        "properties": {
          "label": {
            "type": "string",
            "description": "Citation label (e.g., 'Account: Cedarline Financial')."
          },
          "url": {
            "type": "string",
            "description": "Optional link to the record or list view."
          }
        },
        "required": ["label"]
      }
    }
  },
  "required": ["title", "answer", "sources"],
  "additionalProperties": false
}
```

### Scope the blocks to the prompt

The schema marks only `title`, `answer` and `sources` as required. **Both `tierBar` and `accounts` are optional** — include tierBar for multi-account tier distribution, include accounts datagrid when the prompt asks for details, omit both for single-account queries.

| The prompt is… | Send |
|---|---|
| Broad ("Tier my accounts", "How should I prioritize my book?") | `title` + `answer` + `tierBar` + `accounts` (full breakdown) + `nextStep` (if actionable) + `sources` |
| Summary-level ("Just the tier counts", "How many Tier A accounts?") | `title` + `answer` + `tierBar` + `sources` (omit `accounts` datagrid) |
| Specific account inquiry ("Which tier is Acme in?") | `title` + `answer` + `sources` (omit both `tierBar` and `accounts` if answering about one account) |

### What to send

Rules:
- **Omit a key and its block is not shown.** Never send empty arrays, empty strings or placeholders. Drop `accounts` or `nextStep` when you have no data for them.
- **Scope reading and output to the prompt.** Steps 1–5 still tier the full book, but a summary-prompt outputs counts only; a specific-account prompt returns that account's tier.
- **Display-ready strings:** Format percentages as "60%", currency as "$75K", tier letters as "A"/"B"/"C" with matching `badgeVariant`.
- **Tier badges:** Every account row's `tier` field must be an object with `value` (the letter) and `badgeVariant` (`"success"` for A, `"info"` for B, `"neutral"` for C).
- **Account names** are plain text, never Markdown links. Clickable account URLs go in `sources`.
- **Source URLs:** Construct Salesforce record URLs as `https://{orgMyDomain}/lightning/r/{SObjectType}/{Id}/view` (e.g., `https://example.my.salesforce.com/lightning/r/Account/001xx000003DHhfAAG/view`). Omit the `url` field when the record ID is unknown.
- **Language:** omit `labels` for English. For any other response language, translate all `labels` values (tierBar segment labels like tierA/tierB/tierC detail strings, column headers, sources toggle) and keep tier badge letters (A/B/C) and account names unchanged.
- **Before calling:** no `{!…}` or `{{…}}` anywhere in `data`, and no keys outside the schema.

#### Worked examples (the `data` object only)

**Broad — "Tier my accounts."** (includes accounts datagrid; trimmed):

```json
{
  "title": "Your 10 accounts are sorted into 4 Tier A, 4 Tier B, and 2 Tier C — so you can pour your time into the 4 worth pursuing now.",
  "answer": "- Your book of 10 accounts breaks down: **4 Tier A** (active pursuit), **4 Tier B** (nurture), and **2 Tier C** (monitor).\n- Tiers are set by **Ideal Customer Profile (ICP) fit**, **engagement**, **annual recurring revenue (ARR)**, and **whitespace** — not a single score.\n- Tier A accounts score high on ICP fit and carry the most open whitespace, so each warrants active pursuit this quarter.\n- Tier B are a fit but earlier or quieter — worth nurturing. Tier C are lower fit or engagement; monitor them and revisit if a signal changes.",
  "tierBar": {
    "tierA": { "value": 4, "label": "Tier A - 4" },
    "tierB": { "value": 4, "label": "Tier B - 4" },
    "tierC": { "value": 2, "label": "Tier C - 2" }
  },
  "accounts": [
    { "tier": { "value": "A", "badgeVariant": "success" }, "account": "Cedarline Financial", "icpFit": 4, "engagement": "60%", "arr": "$75K", "whitespace": "$640K", "motion": "Active pursuit" }
  ],
  "nextStep": {
    "lead": "Put this week's energy into the 4 Tier A accounts.",
    "text": "Cedarline, Brightwave, Northpeak, and Summit Health score highest on fit and carry the most open whitespace — they're where active pursuit pays off now. Keep Tier B warm with light nurture, and leave Tier C on monitor until engagement or fit improves. Want me to build a pursuit plan for the 4 Tier A accounts?"
  },
  "sources": [
    { "label": "Account: Cedarline Financial", "url": "https://org.lightning.force.com/..." }
  ]
}
```

**Summary — "How many Tier A accounts do I have?"** (omits accounts datagrid):

```json
{
  "title": "You have 4 Tier A accounts out of 10 total — the ones worth active pursuit now.",
  "answer": "- Your book breaks down: **4 Tier A** (active pursuit), **4 Tier B** (nurture), and **2 Tier C** (monitor).\n- Tier A accounts are high-fit, high-engagement, and carry the most whitespace — each is worth pursuing this quarter.",
  "tierBar": {
    "tierA": { "value": 4, "label": "Tier A - 4" },
    "tierB": { "value": 4, "label": "Tier B - 4" },
    "tierC": { "value": 2, "label": "Tier C - 2" }
  },
  "sources": [
    { "label": "Accounts tiered from your book of 10" }
  ]
}
```

**Specific account — "Which tier is Cedarline Financial in?"** (omits tierBar and accounts):

```json
{
  "title": "Cedarline Financial is Tier A — high fit and engagement, worth active pursuit.",
  "answer": "- **Cedarline Financial** is **Tier A** (active pursuit): ICP fit 4/5, 60% engagement, $75K ARR, $640K whitespace.\n- The high ICP fit and significant whitespace make this account worth pursuing actively this quarter.",
  "sources": [
    { "label": "Account: Cedarline Financial", "url": "https://org.lightning.force.com/..." }
  ]
}
```


## 7. Text fallback — DO NOT USE IF `display_widget` SUCCEEDED

```
# Account Tiering - [N] accounts

## Tier A - Active Pursuit ([N])
| Account | Fit | Eng | Open Opp | Last Touch | Next Action |
|---|---|---|---|---|---|
...

## Tier B - Nurture ([N])
...

## Tier C - Monitor ([N])
...

## Coverage Gaps
- [N] Tier A/B accounts with no activity in 30+ days
- [N] accounts missing Industry or NumberOfEmployees (can't score - fix in SFDC)
```
