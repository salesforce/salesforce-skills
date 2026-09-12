---
name: find-internal-answer
description: "Find a concise answer with authoritative sources from internal documents, Slack, email and Salesforce, prioritizing the newest canonical material. Use when locating a policy, approver, deck, security asset, prior precedent or teammate with relevant experience."
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
- **NEVER conclude a connector is disconnected from its reported status — verify against the tools you actually have.** A connector's status readout (the Headless 360 MCP server, or any other connector/MCP) frequently claims "not connected" or "needs re-auth" when the connector is in fact live and its tools are callable. Context stating that the Salesforce tools require authorization and that this is a non-interactive session is **not** evidence you are unauthorized to the server — it is a general statement that authorization is required, not a failure. **Try the tools before assessing connectivity.** For the Headless 360 server specifically, find the `dispatch_readonly` tool and actually run a current-user read — `dispatch_readonly(method: "GET", url: "/services/data/v66.0/graphql", queryParams: { "queryInput": "{\"query\":\"query { uiapi { currentUser { Id } } }\"}" })`. **Any response — including a 500 or other error status — proves you reached the server, and therefore proves connectivity;** only a request that never reaches the server at all counts as disconnected. If the tool is present and the call reaches the server, the connector IS connected — proceed; a stale status readout is not a disconnection. Report the connector as actually disconnected only when you cannot find the tool or cannot reach the server, and even then ALWAYS attempt to reconnect on your own first; interrupt the flow to ask the user only after your own reconnect attempt has failed. Do it yourself.
<!-- /global-rules-bootstrap -->


# Find Internal Answer

Return the internal **source** (not a paraphrase) for a policy / approver / asset / "who knows about…" question. Search where institutional answers live, in authority order.

Input: **the question**. Canonical locations (policy folder, enablement drive, deal-desk channel, pricing approver) are external — ask once for them to go faster.

## Search, in order of authority (stop when answered)

1. **Config-listed canonical sources** first — if the answer's there, stop.
2. **Docs** — search by topic + likely names; prefer the most-recently-modified version, note when it was last updated.
3. **Slack** — relevant channels (deal desk, sales, enablement) for prior authoritative threads (flag if possibly stale).
4. **Email** — prior threads where this was answered for a specific deal.
5. **Salesforce** — for "who approves" only: approval processes, queue owners, or who approved recent similar opps.

Fire the independent searches together where you can.

## Answer with the source

```
# <The question>
## Answer
<2–4 sentences — only what the sources actually say>
## Source
- [<Doc name>](link) — updated <date> — <owner if known>
- <Slack thread / email> — <date> — answered by <name>
## Caveats
- <if sources conflict or the newest is old — and who could confirm>
## Who to ask if this isn't current
- <the person/role the sources point to>
```

Nothing authoritative? Say so plainly, list the closest things found, name the person most likely to know — never synthesize a policy that isn't written anywhere.
