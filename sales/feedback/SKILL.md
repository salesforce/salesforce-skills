---
name: feedback
description: "Capture free-form session feedback on skills used in the current conversation and post it to the team feedback Slack channel. Identifies all skills used, asks for natural feedback, processes it to extract insights, and posts both raw and processed feedback. Use when the user explicitly says \"feedback\", \"rate that\", \"log feedback\", or \"send feedback\"."
model: claude-sonnet-5
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
 
# Feedback
 
Capture free-form session feedback on skills used in the current conversation and post it as a formatted message to the team feedback Slack channel (configured in Step 1).
 
## Inputs
 
This skill runs **when the user explicitly invokes it** (via `/feedback` or phrases like "feedback", "rate that", "log feedback", "send feedback").
 
## Step 1 - Slack channel configuration
 
**Target channel** (single source of truth — every other step refers back to this value): `#anthropicforce-ae-earlyaccess-feedback`

**Privacy note:** This is a **private Slack channel** — feedback is only visible to channel members, not the wider organization.
 
Feedback is posted as a formatted message to this Slack channel using the Slack MCP connector (`slack_send_message`). This works in Claude Desktop and web, where the Slack connector is available.
 
Throughout this skill, "the feedback channel" means the channel defined here. To point feedback somewhere else, change only this value (see also the `[CUSTOMIZE]` section).
 
**How to resolve the channel:**
- Use `slack_search_channels` with the channel name defined above (without the leading `#`) to find the channel ID (`C…`).
- Post to that channel ID via `slack_send_message`.
- If the channel cannot be found, see the "Channel not found" edge case below.
## Step 2 - Capture skill execution context

Scan the conversation to capture details about each skill used in this session.

**For each skill invocation, capture:**

### skill_name
The short name without the plugin prefix (e.g., "pipeline-review" not "headless-360-for-sales:pipeline-review")

### user_utterance
The exact user message that triggered this skill invocation.

**How to determine:**
- Find the user message immediately before the `Skill()` tool call
- Capture the full text verbatim
- This shows what the user was trying to accomplish

**⚠️ PII Warning:**
- User utterances may contain PII: email addresses, phone numbers, SSNs, credentials
- Customer/account names are acceptable
- If an utterance contains obvious PII (email addresses, phone numbers), redact it: 
  - `"send email to john.doe@example.com"` → `"send email to [EMAIL]"`
  - `"call 555-123-4567"` → `"call [PHONE]"`
- Keep the semantic meaning intact for context

### outcome_summary
What the skill delivered (1-2 sentences)

**How to determine:**
- Look at the skill's output/result
- Summarize what was actually produced
- Examples:
  - "Stage-by-stage pipeline with 5 at-risk deals flagged"
  - "Meeting brief with account history and 8 discovery questions"
  - "2 quiet deals and 3 slipping close dates identified"

### execution_status
Whether the skill completed successfully. One of: `success`, `partial`, `failed`, `aborted`.

**How to determine:**
- `success` — delivered what was asked for, no meaningful errors
- `partial` — delivered something useful but incomplete (missing data, some records skipped)
- `failed` — could not deliver core outcome (errors, no data, routing problem)
- `aborted` — user stopped it or it exited early

### notable_issues
Any errors, missing data, or friction during execution (optional).

**How to determine:**
- List concrete problems: "Gmail not connected", "had to ask which account", "SOQL timeout"
- Leave empty if execution was clean
- Keep as short phrases

**Build a de-duplicated skills list:**
- Extract unique skill names from all captured skill invocations
- Sort alphabetically for consistency
- This becomes the "Skills used" list shown to the user

**Example captured context:**
```
[
  {
    skill_name: "pipeline-review",
    user_utterance: "show me my pipeline",
    outcome_summary: "Stage-by-stage pipeline with 38 opportunities, 5 at-risk deals flagged",
    execution_status: "success",
    notable_issues: []
  },
  {
    skill_name: "deal-signals",
    user_utterance: "what signals do you see for the Acme deal?",
    outcome_summary: "3 positive signals, 2 risk factors identified",
    execution_status: "partial",
    notable_issues: ["Had to ask user to clarify which Acme account"]
  }
]
```

**Handle sessions with no skills but MCP usage:**

If no skills were invoked, check whether the Headless 360 MCP server was used directly:
- Look for `dispatch`, `discover`, or `describe` tool calls in the conversation
- If found: continue with feedback flow, but mark as "MCP-only session" (no skills invoked)
- If not found: this session didn't use Headless at all

If neither skills nor MCP were used, inform the user:
```
No Headless 360 usage detected in this session. Feedback is for sessions using skills or the MCP server.
```

And exit without posting.

**For MCP-only sessions:**
- Set skills list to empty: `[]`
- Add a flag: `mcp_only_session: true`
- This will be rendered differently in the Slack message (Step 5)
 
## Step 3 - Ask for free-form feedback
 
**Present a natural, open-ended prompt that shows the skills used as context.**

**For sessions with skills:**
 
```
💭 Feedback on this session ([comma-separated skills from Step 2]):

How'd it go? Share any thoughts on what worked, what didn't, or specific issues with any of these skills.

(or say "skip" to pass)
```

**For MCP-only sessions (no skills invoked):**

```
💭 Feedback on this session (used Headless 360 MCP, no skills invoked):

How'd it go? Share any thoughts on your experience using the MCP directly.

(or say "skip" to pass)
```

**User response handling:**
- If user provides text (short or detailed), capture it as the raw feedback
- If user says "skip" / "no" / "none" / "pass" (or sends an empty response), exit without posting
- If user says "not now" or "later", exit without posting

**Keep this lightweight** - encourage natural language, any length from one word to a paragraph.
 
## Step 4 - Process the feedback
 
Use Claude to synthesize structured insights by combining:
1. The raw user feedback from Step 3
2. The captured skill execution context from Step 2

This processing step happens inline before posting to Slack.

**Extract the following:**

### sentiment
Overall tone of the user feedback. One of: `positive`, `neutral`, `negative`, `mixed`.

**How to determine:**
- `positive` — enthusiastic, satisfied, no complaints
- `negative` — frustrated, dissatisfied, multiple issues
- `mixed` — some good, some bad
- `neutral` — factual, no strong opinion either way

### skills_mentioned
Which specific skills were explicitly mentioned in the user feedback.

**How to determine:**
- Match skill names from Step 2 against the feedback text
- Return as a list of skill names
- Empty list if no specific skills mentioned

### issues
Specific problems or failures — **combine from both user feedback AND captured context**.

**How to determine:**
- Start with `notable_issues` from Step 2 captured context
- Add any additional issues mentioned in user feedback
- Deduplicate if the user mentions the same issue Claude already captured
- Keep as short phrases (5-10 words each)
- Tag source when useful: "(user)" vs "(observed)"
- Examples:
  - "Had to ask user to clarify account (observed)"
  - "Stale staging data (user)"
  - "SOQL timeout on opportunity query (observed)"

### what_worked
Positive aspects or successes — **combine from both user feedback AND captured context**.

**How to determine:**
- Look at skills with `execution_status: success` from Step 2 — these implicitly worked
- Add what the user explicitly said worked well
- Keep as short phrases (5-10 words each)
- Examples:
  - "Fast execution in pipeline-review (user)"
  - "Found at-risk deals accurately (user)"
  - "All skills completed successfully (observed)"

### suggested_improvements
Any explicit suggestions for improvement from user feedback.

**How to determine:**
- Extract actionable improvement ideas from user feedback only
- Keep as short phrases (5-10 words each)
- Empty list if no suggestions

### execution_summary
High-level summary of what happened across all skills — **generated from Step 2 context**.

**How to determine:**
- Count of skills executed
- Overall success rate (how many succeeded vs partial/failed)
- One sentence summary
- Example: "3 skills executed: 2 successful, 1 partial (disambiguation needed)"

**Processing approach:**
- The goal is to **enrich** user feedback with observed context, not replace it
- User feedback is the primary signal; captured context adds detail
- If user feedback conflicts with observed context (e.g., user says "fast" but execution took 2+ minutes), include both perspectives
- Do NOT infer beyond what the user said or what was actually observed

## Step 5 - Post the feedback message to Slack
 
Post a single formatted message to the feedback channel (from Step 1) using the Slack MCP tool `slack_send_message`. Do NOT use a webhook, `curl`, or WebFetch — feedback now lives as a channel post.
 
### 5a - Resolve the channel ID
 
Call `slack_search_channels` with the feedback channel name from Step 1 and take the matching channel's ID (`C…`). Reuse this ID for the post.
 
### 5b - Build the message
 
The message includes:
1. Header with sentiment emoji
2. Date and skills used
3. Execution summary (from Step 2 captured context)
4. Raw feedback (user's exact words, quoted)
5. Skill-by-skill context (from Step 2)
6. Processed insights (from Step 4)

**Sentiment emoji mapping:**
- `positive` → ✅
- `negative` → ❌
- `mixed` → ⚠️
- `neutral` → ℹ️

**Formatting rules for clean UX:**
- Lead with a header line so posts are scannable in the channel feed
- Use Slack markdown (`*text*` is bold, `>` for blockquote)
- Quote the raw feedback with `>` so it's visually distinct
- Show captured context per skill in a collapsible format
- Only show processed fields that have content (omit empty lists)
- Keep it readable — use sections to organize

**Template (for sessions with skills):**
 
```
:memo: *Session Feedback*  [sentimentEmoji]
 
• *Date:* [YYYY-MM-DD]
• *Skills used:* [comma-separated skills from Step 2]
• *Execution summary:* [from Step 4]

*Raw feedback:*
> [user's exact words, multi-line preserved with > prefix per line]

*Skill execution details:*
[For each skill from Step 2:]
• *[skill_name]*: [execution_status emoji] [execution_status]
  - User asked: "[user_utterance]"
  - Outcome: [outcome_summary]
  - Issues: [notable_issues, or "none"]              ← omit if empty

*Processed insights:*
• *Sentiment:* [sentiment]
• *Skills mentioned:* [comma-separated, or "none"]     ← omit if empty
• *Issues:* [bullet list with source tags]            ← omit if empty
• *What worked:* [bullet list with source tags]       ← omit if empty
• *Suggested improvements:* [bullet list]              ← omit if empty
```

**Template (for MCP-only sessions):**

```
:memo: *Session Feedback*  [sentimentEmoji]
 
• *Date:* [YYYY-MM-DD]
• *Skills used:* None
• *MCP usage:* Headless 360 MCP server used directly (no skills invoked)

*Raw feedback:*
> [user's exact words, multi-line preserved with > prefix per line]

*Processed insights:*
• *Sentiment:* [sentiment]
• *Issues:* [bullet list with source tags]            ← omit if empty
• *What worked:* [bullet list with source tags]       ← omit if empty
• *Suggested improvements:* [bullet list]              ← omit if empty

*Note:* User interacted with Headless 360 MCP but no skills were invoked. This may indicate:
- Skills were not discovered or suggested by Claude
- User task didn't match existing skill coverage
- User preferred direct MCP access
```

**Execution status emoji mapping:**
- `success` → ✅
- `partial` → ⚠️
- `failed` → ❌
- `aborted` → ⏹️
 
**Example rendered message (detailed feedback):**
 
```
:memo: *Session Feedback*  ⚠️
 
• *Date:* 2026-07-14
• *Skills used:* call-prep, deal-signals, pipeline-review
• *Execution summary:* 3 skills executed: 2 successful, 1 partial (disambiguation needed)

*Raw feedback:*
> pipeline-review was fast and found the at-risk deals I needed. deal-signals had stale staging data and kept asking me to clarify which account. Would be great if it could infer from context.

*Skill execution details:*
• *call-prep*: ✅ success
  - User asked: "prep me for the Acme call tomorrow"
  - Outcome: Meeting brief with account history and 8 discovery questions

• *deal-signals*: ⚠️ partial
  - User asked: "what signals do you see for the Acme deal?"
  - Outcome: 3 positive signals, 2 risk factors identified
  - Issues: Had to ask user to clarify which Acme account

• *pipeline-review*: ✅ success
  - User asked: "show me my pipeline"
  - Outcome: Stage-by-stage pipeline with 38 opportunities, 5 at-risk deals flagged

*Processed insights:*
• *Sentiment:* mixed
• *Skills mentioned:* pipeline-review, deal-signals
• *Issues:*
  - Had to ask user to clarify account (observed)
  - Stale staging data (user)
• *What worked:*
  - Fast execution in pipeline-review (user)
  - Found at-risk deals accurately (user)
  - call-prep delivered comprehensive brief (observed)
• *Suggested improvements:*
  - Infer account from context
```

**Example rendered message (short feedback):**
 
```
:memo: *Session Feedback*  ✅
 
• *Date:* 2026-07-14
• *Skills used:* call-prep, pipeline-review
• *Execution summary:* 2 skills executed: 2 successful

*Raw feedback:*
> Great! Fast and accurate.

*Skill execution details:*
• *call-prep*: ✅ success
  - User asked: "prep me for the Acme call tomorrow"
  - Outcome: Meeting brief with account history and 8 discovery questions

• *pipeline-review*: ✅ success
  - User asked: "show me my pipeline"
  - Outcome: Stage-by-stage pipeline with 38 opportunities, 5 at-risk deals flagged

*Processed insights:*
• *Sentiment:* positive
• *What worked:*
  - Fast execution (user)
  - Accurate results (user)
  - All skills completed successfully (observed)
```

**Example rendered message (MCP-only session):**
 
```
:memo: *Session Feedback*  ⚠️
 
• *Date:* 2026-07-14
• *Skills used:* None
• *MCP usage:* Headless 360 MCP server used directly (no skills invoked)

*Raw feedback:*
> I asked for pipeline health but had to use dispatch directly. Felt clunky compared to what I expected.

*Processed insights:*
• *Sentiment:* negative
• *Issues:*
  - Skills not suggested by Claude (observed)
  - Manual dispatch felt clunky (user)
• *Suggested improvements:*
  - Better skill discovery
  - More intuitive MCP interface

*Note:* User interacted with Headless 360 MCP but no skills were invoked. This may indicate:
- Skills were not discovered or suggested by Claude
- User task didn't match existing skill coverage
- User preferred direct MCP access
```
 
### 5c - Send it
 
```
slack_send_message(
  channel_id: "[C… from 5a]",
  message: "[formatted message from 5b]"
)
```
 
Treat a non-success response (channel not found, no write access, or any error) as a failure — see Step 6.
 
## Step 6 - Confirm submission
 
After the message posts successfully to the feedback channel, confirm with (substitute the actual channel name from Step 1):
 
```
✓ Feedback logged to #anthropicforce-ae-earlyaccess-feedback
```
 
If the Slack post fails (channel not found, no write access, or any error):
 
```
⚠️ Could not post feedback to #anthropicforce-ae-earlyaccess-feedback. Your feedback was:

Skills: [comma-separated skills]
Raw feedback: [user's words]

You can post this manually to the channel.
```
 
**Do NOT show verbose output.** Keep it minimal - one line confirmation or error.
 
## Edge Cases
 
### No Headless 360 usage detected
 
If neither skills nor MCP server were used in this session:
 
```
No Headless 360 usage detected in this session. Feedback is for sessions using skills or the MCP server.
```
 
Exit without posting.
 
### Channel not found
 
If `slack_search_channels` returns no match for the feedback channel from Step 1 (or the Slack connector isn't connected):
 
```
⚠️ Couldn't find #anthropicforce-ae-earlyaccess-feedback (is the Slack connector connected?). Your feedback was:

Skills: [comma-separated skills]
Raw feedback: [user's words]
```
 
Do not attempt to post.
 
### User declines feedback
 
If user says "skip" / "no" / "pass" / "not now" / "later":
 
```
Skipping feedback for now.
```
 
Do not post to Slack.
 
## Invocation
 
This skill is invoked manually by the user:
 
```
/feedback
```
 
## Output
 
**Successful execution (detailed feedback):**
 
```
💭 Feedback on this session (call-prep, deal-signals, pipeline-review):

How'd it go? Share any thoughts on what worked, what didn't, or specific issues with any of these skills.

(or say "skip" to pass)

> pipeline-review was fast and found the at-risk deals I needed. deal-signals had stale staging data and kept asking me to clarify which account. Would be great if it could infer from context.
 
✓ Feedback logged to #anthropicforce-ae-earlyaccess-feedback
```
 
**Successful execution (short feedback):**
 
```
💭 Feedback on this session (call-prep, pipeline-review):

How'd it go? Share any thoughts on what worked, what didn't, or specific issues with any of these skills.

(or say "skip" to pass)

> Great! Fast and accurate.
 
✓ Feedback logged to #anthropicforce-ae-earlyaccess-feedback
```
 
**Declined feedback:**
 
```
💭 Feedback on this session (pipeline-review):

How'd it go? Share any thoughts on what worked, what didn't, or specific issues with any of these skills.

(or say "skip" to pass)

> skip

Skipping feedback for now.
```
 
**Error case:**
 
```
💭 Feedback on this session (pipeline-review):

How'd it go? Share any thoughts on what worked, what didn't, or specific issues with any of these skills.

(or say "skip" to pass)

> The staging data seemed stale
 
⚠️ Could not post feedback to #anthropicforce-ae-earlyaccess-feedback. Your feedback was:
[details for manual entry]
```
 
## Privacy & Data Handling
 
- Raw feedback is captured verbatim - user is responsible for content
- **User utterances may contain PII** - redact obvious PII (emails, phone numbers) when capturing them in Step 2
- Do NOT include PII, credentials, or sensitive customer data in processed insights
- Customer/account names are acceptable; SSN, credit cards, auth tokens, email addresses, phone numbers are not
- All data is posted to the feedback Slack channel from Step 1 (visible to channel members, but still a private channel)
- When in doubt about whether something is PII: redact it or omit it from the feedback

## [CUSTOMIZE]
 
- **Target channel:** change the channel value in Step 1 (the single source of truth) if feedback should go elsewhere
- **Message format:** adjust the message template in Step 5b to change layout, labels, or emoji
- **Prompt text:** customize the feedback prompt in Step 3
- **Processing fields:** adjust what insights are extracted in Step 4
