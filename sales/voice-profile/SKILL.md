---
name: voice-profile
description: Mine your email sent folder to learn how you actually write, then present it so you can paste the profile into your own Claude instructions. Draft-outreach and inbox-sweep will then match your real voice. One-time setup. Use when the user says "learn my voice", "build my voice profile", "make drafts sound like me", or during initial plugin setup. IMPORTANT: Exit gracefully if email is not available - do not spiral attempting unavailable operations.
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


# Voice Profile

Extract your real writing patterns from sent email → a pasteable Voice & Messaging profile (draft-outreach and inbox-sweep reuse it). No Salesforce. One-time setup.

## 0. Email available? (hard gate)

No email connected / can't read sent mail → exit gracefully, exactly:

```
To build your voice profile, I need access to your email sent folder. Please connect email via /mcp and re-run this skill.
```

Do NOT attempt workarounds, ask clarifying questions, or invent a profile. Just stop.

## 1. Pull + clean

Search sent folder: last 60 messages to **external** recipients (not your own domain). Dedupe by thread (keep the opener over replies). Strip quoted/forwarded text, signature blocks (repeated trailing lines), calendar boilerplate.

## 2. Analyze the cleaned set

- **Greeting** — top 3 openers + frequency ("Hi [Name]," 60% / …)
- **Sign-off** — top 3 closers + frequency
- **Length** — median words, openers vs replies
- **Structure** — bullets vs prose, paragraph count
- **Tone** — formality (contractions? exclamations? lowercase?), directness (questions vs statements)
- **Phrases you use** — recurring non-generic 3–5 word phrases
- **What you don't do** — notable absences (no "hope this finds you well", no emoji, etc.)

## 3. Output — the profile + 2 anchors

```
# Voice Profile — built from <N> sent emails

## Voice & Messaging
**Greeting:** <top opener> (<N%>)
**Sign-off:** <top closer>
**Length:** ~<N> words first-touch, ~<N> replies
**Structure:** <prose / bullets / mixed>
**Tone:** <2–3 adjectives>
**Phrases I use:** "<phrase>" · "<phrase>"
**What I don't do:** <pattern> · <pattern>
**Signature block:** <detected signature>

## Anchor examples
**Opener:** > <excerpt from a real sent email>
**Reply:** > <excerpt>

Look right? If you'd like, paste this into your own Claude instructions so draft-outreach and inbox-sweep can reuse your voice.
```
