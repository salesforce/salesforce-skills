---
name: handle-objection
description: Work through a live objection or competitive threat - what's really being said, the response that has worked before, and the proof points to use, grounded in your own win/loss history and customer quotes. Use when the user says "they said we're too expensive", "how do I respond to [objection]", "[competitor] is in the deal", "help me handle this pushback", or pastes an objection from an email or call.
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


# Handle Objection

A grounded response, not a script: what the objection means, how deals like it went, and your own customers' evidence that answers it. Inputs: **the objection** (their words / email / transcript) and **the deal** (opp for context). Common objections/competitors/differentiators are external — infer from org data or ask once; never invent.

## 1. Classify what's really being said

Map to type: price/value · timing/priority · competitive · risk/trust · authority ("check with…") · status quo. Distinguish an **objection** (reason not to buy) from a **negotiation move** (reason to buy cheaper) — the response differs.

## 2. Pull your own evidence (fire in parallel)

- **Win/loss** (`win-loss-review`): how deals with this objection ended; what wins did differently.
- **Customer voice** (`customer-voice`): verbatim quotes speaking to this exact concern.
- **Docs**: case studies, ROI, security/compliance already cleared for external use.
- **The deal itself**: what this customer already told you (their stated pain/metrics are the best rebuttal).

## 3. Build the response

```
# Objection: "<their words>"
## What's underneath it
<1–2 sentences: the real concern; objection vs negotiation>
## The response
<talk track in your voice, 3–5 sentences: acknowledge → answer with their own stated goals + one proof point → question that moves it forward>
## Proof points to have ready
- <customer quote / case study / metric — with source>
## If it's <competitor>
- Where they're strong (be honest) + where this customer's needs don't match it; the trap question that surfaces the difference
## What history says
<from win/loss: how often this objection appears in wins vs losses, and what winning reps did next>
## Don't
- <the response that historically loses this — overdiscounting, feature-dumping, arguing>
```

Objection arrived in writing? Offer to draft the reply via `draft-outreach`.
