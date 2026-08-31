---
name: account-plan
description: Required when viewing or creating AccountPlan records visually. Use whenever the user asks to "show/get/view/pull up the account plan for [Account]" (view path) or "create/build/set up/draft an account plan for [Account]" (create path). Returns the plan in either an interactive HTML widget with vision, priorities, KPIs, and relationship grid (Cowork/desktop/web) or clean markdown (Claude Code).
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
# Goal:
View or create an `AccountPlan` for a Salesforce Account entirely via the API — the strategic picture (challenges, competitive landscape, industry trends, priorities, vision) and the relationship SWOT.

# Audience:
Sales-org workers who want results fast. Minimize thinking when it's not needed; get them the plan.

# Rules:

- Parallelize independent reads — fire the account resolve and the AccountPlan-custom grounding in ONE turn.
- **Pick View vs Create from the verb before doing anything.** View = show/get/pull up/view/see. Create = create/build/set up/draft/make. Ambiguous → ask which; **never fall through a view request into creating a record.**
- On the create path, flag anything you can't source with `[needs validation]`.
- **`Status` is always `"Not Started"` on creation.** Never create a plan in any other status; lifecycle changes are out of scope.

**Voice/tone (create path only).** The generated narrative fields should read in the org's own house voice, not a generic register. Infer that voice in priority order: (1) **explicit user direction** — if the user dictates tone or wording, follow it verbatim; (2) **this account's existing plan prose**, when V1 already returned a plan (the second-plan case) — the truest house-voice sample you'll have; (3) **`Account.Description`** from step 1, as a light register anchor — it's often short or blank, so lean on it lightly. Absent all three, **default to a clear, plainly-professional register**: direct declarative sentences, concrete and specific, no marketing adjectives ("robust", "cutting-edge"), no filler, no exclamation points. Voice governs **style only** — it never licenses inventing content: numbers, quotes, competitor names, and every other claim still obey the cite-as-queried / `[needs validation]` rule above.

The account's real competitor list and org defaults for plan naming/start date are external knowledge — infer from the org's own data or ask the user once. Never invent them.

# Account Plan

## 1. Resolve the account (fire in parallel with step 2)

If the user gave a Salesforce Id, skip to the path. Otherwise resolve by name — this same read seeds the Create-path context (industry, revenue, employees, description):

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Name: { like: \\\"%ACCOUNT%\\\" } }, first: 5) { edges { node { Id Name { value } Industry { value } Website { value } Description { value } AnnualRevenue { value displayValue } NumberOfEmployees { value } Type { value } BillingCity { value } BillingCountry { value } Owner { Name { value } } } } } } } }\"}" })
```

- **One match** → take its `Id`, keep the other fields as account context.
- **Multiple** → list candidates (Name · Industry · Website · Owner) and ask which. Don't guess.
- **None** → tell the user no Account by that name exists; ask them to confirm the name or give the Id. Never invent or create an Account.

## 2. Ground AccountPlan customs (fire in parallel with step 1)

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"AccountPlan\\\"]) { fields { ApiName label } } } }\"}" })
```

`AccountPlan` is **feature-gated** — ObjectInfo may not surface it in every org. If this returns an error or empty, that is NOT fatal: skip custom grounding and use the SOQL fallback in V1. Note any `__c` fields whose `label` matches plan/relationship keywords for `<PLAN_CUSTOM>`.

---

# View path

## V1. Query the existing plan (by resolved AccountId)

GraphQL first; insert `<PLAN_CUSTOM>` = confirmed `__c { value }` fields from step 2:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { AccountPlan(where: { AccountId: { eq: \\\"<ID>\\\" } }, first: 5, orderBy: { LastModifiedDate: { order: DESC } }) { edges { node { Id Name { value } Status { value } StartDate { value } LastModifiedDate { value } AccountChallenges { value } AccountCmptvWeaknesses { value } AccountCompetitiveStrengths { value } AccountCompetitors { value } AccountIndustryTrends { value } AccountPrfmIndicators { value } AccountStrategicPriorities { value } AccountVision { value } RelationshipOpportunities { value } RelationshipStrengths { value } RelationshipThreats { value } RelationshipWeaknesses { value } <PLAN_CUSTOM> Account { Name { value } } } } } } } }\"}" })
```

**Fallback (feature-gated object).** If `AccountPlan` isn't UI-API queryable here, use describe-grounded SOQL at **`v63.0`**:

```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT Id, Name, AccountId, Account.Name, AccountChallenges, AccountCmptvWeaknesses, AccountCompetitiveStrengths, AccountCompetitors, AccountIndustryTrends, AccountPrfmIndicators, AccountStrategicPriorities, AccountVision, RelationshipOpportunities, RelationshipStrengths, RelationshipThreats, RelationshipWeaknesses, StartDate, Status, LastModifiedDate FROM AccountPlan WHERE AccountId = '[Id]' ORDER BY LastModifiedDate DESC" })
```

On `INVALID_TYPE`, **first confirm the request used `v63.0`** (retry at v63.0 if not) — report "AccountPlan is not available in this org" only when a correctly-versioned v63.0 request still returns `INVALID_TYPE`.

- **One plan** → use it. **Multiple** → list (Name · Status · StartDate · LastModifiedDate), default to most-recently-modified and say so. **None** → tell the user there's no plan yet and offer to create one (switch to Create path). Never invent plan content.

## V2. Render → **Step R**. Read-only — never write on this path.

---

# Create path

## C1. Guard against duplicates

Run V1 first. **Plan exists** → render it (Step R) and ask the user to confirm they want a *second* plan before proceeding — don't duplicate without explicit yes. **None** → continue.

## C2. Gather context (one turn — batch the SF read with any web research)

**One GraphQL read** pulls open pipeline + recent activity together as children of the account (replaces two SOQL calls):

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Id: { eq: \\\"<ID>\\\" } }, first: 1) { edges { node { Opportunities(where: { IsClosed: { eq: false } }, first: 10, orderBy: { CloseDate: { order: ASC } }) { edges { node { Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } } } } Tasks(first: 10, where: { ActivityDate: { gte: { literal: LAST_90_DAYS } } }, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Subject { value } ActivityDate { value } Type { value displayValue } } } } } } } } } }\"}" })
```

Open opps inform `RelationshipOpportunities`/`RelationshipStrengths`; quiet Tasks inform `RelationshipThreats`. In the same turn, do web research (if a tool is present) to ground the competitive picture, industry trends, and strategic priorities. **Only write claims you can trace to a source** — `[needs validation]` for anything thin, general/inferential phrasing over invented specifics ("likely prioritizing cost reduction given industry headwinds", not "cutting costs 20%"). If the user dictated field values, use them verbatim and generate only the rest.

## C3. Assemble the field map

| Field | Holds |
|---|---|
| `AccountId` | Resolved Id (required FK). |
| `Name` | Default `"{Account Name} Account Plan"` unless the user names it. |
| `AccountChallenges` | Key business challenges. |
| `AccountCmptvWeaknesses` | The account's competitive weaknesses. |
| `AccountCompetitiveStrengths` | The account's competitive strengths. |
| `AccountCompetitors` | Primary competitors. |
| `AccountIndustryTrends` | Relevant industry trends. |
| `AccountPrfmIndicators` | Key performance indicators. |
| `AccountStrategicPriorities` | Strategic priorities. |
| `AccountVision` | Stated or inferred vision. |
| `RelationshipOpportunities` | Opportunities to grow the relationship. |
| `RelationshipStrengths` | Current relationship strengths. |
| `RelationshipThreats` | Threats to the relationship. |
| `RelationshipWeaknesses` | Relationship weaknesses. |
| `StartDate` | Default today, `YYYY-MM-DD`. |
| `Status` | **Always `"Not Started"`.** |

## C4. Confirm — the write gate

Show the assembled field map (narrative + resolved `AccountId`/`Name`) and let the user correct it. **Do not create the record until the user confirms or edits.**

## C5. Create, verify, render

```
dispatch(method: "POST", url: "/services/data/v63.0/sobjects/AccountPlan",
  body: { "AccountId": "[accountId]", "Name": "[Account Name] Account Plan", "AccountChallenges": "…", "AccountCmptvWeaknesses": "…", "AccountCompetitiveStrengths": "…", "AccountCompetitors": "…", "AccountIndustryTrends": "…", "AccountPrfmIndicators": "…", "AccountStrategicPriorities": "…", "AccountVision": "…", "RelationshipOpportunities": "…", "RelationshipStrengths": "…", "RelationshipThreats": "…", "RelationshipWeaknesses": "…", "StartDate": "[today YYYY-MM-DD]", "Status": "Not Started" })
```

Capture the returned `id`, read it back to confirm it persisted, verify `Status` is `Not Started` and `AccountId` matches, then render (**Step R**):

```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/sobjects/AccountPlan/[createdPlanId]")
```

---

## Step R — Render (shared)

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

If `display_widget` is available (Cowork/desktop/web), the widget IS the output — call it immediately. Produce the markdown below only if `display_widget` is unavailable (e.g. a terminal); don't also dump it when the widget renders. The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (`growthBands`, `objRows`) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text.

Tokens: `planTitle` (e.g. "Account plan — <Account> FY26") · `headerStatus` (a short pace badge, e.g. "BEHIND PACE"/"ON PLAN") · `planSubtitle` (one line: live ARR → target · N objectives · on track on M of N) · **growth meter** `growthValue`/`growthMax`/`growthTarget` (raw numbers in the same unit, e.g. $M — current booked/live revenue, the plan ceiling, and the FY target), `growthValueLabel`/`growthTargetLabel` (display strings like "$1.6M of $3.0M plan"), `growthStatus` (e.g. "53% of plan, behind pace"), `growthBands` (array of `{from,to,variant,label}` — error/warning/success — covering 0→max in order) · **objectives datagrid** `objRows` (array, one per strategic objective: `{obj, prog: 0-100, owner (plain string — format as the person's display name (e.g. "Priya Nair"); names must be plain strings, not objects: use `User.Name.value` from the SF response), due: YYYY-MM-DD, state: {value,badgeVariant}, _tone, _status}`) · **callout** `synthTitle`/`synthDetail` (the plan's single most important read — the long pole and the move), `ctaLabel`/`ctaMsg` (`action/sendMessage`, a first-person next-step prompt), `planUrl` (the Account/AccountPlan Lightning record URL for the "View in Salesforce" button).

The growth meter and objectives are synthesized from what you already gathered — the AccountPlan narrative fields (`AccountStrategicPriorities`, `AccountVision`, relationship fields) become the objective rows and the synthesis callout; the C2 open-pipeline read and `Account.AnnualRevenue` inform the growth figures. FY target and per-objective progress are judgment calls off that narrative, not structured Salesforce fields — reason from the text, mark anything thin `[needs validation]`, and never invent dollar figures. The account-analysis narrative (challenges, competitors, industry trends, performance indicators) isn't carried by the widget — include it in the markdown fallback below. Blank fields stay "blank", never invented.

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
                  { "definition": "tile/icon", "attributes": { "name": "target", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{planTitle}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{headerStatus}}", "variant": "warning" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{planSubtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/meter",
            "attributes": {
              "label": "Growth to FY26 target",
              "value": "{{growthValue}}",
              "min": 0,
              "max": "{{growthMax}}",
              "target": "{{growthTarget}}",
              "valueFormat": "currency",
              "valueLabel": "{{growthValueLabel}}",
              "targetLabel": "{{growthTargetLabel}}",
              "status": "{{growthStatus}}",
              "size": "lg",
              "bands": "{{growthBands}}"
            }
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Strategic objectives and progress",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                { "key": "obj", "header": "Objective", "type": "text" },
                { "key": "prog", "header": "Progress", "type": "databar", "target": 100 },
                { "key": "owner", "header": "Owner", "type": "avatar" },
                { "key": "due", "header": "Due", "type": "date" },
                { "key": "state", "header": "State", "type": "badge" }
              ],
              "rows": "{{objRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "warning",
              "title": "{{synthTitle}}",
              "description": "{{synthDetail}}"
            },
            "children": [
              {
                "definition": "tile/row",
                "attributes": { "gap": "sm", "align": "center", "isWrapped": true },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{ctaLabel}}",
                      "variant": "primary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{ctaMsg}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "View in Salesforce",
                      "variant": "secondary",
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{planUrl}}" } }
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



> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.
Markdown — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED:

```markdown
# [AccountName] — Account Plan
**Status:** [Status]  |  **Start:** [StartDate]

## Vision
[AccountVision]

## Strategic Priorities
- [AccountStrategicPriorities as bullets]

## Account
- **Challenges:** [AccountChallenges]
- **Competitors:** [AccountCompetitors]
- **Competitive strengths:** [AccountCompetitiveStrengths]
- **Competitive weaknesses:** [AccountCmptvWeaknesses]
- **Industry trends:** [AccountIndustryTrends]
- **Performance indicators:** [AccountPrfmIndicators]

## Relationship
| Strengths | Weaknesses |
|---|---|
| [RelationshipStrengths] | [RelationshipWeaknesses] |

| Opportunities | Threats |
|---|---|
| [RelationshipOpportunities] | [RelationshipThreats] |

[View in Salesforce](https://[instanceUrl]/lightning/r/AccountPlan/[Id]/view)
```

Quote any blank field as "blank" rather than omitting it. Always include the record link.
