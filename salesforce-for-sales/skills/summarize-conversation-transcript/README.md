# Summarize Conversation Transcript

Retrieve and summarize a Salesforce VoiceCall or VideoCall transcript.

## What it does

1. Finds the VoiceCall or VideoCall record (by ID, account, contact, or search criteria)
2. Retrieves the conversation transcript via Salesforce Actions API
3. Analyzes and summarizes:
   - **Customer Impression** (2-3 sentences on sentiment)
   - **Call Summary** (key highlights, decisions, takeaways)
   - **Next Steps** (actionable items with owners and dates)
4. Enriches with related opportunity context
5. Suggests follow-up actions (log activity, update opportunity, draft email)

## When to use

- "Summarize my call with [account]"
- "Get the transcript for [call]"
- "What happened on that call?"
- "Summarize the [contact] call"

**Note:** This skill is for Salesforce-recorded VoiceCall/VideoCall records with transcripts. For Google Meet transcripts or Drive docs, use `call-follow-up` instead.

## Inputs

- Call identifier (VoiceCall/VideoCall ID, account name, contact name, or date/time context)

## Outputs

- Customer impression summary
- Call summary (250 words)
- Numbered next steps with owners/dates
- Related opportunity links
- Suggested follow-up actions

## API Usage

Uses the Salesforce Actions API:
- `POST /services/data/v64.0/actions/standard/getConversationTranscript`

Queries:
- `VoiceCall` and `VideoCall` objects to find records
- `Opportunity` to enrich context

## Edge Cases

- **No transcript available:** Reports gracefully with call details
- **Multiple calls match:** Lists all and asks for disambiguation
- **Minimal transcript:** Detects and reports "no substantial conversation"
- **Call not found:** Offers alternative search methods

## Customization

See `[CUSTOMIZE]` section in SKILL.md:
- Summary length (default: 250 words)
- Additional extraction fields (competitive mentions, feature requests)
- Auto-logging behavior
