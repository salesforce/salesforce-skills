---
name: call-prep
description: Pre-call brief for an upcoming meeting - attendees, account history, prior call notes, open opportunity status, and suggested discovery questions. Use when the user asks "prep me for [meeting/company]", "call prep", "prep for my call with [customer/account]", "what do I need to know before my [time] call", or runs /call-prep. IMPORTANT: This is for prepping CUSTOMER/PROSPECT meetings - if the user is prepping for a 1:1 with a sales rep on their team, use rep-context instead.
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

# Rules:


# Call Prep

Resolve meeting → ground → read account → (calendar + email + docs + slack searches, all in ONE turn with the SF read) → assemble brief. Qualification framework (BANT/MEDDIC/etc.), value prop, and competitors are external knowledge — infer from org data or ask once. Never invent.

## 1. Resolve meeting

**Inputs:** a calendar event (by time, title, or "my next call"), OR an account name + time. If neither given, list today's external meetings and ask which one.

**1a. Find the owner (if named rep)**

- **"my next call"** (default) → skip to 1b with `scope: MINE`
- **"[Rep]'s next call"** → resolve one User. Shared/demo orgs collide (one name → base user + regional variants like `(AM)`/`(BK)`). Pull enough to disambiguate:
  ```
  dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
    queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { User(where: { Name: { like: \\\"%REP%\\\" } }, first: 10) { edges { node { Id Name { value } Email { value } IsActive { value } } } } } } }\"}" })
  ```
  **One match** → take its Id. **Several** → list them (Name · Email · active? · Id) and ask user to pick. Then filter Events by `OwnerId: { eq: \"<UserId>\" }` in 1b.

**1b. Find the meeting**

Build the Event query based on input pattern. All patterns share the node shape (`Id Subject StartDateTime EndDateTime Location WhatId WhoId Description`). Combine filters with `and: [...]` when needed.

**Pattern: "my next call"** (scope: MINE, StartDateTime >= TODAY, first: 1):
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Event(scope: MINE, where: { StartDateTime: { gte: { literal: TODAY } } }, first: 1, orderBy: { StartDateTime: { order: ASC } }) { edges { node { Id Subject { value } StartDateTime { value } EndDateTime { value } Location { value } WhatId { value } WhoId { value } Description { value } } } } } } }\"}" })
```

**Pattern: "[Rep]'s next call"** (OwnerId from 1a, StartDateTime >= TODAY, first: 1):
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Event(where: { OwnerId: { eq: \\\"<UserId>\\\" }, StartDateTime: { gte: { literal: TODAY } } }, first: 1, orderBy: { StartDateTime: { order: ASC } }) { edges { node { Id Subject { value } StartDateTime { value } EndDateTime { value } Location { value } WhatId { value } WhoId { value } Description { value } } } } } } }\"}" })
```

**Pattern: specific event name** (e.g. "City of Hope call") — match Subject with LIKE, widen window to catch it (next 30 days), list if multiple:
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Event(scope: MINE, where: { Subject: { like: \\\"%EVENTNAME%\\\" }, StartDateTime: { gte: { literal: TODAY }, lte: { range: { next_n_days: 30 } } } }, first: 10, orderBy: { StartDateTime: { order: ASC } }) { edges { node { Id Subject { value } StartDateTime { value } EndDateTime { value } Location { value } WhatId { value } WhoId { value } Description { value } } } } } } }\"}" })
```
**One match** → use it. **Several** → list them (Subject · StartDateTime · Id) and ask user to pick. **Zero** → broaden `%EVENTNAME%` or ask user for account name directly.

**Pattern: time-based** (e.g. "call next thursday", "meeting tomorrow") — parse to date range. Use relative date filters:
- **"tomorrow"**: `StartDateTime: { gte: { range: { next_n_days: 1 } }, lte: { range: { next_n_days: 1 } } }`
- **"next thursday"**: compute day offset (if today = Monday, thursday = 3 days out) → `gte: { range: { next_n_days: 3 } }, lte: { range: { next_n_days: 3 } }`
- **"next week"**: `gte: { range: { next_n_days: 7 } }, lte: { range: { next_n_days: 14 } }`

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Event(scope: MINE, where: { StartDateTime: { gte: { range: { next_n_days: <OFFSET_START> } }, lte: { range: { next_n_days: <OFFSET_END> } } } }, first: 10, orderBy: { StartDateTime: { order: ASC } }) { edges { node { Id Subject { value } StartDateTime { value } EndDateTime { value } Location { value } WhatId { value } WhoId { value } Description { value } } } } } } }\"}" })
```
**One match** → use it. **Several** → list them and ask user to pick.

**Pattern: account name directly** (e.g. "prep for City of Hope", "call with Acme") — no meeting specified. Skip Event query entirely, treat input as customer company name, jump to Step 2.

**Pattern: Event ID** (if user pastes SFDC Id `00U...`) — direct lookup:
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Event(where: { Id: { eq: \\\"<EventId>\\\" } }, first: 1) { edges { node { Id Subject { value } StartDateTime { value } EndDateTime { value } Location { value } WhatId { value } WhoId { value } Description { value } } } } } } }\"}" })
```

**Extract:** title (Subject), time (StartDateTime/EndDateTime), WhatId (if `001…` → Account, `006…` → Opportunity), WhoId (Contact), description/agenda, meeting link (Location). From Description text or WhoId email domain, identify customer company.

## 2. Ground (hardcoded — Account only; fire with step 3 if independent)

Ground **only Account** — it always exists. Its fields + childRelationships reveal this org's account/opp/contact schema.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Account\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

From the result: (a) scalar `__c` fields (industry, size, qualification, etc.) — take their `{ value }`; (b) each lookup field's exact `relationshipName` to span for a related record's Name; (c) each child `relationshipName` (Opportunities, Contacts, ActivityHistories).

**Batch with step 3 if you already have the customer company name from step 1.** If step 1's WhoId email or Description text gave you the domain/company, fire objectInfo + account read + evidence in ONE turn.

## 3. Read account (template — fill from step 2)

Insert `<ACCOUNT_CUSTOM>` = confirmed scalar `__c { value }` fields (industry, size, qualification signals, etc.); `<REL_BLOCKS>` = confirmed relationships. **Nest children in ONE dispatch:**

- **Children:** `Opportunities(where: { IsClosed: { eq: false } }, orderBy: { LastModifiedDate: { order: DESC } }, first: 5) { edges { node { Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } NextStep { value } LastActivityDate { value } } } }`
- **Children:** `Contacts(where: { Email: { in: [<ATTENDEE_EMAILS>] } }) { edges { node { Name { value } Title { value } Email { value } } } }`
- **Children:** `ActivityHistories(orderBy: { ActivityDate: { order: DESC } }, first: 5) { edges { node { Subject { value } ActivityDate { value } Description { value } } } }`

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { <DOMAIN_FILTER> }, first: 1) { edges { node { Id Name { value } Industry { value } NumberOfEmployees { value } Type { value } Description { value } <ACCOUNT_CUSTOM> Owner { Name { value } } Opportunities(where: { IsClosed: { eq: false } }, orderBy: { LastModifiedDate: { order: DESC } }, first: 5) { edges { node { Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } NextStep { value } LastActivityDate { value } } } } Contacts(where: { Email: { in: [<ATTENDEE_EMAILS>] } }) { edges { node { Name { value } Title { value } Email { value } } } } ActivityHistories(orderBy: { ActivityDate: { order: DESC } }, first: 5) { edges { node { Subject { value } ActivityDate { value } Description { value } } } } } } } } } }\"}" })
```

**Reference-field rules:** To span a related record's name, use the exact `relationshipName` from Step 2. Do NOT append `{ ... }` to the raw `__c` field — that fails. If no usable relationshipName, take the `Id` and move on — **do not retry**.

**If `<DOMAIN_FILTER>` matches more than one Account** (shared/demo orgs collide — duplicate seed data, regional subsidiaries on the same domain), don't silently take `first: 1`. Drop to `first: 10`, Account-level fields only (Name, Website, Owner — no Opportunities/Contacts probe), list the candidates, and ask the user to pick before reading further.

## 3b. Evidence (run IN PARALLEL with step 3 — same turn)

**Issue step 3 and all of step 3b as tool calls in a single turn.** They're independent (searches key on account name/attendee emails, not the SF result):
- **email**: threads with the attendee emails in last 90d → last 2–3 exchanges (date, who, what discussed/committed)
- **docs**: docs mentioning the account name → prioritize files with "transcript", "notes", or "plan" in title, most recent first. Read top 1–2 and extract: key topics, open questions, commitments made.
- **slack**: account name in last 30d → internal context (deal desk threads, exec mentions, support escalations)

Use whatever email/doc/Slack search tools are available. If none present, skip silently (SF-only is fine). Cite source + date for anything you use.

**Perf guardrail:** Do NOT fire additional SF dispatches for `Task` or `EmailMessage` — the step 3 read + external evidence has the data.

## 4. Attendee profiles

For each external attendee: their SFDC Contact title, plus a 1–2 line summary of what they likely care about (from title + prior interactions from evidence). Flag anyone who's new (not in SFDC Contacts, no prior email thread).

## 5. Call plan

Based on opportunity stage and the qualification framework (inferred from org data or provided by the user):

- **Objective for this call:** [what should be true after the call that isn't before — e.g. "confirm budget owner and timeline" or "get technical validation scheduled"]
- **3–5 discovery questions:** tailored to the stage and any gaps in the qualification framework. Pull from prior notes if there were unanswered questions.
- **Likely objections:** infer from prior conversations or skip.
- **What to bring:** any doc/proposal/demo that was committed in prior threads.


## 6. Dashboard widget (editorial layout)

When the `display_widget` tool is available (Claude Cowork, the desktop app, the web app), render the call-prep brief as a visual widget instead of the Step 7 text. The layout follows editorial restraint: header with icon, one-line subhead, two datagrids (attendees and talk-track topics), and one synthesis callout with two buttons. When `display_widget` is unavailable (e.g. a terminal) the Step 7 markdown is the whole output, so produce it only then.

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

- [ ] Every `{{token}}` replaced with a resolved literal — no `{{…}}`, no `{!…}`.
- [ ] `{{attendeeRows}}` and `{{topicRows}}` are typed arrays — each row object has the required keys and `_tone`/`_status`.
- [ ] Every button's `onClick` is `action/sendMessage` or `action/openLink` with real content.
- [ ] No charts (meter/piechart/chart/heatmap/waterfall) — only datagrids.
- [ ] The callout is `variant: "info"` and closes the widget.
- [ ] The Step 7 markdown is produced only when `display_widget` is unavailable (the terminal fallback) — not alongside a rendered widget.
- [ ] No prose written before or after this call — no input narration, no transition text, no summary (only applies when display_widget is available; if unavailable, produce the text fallback section below).
- [ ] I am producing zero prose before or after this call. If I am tempted to summarize findings, I must not.

The widget template is embedded below. It is a skeleton: replace every `{{token}}` with a fully-resolved literal computed from the brief you built in Steps 1–5 — this echo path does no expression compilation, so no `{!…}` bindings. See `sample-data.json` in this dir for a fully-worked example.

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
                  { "definition": "tile/icon", "attributes": { "name": "phone", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{title}}", "variant": "page-title" } }
                ]
              }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{subtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Who's on the call",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                { "key": "name", "header": "Attendee", "type": "avatar" },
                { "key": "role", "header": "Role", "type": "text" },
                { "key": "stance", "header": "Stance", "type": "badge" },
                { "key": "watch", "header": "Watch for", "type": "text" }
              ],
              "rows": "{{attendeeRows}}"
            }
          },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Talk track — open items to resolve",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                { "key": "topic", "header": "Topic", "type": "text" },
                { "key": "state", "header": "State", "type": "badge" },
                { "key": "ask", "header": "Your ask", "type": "text" }
              ],
              "rows": "{{topicRows}}"
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
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{oppUrl}}" } }
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

What each block shows, from data you already have:

- **Header** — phone icon + serif `page-title` (`{{title}}`, "Call prep — [Meeting title]").
- **Subhead caption** — `{{subtitle}}` (one line: time, attendees, deal size, stage).
- **Attendee datagrid** (`{{attendeeRows}}`) — one row per attendee. Columns: Attendee (avatar), Role (text), Stance (badge), Watch for (text). Each row carries `_tone` (success/warning/error/default) and `_status` (Ally/Neutral/Blocker); the renderer auto-injects a leading Status column from `_status`.
- **Talk track datagrid** (`{{topicRows}}`) — one row per open item. Columns: Topic (text), State (badge), Your ask (text). Each row carries `_tone` and `_status` (Must land/Push/Defuse/Confirm).
- **One synthesis callout** (`variant: "info"`) — `{{calloutTitle}}` and `{{calloutDesc}}` (the call's goal and what success looks like). Two buttons: a primary "Draft call agenda" (`{{ctaLabel}}` / `{{ctaMsg}}`, `action/sendMessage`) and a secondary "View in Salesforce" (`{{oppUrl}}`, `action/openLink`).

**Hydration rules:**
1. Start from the embedded template above — a valid-JSON widget-definition envelope whose leaf values carry `{{token}}` placeholders.
2. Resolve every `{{token}}`. A value that is **only** a `{{token}}` (datagrid `rows`) becomes the resolved **typed** literal — arrays stay arrays. A `{{token}}` **inside** a larger string is interpolated as text.
3. `{{attendeeRows}}` is an array of attendee objects — each with `name` (plain string — format as the person's display name (e.g. "Dana Kwon"); names must be plain strings, not objects: use `Contact.Name.value` from the SF response), `role`, `stance` (`{ value, badgeVariant }`), `watch`, `_tone`, and `_status`. `{{topicRows}}` is an array of topic objects — each with `topic`, `state` (`{ value, badgeVariant }`), `ask`, `_tone`, and `_status`.
4. The result is hydrated widget definition (no `{{…}}` placeholders remain). Then:

```
display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated widget definition> })
```

**Binding rules:**
- Resolve every `{{token}}` to a literal before calling — arrays stay arrays (`{{attendeeRows}}`, `{{topicRows}}`), strings stay strings.
- `datagrid` rows: one per attendee (name as avatar, role, stance badge, watch text), one per topic (name, state badge, ask text). Stance badge (`stance.badgeVariant`) reflects alignment — `"success"` (Champion/Ally), `"warning"` (Neutral), `"error"` (Blocker). State badge (`state.badgeVariant`) reflects urgency — `"error"` (Open/Critical), `"warning"` (Pending/Risk), `"success"` (Agreed/Resolved). `_status` drives the auto Status column.
- Callout buttons: the primary is `action/sendMessage` with a first-person `content` prompt (`{{ctaMsg}}`, e.g. "Draft an agenda for the Cobalt contract walkthrough…"); the secondary is `action/openLink` with `{{oppUrl}}` — the opportunity's Lightning URL (`https://<myDomain>/lightning/r/Opportunity/<Id>/view`), opening a new tab. Omit the openLink button if you lack the Id.
- No fabricated content — quote blank fields as blank rather than inventing them; drop attendees or topics you have no data for.


> **Before writing any text:** confirm `display_widget` returned an explicit error. If it returned any non-error result, you are in widget mode — stop. The text section below does not exist in widget mode.

## 7. Output

```
# Call Prep: [Account] - [Meeting Title]
[Date Time] | [Attendees]

## Account Snapshot
- [Industry, size, type] | Owner: [Name]
- Open opp: **[Name]** - [Stage] $[Amount] closing [Date]
  Next step (SFDC): [NextStep or "blank"]

## Who's in the room
- **[Name]**, [Title] - [1–2 line context, prior interactions]
- **[Name]**, [Title] - ⚠ NEW (no prior contact)
...

## What's happened so far
- [Date] - [Last call summary from transcript]
- [Date] - [Email thread summary]
- [Date] - [Slack/internal context if any]

## Open threads
- [Unanswered question or commitment from prior notes]
...

## This call
**Objective:** [one sentence]

**Questions to ask:**
1. [Stage-appropriate discovery Q]
...

**Likely objections:** [list]

**Bring:** [any committed deliverables]
```
