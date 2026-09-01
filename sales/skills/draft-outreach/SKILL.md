---
name: draft-outreach
description: Draft a personalized outreach email to a prospect and create it as a email draft. Use when the user asks to "draft outreach to [person/company]", "write a cold email to", "reach out to", or "follow up with [prospect]".
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


# Draft Outreach

Ground → (read + evidence searches, all in ONE turn) → draft → create draft.

Value prop, proof points, voice/tone, signature block, and competitors (to avoid naming unprompted) are external knowledge — infer from the org's own closed-won data and product catalog, or ask the user once. Never invent them.

## 1. Ground (hardcoded — Contact only)

Ground **only Contact** — it always exists (naming a missing custom object fails the whole call). Its fields + childRelationships reveal this org's persona/segment schema; don't assume names.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { objectInfos(apiNames: [\\\"Contact\\\"]) { fields { ApiName label dataType relationshipName } childRelationships { childObjectApiName relationshipName } } } }\"}" })
```

Step 1 is the authority on names — use exact strings from it, never guess. From the result, note: (a) scalar `__c` fields (persona, segment, relationship-context, etc.) — take their `{ value }`; (b) each lookup field's exact `relationshipName` to span for a related record's name; (c) each child `relationshipName` beyond the two standard ones below.

## 2. Read (fill from step 1)

`%NAME%` = recipient's name (swap `Name: { like: ... }` for `Email: { eq: \"%EMAIL%\" }` when given an email instead). **Reference-field rules (avoids the retry loop):**
- A scalar/`__c` field → `Field__c { value }`. `displayValue` is null for Id fields here — don't rely on it.
- To get a **related record's name**, span via the exact `relationshipName` from Step 1. Do NOT append `{ ... }` to a raw `Id`/`__c` field.
- Only span relationships Step 1 actually returned. No usable relationshipName → take the `__c { value }` (the Id) and move on — **do not retry**.

Insert `<CONTACT_CUSTOM>` = confirmed scalar `__c { value }` fields; `<REL_BLOCKS>` = one block per confirmed org-specific relationship. `Account` (parent) and `OpportunityContactRoles` (child) always work.

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Contact(where: { Name: { like: \\\"%NAME%\\\" } }, first: 1) { edges { node { Id Name { value } Title { value } Email { value } LastActivityDate { value } <CONTACT_CUSTOM> Account { Name { value } Industry { value } Opportunities(where: { IsClosed: { eq: false } }, first: 5) { edges { node { Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } } } } } <REL_BLOCKS> OpportunityContactRoles { edges { node { Role { value } IsPrimary { value } Opportunity { Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } IsClosed { value } } } } } Tasks(first: 3, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Subject { value } ActivityDate { value } Description { value } Type { value } } } } Events(first: 3, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Subject { value } ActivityDate { value } Description { value } } } } } } } } } }\"}" })
```

Empty `edges` → broaden `%NAME%`. **Prior-contact detection reads BOTH children plus the email search** — the `Tasks` child carries logged emails, the `Events` child carries calls/meetings; take the most-recent touch across Tasks, Events, AND the 2b email threads (a prior touch logged as an Event is invisible if you look only at Tasks). `Task.Type` labels the last touch email-vs-call for the warm/cold call. `Tasks`/`Events` are standard activity children — but if a read errors on `Events` (`FieldUndefined`/`InvalidSyntax`), re-issue it **without** the `Events` block (Tasks-only) rather than failing the whole read; don't retry byte-identical. `Account.Opportunities` (open) surfaces a deal-in-flight hook even when the contact has no contact-role of their own. Given a **company only** (no person named): skip Step 1 grounding and dispatch this instead — standard fields only, no custom-field grounding needed; its `Tasks`/`Events` children fill the "Prior contact" line for company-level asks:

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(where: { Name: { like: \\\"%COMPANY%\\\" } }, first: 1) { edges { node { Id Name { value } Industry { value } Owner { Name { value } } Opportunities { edges { node { Name { value } StageName { value displayValue } Amount { value displayValue } CloseDate { value } IsClosed { value } } } } Tasks(first: 3, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Subject { value } ActivityDate { value } Description { value } Type { value } } } } Events(first: 3, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Subject { value } ActivityDate { value } Description { value } } } } } } } } } }\"}" })
```

## 2b. Evidence (run IN PARALLEL with step 2 — same turn, issue all at once)

**Issue step 2 and all of step 2b as tool calls in a single turn.** They key on the recipient/company name from the request, not on the SF result, so batch them together:
- **email**: prior threads with this recipient — last exchange date + topic (warm follow-up vs. cold)
- **docs**: recent notes/transcripts mentioning the account — hooks, decisions, objections
- **slack**: internal mentions of the account/contact — context worth referencing

Use whatever email/doc/Slack tools are available; skip silently if none are present (SFDC-only is fine). Cite source + date for anything you use.

## 3. Draft the email (cite every claim; invent nothing)

If step 2 AND 2b both come back empty (no SFDC record, no prior threads): run a lightweight pass — company basics + one recent signal — before drafting; never draft on invented context.

Structure (body under 120 words):
1. **Relevance line** — one sentence proving you did homework, sourced from step 2/2b. Never "I came across your company."
2. **Value bridge** — connect their situation to the value prop; use a proof point if it fits naturally.
3. **Soft ask** — one low-friction CTA. Default: "Worth a 20-min call to see if this maps to what you're working on?"
4. **Signature** — the block the user provided, or sampled from sent mail.

Tone: match the team voice (sampled from sent mail, or as directed); concise and direct — no "hope this finds you well," no paragraph intros.

Subject: 4-7 words, specific not salesy — references the hook, not the product.

## 4. Create email draft

Use email to create a draft (do not send): To = recipient email, Subject = [generated], Body = [generated]. Return the draft ID/link.

## 5. Widget (default output when `display_widget` is present: Cowork/desktop/web)

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

The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left — this echo path compiles no expressions), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (the `{{contextRows}}` datagrid array) becomes the typed literal — arrays stay arrays; a `{{token}}` inside a larger string is interpolated as text. Fabricate nothing — every context row must trace to a real Step 2/2b finding; drop rows you lack data for rather than pad. Tokens: `{{draftTitle}}` header page-title ("Outreach — [Name], [Title] @ [Company]"); `{{draftSubtitle}}` caption subhead summarizing CRM status, prior-contact recency, and the hook; `{{intentBadge}}` status badge = the outreach intent (COLD INTRO / WARM FOLLOW-UP / RE-ENGAGE / REFERRAL / EVENT FOLLOW-UP); `{{contextRows}}` datagrid array (Source badge, What-it-told-us text), each row `{ source: { value, badgeVariant }, detail }` with badgeVariant `"info"` (CRM), `"secondary"` (prior email/activity), `"success"` (research signal); `{{subject}}` / `{{emailBody}}` the draft callout title/description — the exact subject and body created in Step 4, verbatim, not a paraphrase; `{{reviseLabel}}` / `{{reviseMsg}}` primary button (`action/sendMessage`) label + first-person revision instruction; `{{draftUrl}}` secondary button (`action/openLink`) = the created draft's deep link from Step 4 — omit that button if the draft tool returned no link. Before calling, confirm no `{{…}}` or `{!…}` remain and `{{subject}}`/`{{emailBody}}` match the Step 4 draft verbatim.

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
                  { "definition": "tile/icon", "attributes": { "name": "mail", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{draftTitle}}", "variant": "page-title" } }
                ]
              },
              { "definition": "tile/badge", "attributes": { "label": "{{intentBadge}}", "variant": "info" } }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{draftSubtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Context used to personalize",
              "appearance": "striped",
              "size": "sm",
              "columns": [
                { "key": "source", "header": "Source", "type": "badge" },
                { "key": "detail", "header": "What it told us", "type": "text" }
              ],
              "rows": "{{contextRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "info",
              "eyebrow": "DRAFT EMAIL",
              "title": "{{subject}}",
              "description": "{{emailBody}}"
            },
            "children": [
              {
                "definition": "tile/row",
                "attributes": { "gap": "sm", "align": "center", "isWrapped": true },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{reviseLabel}}",
                      "variant": "primary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{reviseMsg}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "Open draft in email",
                      "variant": "secondary",
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{draftUrl}}" } }
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
## 6. Text — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Outreach Draft → [Recipient Name], [Title] @ [Company]

**Context used:**
- CRM: [summary of SFDC findings or "net new"]
- Prior contact: [last thread date + topic, or "none - cold"]
- Hook: [the relevance angle used]

---
**Subject:** [subject line]

[email body]
---

✉️ Created as email draft: [link/ID]
Review, edit, and send from your drafts folder.

**Suggested SFDC logging** (via `log-activity`, or manually on a read-only connector)**:**
- Log Activity on [Account/Contact]: "Outbound email - [subject]"
```
