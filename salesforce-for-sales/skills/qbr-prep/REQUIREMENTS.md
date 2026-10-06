# Feature requirements: QBR Prep skill

## Problem

Account executives and customer success partners routinely prepare Quarterly Business Reviews (QBRs), but the plugin today has call prep, renewal radar, and pipeline tools — not an account-level QBR assembly workflow. Sellers stitch opportunities, cases, stakeholders, and wins by hand.

## Goal

Add a read-only Cowork skill `/salesforce-for-sales:qbr-prep` that produces a grounded QBR brief for a named Account.

## User stories

1. As an AE, I can ask “Prep a QBR for Cobalt” and get last-quarter wins, open pipeline, stakeholders, risks, and a timed agenda.
2. As a sales leader, I can review the brief before joining a customer QBR and see evidence-linked health (not invented CSAT).
3. As a user on a read-only Salesforce connection, I still get the full analysis; CRM updates are suggested as text only.

## Functional requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Accept an account name (or opportunity that resolves to an account). | Must |
| FR-2 | Default review window = last 90 days; allow user override. | Must |
| FR-3 | Query Account, Opportunities, Contacts; Cases when available. | Must |
| FR-4 | Ground Account/Opportunity/Case field metadata before custom fields. | Must |
| FR-5 | Output health snapshot, value delivered, open pipeline, support/risk, stakeholders, agenda, three asks. | Must |
| FR-6 | Prefer `display_widget` output; provide markdown fallback. | Must |
| FR-7 | Never write to Salesforce from this skill. | Must |
| FR-8 | Continue when Slack/email/docs connectors are absent. | Must |
| FR-9 | Cite Lightning record URLs for every Salesforce entity discussed. | Must |
| FR-10 | Label expansion/whitespace ideas as hypotheses when not backed by product data. | Should |

## Non-functional requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | Follow the shared global-rules bootstrap (silent tool execution, no false disconnects). |
| NFR-2 | Batch independent Salesforce reads in one turn where possible. |
| NFR-3 | Do not call undocumented REST paths or `discover`/`describe`. |
| NFR-4 | Keep user-facing labels human-readable (field labels, not API names). |

## Out of scope

- Sending customer email or Slack without draft + approval (use draft-outreach / call-follow-up patterns).
- Automatic Opportunity/Account field updates (defer to `update` skill).
- Multi-account portfolio QBRs in v1 (single account only).

## Acceptance criteria

- [ ] Skill folder `salesforce-for-sales/skills/qbr-prep/` contains `SKILL.md` and this `REQUIREMENTS.md`.
- [ ] Skill is discoverable via description keywords: QBR, EBR, quarterly business review, account review.
- [ ] Plugin README lists the skill for end users.
- [ ] Root marketplace README mentions QBR prep in the salesforce-for-sales summary.
- [ ] Behavior matches design principles: read-only, draft-before-send, grounded in records, graceful degradation.

## Invocation examples

```
/salesforce-for-sales:qbr-prep Cobalt Systems
Prep a QBR for account Acme for FY26 Q2
Build an executive business review pack for the Globex account
```
