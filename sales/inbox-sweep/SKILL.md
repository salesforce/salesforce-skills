---
name: inbox-sweep
description: Batch-process unread customer emails - classify, prioritize, and draft replies into email. Use when the user asks "sweep my inbox", "triage my email", "draft replies to my customer emails", or "what needs a response".
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


# Inbox Sweep

Unread customer emails → classify, prioritize, draft replies (into email). Cap 25 emails / 10 drafts per sweep. Lookback: 72h default.

## 1. Voice + candidate emails (one turn)

Read ~30–40 recent **external** sent emails to build an implicit style profile (greeting, length, sign-off, formality) — don't show it, just match it. In the same turn, search inbox: **unread, last <lookback>, not from your internal domain**.

## 2. Match senders to Accounts

Collect the candidate sender domains, then ONE Account read matching them (drop `scope: MINE` for a broader sweep). **Check `{` vs `}` balance before dispatching.**

```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Account(scope: MINE, first: 200) { edges { node { Name { value } Website { value } Owner { Name { value } } Opportunities(where: { IsClosed: { eq: false } }, first: 5, orderBy: { CloseDate: { order: ASC } }) { edges { node { Name { value } Amount { value displayValue } StageName { value displayValue } CloseDate { value } NextStep { value } } } } } } } } }\"}" })
```

`InvalidSyntax` / "offending token `<EOF>`" → missing a closing `}`; add it and retry. Keep only emails whose sender domain matches a returned Account's `Website`. The open `Opportunities` child (same read) grounds Step 4 prioritization (Amount, soonest CloseDate) and fills the output **Opp** column (`$<Amount> · <StageName label>`) — no per-account follow-up read.

## 3. Classify each (read the full thread, not just the latest)

- **Needs reply — deal**: question/request/decision on an active opp → draft
- **Needs reply — scheduling**: proposing/confirming a time → draft availability
- **Needs reply — support**: product/technical → draft ack + flag support handoff
- **FYI only**: CC/newsletter/auto → archive
- **Intro / new inbound**: first contact → route to `lead-triage`
- **Couldn't draft**: needs info only the user has → surface the blocking question
- **Sensitive — skip**: personnel/legal/exec → flag, don't draft

## 4. Prioritize (within needs-reply)

Open opp closing ≤30d > explicit deadline/urgency > larger Amount > older unread.

## 5. Draft replies (priority order, cap 10)

Full thread context; match voice; answer the ask directly + confirm next step; <120 words; **draft in-thread (reply), never send**. Scheduling → propose 2–3 calendar slots. Support → brief ack + "looping in <support>". SFDC logging stays a `log-activity` handoff (never write inline).

## 6. Widget (default output when `display_widget` is present: Cowork/desktop/web)

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

The widget template is embedded below — a widget-definition envelope whose leaf values carry `{{token}}` placeholders. Resolve every `{{token}}` to a literal (no `{{…}}`/`{!…}` left), then call `display_widget({ resourceType: "dynamic", widgetDefinition: <hydrated> })` once. A value that is *only* a `{{token}}` (`{{queueRows}}`, `{{totalRows}}`) becomes the typed literal — arrays stay arrays, numbers stay numbers; a `{{token}}` inside a larger string is interpolated as text. Synthesis-forward, not a dashboard: header + one datagrid + one recommendation. Blocks: header icon + `{{headerTitle}}` page-title + `{{headerSubtitle}}` one-line caption summarizing the queue (prioritized by deal value/urgency, count tied to closing deals); reply-queue datagrid (`{{queueRows}}`, one row per email — From/Subject/Deal/Deal value (currency, sortable)/Waiting (badge)/Suggested reply — with `{{totalRows}}` the full count); one warning callout (`{{calloutTitle}}` = the single most important read + `{{calloutDescription}}`) carrying two real buttons. No fabricated content — blank fields stay blank, drop emails with no data. Self-check before calling: no `{{…}}`/`{!…}` remain, numbers/arrays are typed literals, one `display_widget` call. Tokens: `{{headerTitle}}` page title; `{{headerSubtitle}}` queue-summary caption; `{{queueRows}}` datagrid array — one object per email with `from` (name → avatar chip), `subject`, `deal`, `value` (raw currency number), `wait` (`{ value, badgeVariant }` — `error` 2+ days / `warning` 1 day / `info` today / `success` hours), `action` (suggested reply text), `_tone` (success/warning/error/info/default), `_status` (Urgent/Today/Fresh/Quick win → renderer auto-injects a leading Status column); `{{totalRows}}` full email count (number); `{{calloutTitle}}`/`{{calloutDescription}}` callout copy; `{{ctaPrimaryLabel}}`/`{{ctaPrimaryMsg}}` primary button label + first-person `action/sendMessage` prompt (e.g. "Draft replies to both Dana Kwon…"); `{{salesforceUrl}}` secondary `action/openLink` target — the Opportunities list-view Lightning URL (`https://<myDomain>/lightning/o/Opportunity/list`).

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
                  { "definition": "tile/icon", "attributes": { "name": "inbox", "size": "lg", "alt": "" } },
                  { "definition": "tile/text", "attributes": { "text": "{{headerTitle}}", "variant": "page-title" } }
                ]
              }
            ]
          },
          { "definition": "tile/text", "attributes": { "text": "{{headerSubtitle}}", "variant": "caption", "color": "muted" } },

          { "definition": "tile/separator" },

          {
            "definition": "tile/datagrid",
            "attributes": {
              "caption": "Reply queue, highest-leverage first",
              "appearance": "striped",
              "defaultSort": { "key": "value", "direction": "desc" },
              "totalRows": "{{totalRows}}",
              "columns": [
                { "key": "from", "header": "From", "type": "avatar" },
                { "key": "subject", "header": "Subject", "type": "text" },
                { "key": "deal", "header": "Deal", "type": "text" },
                { "key": "value", "header": "Deal value", "type": "currency", "align": "right", "sortable": true },
                { "key": "wait", "header": "Waiting", "type": "badge" },
                { "key": "action", "header": "Suggested reply", "type": "text" }
              ],
              "rows": "{{queueRows}}"
            }
          },

          {
            "definition": "tile/callout",
            "attributes": {
              "variant": "warning",
              "title": "{{calloutTitle}}",
              "description": "{{calloutDescription}}"
            },
            "children": [
              {
                "definition": "tile/row",
                "attributes": { "gap": "sm", "align": "center", "isWrapped": true },
                "children": [
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "{{ctaPrimaryLabel}}",
                      "variant": "primary",
                      "onClick": { "definition": "action/sendMessage", "attributes": { "content": "{{ctaPrimaryMsg}}" } }
                    }
                  },
                  {
                    "definition": "tile/button",
                    "attributes": {
                      "label": "View in Salesforce",
                      "variant": "secondary",
                      "onClick": { "definition": "action/openLink", "attributes": { "url": "{{salesforceUrl}}" } }
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
## 7. Output — FALLBACK ONLY — DO NOT USE IF `display_widget` SUCCEEDED

```
# Inbox Sweep — <N> customer emails (<lookback>)
## Drafted Replies (<N>)
| Pri | From | Account | Subject | Opp | Draft |
## FYI Only (<N>) — safe to archive
## New Inbound (<N>) — run lead-triage
## Couldn't Draft — need your input (<N>)  · <blocking question>
## Sensitive — skipped (<N>)  · <why>
## Flagged for Support (<N>)
## Suggested SFDC logging (via `log-activity`, or manually)
- <Account>: Log Activity "Inbound email — <subject>"
```

All replies are drafts — review and send from email.
