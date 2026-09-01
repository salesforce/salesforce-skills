---
name: configure
description: One-time onboarding for the Headless 360 sales plugin. Verifies Salesforce is connected, reads who you are and what you sell, then renders a reviewable Profile card (your first-class, durable user-profile memory), a live Command Center, and a searchable Memories store — all as durable Claude Artifacts — and sets up a daily schedule to keep the profile fresh. Use when the user says "configure", "configure salesforce", "set me up", "onboard me", "get me started", or on first run of the plugin. IMPORTANT: Exit gracefully if Salesforce is not connected - do not spiral attempting unavailable operations.
model: claude-sonnet-4-6
effort: medium
# Explicit-invocation only: the user runs this deliberately (/configure or by name).
# Claude must not auto-trigger onboarding from ambient conversation.
disable-model-invocation: true
---
<!-- global-rules-bootstrap -->
# Global Rules

- **Execute silently between tool calls.** Do not output planning, progress, transition, waiting, or tool-result narration between calls. Execute tool calls silently and proceed directly to the next call. Parallelize independent tasks by batching tool calls into one turn whenever possible. Before the final output, speak only when the skill explicitly requires user input, approval, an exact notice, or material error/blocked reporting. Do not invent checkpoints.
- **Keep the final output concise.** Return only the requested result or deliverable. Omit process recaps, tool-call details, redundant preambles or conclusions, and data already shown in a widget.
- **Ground dynamic or custom relationship and field names before relying on them.** Fixed standard fields that this skill explicitly marks as requiring no grounding need no extra grounding call. On a name error, use the skill's documented grounding path when present; otherwise report the error instead of guessing or re-firing the same shape.
- **Cite every value exactly as queried**; never fabricate; distinguish a blank value from a value that was not queried. Link each Salesforce record inline: `https://[instanceUrl]/lightning/r/[SObjectType]/[Id]/view`.
- **Show human labels, never API/field literals.** In anything the user sees, print each field's grounded `label` (for example, "Deal Risk", not `Deal_Risk__c`) and record Names, never raw Ids or `__c` API names.
- **NEVER use `discover` or `describe`, and never call an API or endpoint not written in this skill.** Every Salesforce URL you need is in the skill. Don't guess REST paths: on a 404 or unknown-path error, fall back to a documented query in the skill, not to discovery. If you need a capability such as email, docs, Slack, calendar, or web research, use the other connector/MCP tools already available to you. Endpoint guessing and discovery add needless round-trips. Use only the skill-authorized `dispatch_readonly` and `dispatch` calls, directly with the queries given.

# Rules:

- **Empty `MINE` scope is not a failure.** A brand-new user legitimately has no activity — record "none yet", never invent records.
- **Memory lives in artifacts, not files or an MCP.** Durable memory is stored as Claude Artifacts, because in Claude Desktop the shell/tool sandbox home is ephemeral — files you write (and any disk-backed MCP) do not survive between sessions, but artifacts do. Two artifacts hold it: (1) the **`salesforce-user-profile` artifact is the first-class user profile** — the whole profile is inlined in it and it is re-derived from Salesforce on every run, so it is never read back; (2) the **`salesforce-memories` artifact is the general store** of many smaller memories (frontmatter + body records). **Do not write memory files to disk and do not call any `salesforce-memory` MCP tool** — neither persists in Desktop.
- **The memories store is searched via its artifact `description`, not by reading the artifact.** No tool reads an artifact's HTML back, but the artifact's `description` persists to the workspace's `artifacts.json` (which a later session can grep). So the `salesforce-memories` artifact's `description` MUST carry a compact frontmatter INDEX — `mem:<name>[<type>;<tag>,<tag>] <one-line summary>` per memory, joined by `; ` — so a future session finds relevant memories and pulls only those. The full records (including bodies) live inlined in the artifact for the human and any future read path; the index is the agent's cross-session read surface, so write each memory's `summary` to stand alone.
- **Artifacts can only call MCP tools you declare in their `mcp_tools`, and the host blocks any tool you did not actually call this session.** So (1) resolve the EXACT fully-qualified tool name in-session before creating an artifact — do not guess or list candidate variants; (2) declare only tools you verified this session in `mcp_tools`; (3) never make an artifact depend on a server that may not be connected. The Command Center calls exactly one tool (the read-only dispatch tool); the Profile, Plugin Info, and Memories artifacts call none (their data is inlined).

# Configure Salesforce

Gate on Salesforce → gather identity + role + book-of-business → author the dataset once → one shell command builds the four artifact files (Profile, Command Center, Plugin Info, Memories) → create all four artifacts in one message → create the daily refresh schedule → render the "four places I'll be most useful" launcher.

**Load every tool you'll need in ONE ToolSearch first.** If any tools are deferred in this session, resolve them up front in a single `select:` query rather than discovering them one step at a time (four separate mid-run ToolSearch round-trips was a measured slowdown). You will need, across the whole flow: the Salesforce dispatch tool (`dispatch_readonly`), `create_artifact`, the scheduling tool (step 5), and — if present — Slack read tools. Load them once, then proceed. Skip any that aren't offered in this session.

## 0. Salesforce connected? (hard gate)

Probe the running user:
```
dispatch_readonly(method: "GET", url: "/services/data/v66.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { currentUser { Id Name { value } } } }\"}" })
```
If `dispatch_readonly`/`salesforce-h360` is absent, or the probe errors, exit gracefully, exactly:

```
I can't reach Salesforce yet. Please connect the Headless 360 server (`salesforce-h360`) via /mcp, then re-run configure.
```

Do NOT attempt workarounds, ask clarifying questions, or invent a profile. Just stop.

**Record the exact tool name.** The tool you just called successfully has a fully-qualified name — `mcp__<server>__dispatch_readonly` (typically `mcp__salesforce-h360__dispatch_readonly`; in local dev it may be `mcp__salesforce-h360-dev__dispatch_readonly`). Note that exact string as `<DISPATCH_TOOL>`; the Command Center artifact (step 4) needs it verbatim, both inlined in its script and as its sole `mcp_tools` entry.

## 1. Gather (issue ALL reads in ONE parallel batch)

Keep `currentUser.Id` from step 0 as `<UID>`. Reads **1a–1e, 1h, and 1j are independent** — issue them as a **single batch of parallel `dispatch_readonly` calls in one turn**, don't await each before sending the next. Round-tripping them one at a time was a top slowdown. (1f/1g are optional Slack/mail passes; fire them in the same batch when those MCPs are connected. 1i needs no query.)

**1a. Identity** — already have Id/Name/Email/TimeZone if you widened step 0; else:
```
dispatch_readonly(method: "GET", url: "/services/data/v66.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { currentUser { Id Name { value } Email { value } TimeZoneSidKey { value } } } }\"}" })
```

**1b. Role / title / manager / profile** — not served by UI-API GraphQL; SOQL:
```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT Id, Name, Title, Department, ManagerId, Manager.Name, UserRole.Name, Profile.Name FROM User WHERE Id = '<UID>'" })
```
`UserRole.Name` is edition-gated — the role hierarchy is absent in some editions (Group/Essentials/Contact Manager), where this query throws `INVALID_FIELD` on that column. If it does, **drop `UserRole.Name` and re-run** the same query with the rest of the fields (all of which are guaranteed standard) — record role as "not set" rather than failing the step.

**1c. Permission sets** (what they're licensed to do) — SOQL:
```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT PermissionSet.Label, PermissionSet.Name FROM PermissionSetAssignment WHERE AssigneeId = '<UID>'" })
```

**1d. What they work on** (dominant objects) — SOQL:
```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT Id, Name, Type, LastReferencedDate FROM RecentlyViewed WHERE LastReferencedDate != null ORDER BY LastReferencedDate DESC LIMIT 100" })
```
Group by `Type` → the objects they touch most (Opportunity, Account, Lead, …).

**1e. Recent activity** (cadence signal) — GraphQL, `scope: MINE`:
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Task(scope: MINE, where: { ActivityDate: { gte: { literal: LAST_90_DAYS } } }, first: 100, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Id Subject { value } Status { value displayValue } ActivityDate { value } } } } } } }\"}" })
```
```
dispatch_readonly(method: "GET", url: "/services/data/v65.0/graphql",
  queryParams: { "queryInput": "{\"query\":\"query { uiapi { query { Event(scope: MINE, where: { ActivityDate: { gte: { literal: LAST_90_DAYS } } }, first: 100, orderBy: { ActivityDate: { order: DESC } }) { edges { node { Id Subject { value } ActivityDate { value } } } } } } }\"}" })
```

**1f. Slack signal (optional).** Salesforce alone can't see how someone actually works — pull it from Slack when that MCP is connected. Do a light, read-only pass and **skip silently** if the tools aren't present:
- `slack_search_users` / `slack_read_user_profile` on their name → team, title-as-written, handle, timezone (cross-checks the CRM title, and often names the team CRM can't).
- `slack_search_channels` / a light `slack_search_public_and_private` on their name and top accounts → which deal/team channels they live in and roughly how often they post (a real cadence signal). Names of accounts or deals they discuss are a strong "what they sell / who they sell with" signal.
Feed this into the profile's **How you work** section and, where it's a headline, a highlight card. Attribute every Slack-derived field `source: "Slack"`. Never quote message contents in the profile — use it only to infer team, cadence, and focus.

**1g. Email + calendar signal (optional).** If a mail/calendar connection is available (a Gmail / Google Workspace MCP, or the host's own email & calendar tools), read *metadata only* — never body contents — to model how they sell:
- Calendar: meeting volume and mix over the last ~30 days (internal vs. external, recurring 1:1s vs. customer calls) → a meeting-cadence and selling-motion signal for **How you work**.
- Email: top external domains/contacts they correspond with → corroborates their book of business and ICP.
Attribute calendar-derived fields `source: "Calendar"` and email-derived fields `source: "Gmail"`. **Skip silently** if no such connection is present, and record the gap in the profile's "What I can't see today" (see step 3) so the absence is honest rather than invisible.

**1h. Sales performance + ICP signal** — the Profile mock surfaces win rate, deal size/velocity, and an inferred ICP. Derive these from closed-won history (SOQL):
```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT Id, Amount, StageName, IsWon, CloseDate, CreatedDate, Account.Industry, Account.NumberOfEmployees FROM Opportunity WHERE OwnerId = '<UID>' AND IsClosed = true AND CloseDate = LAST_N_DAYS:365 ORDER BY CloseDate DESC LIMIT 200" })
```
From the result compute: **win rate** (`IsWon` count ÷ decided count), **avg / largest deal size** (won `Amount`), **median velocity** (`CloseDate − CreatedDate`, days), and the **dominant industry + employee-size band** among won deals → the ICP. Label every derived value **"Inferred"** in the profile (it's a best-guess from history, not a fact). If the user has no closed deals yet, record "none yet" — never invent figures.

**1i. Quota (only if you can source it).** There is no reliable standard SOQL field for a rep's quota. If the user states it, use it; otherwise leave quota `null` — the Command Center's Attainment donut degrades to a closed-won summary, and the Profile's quota field reads "not set". Do **not** query `ForecastingQuota` speculatively or fabricate a number.

**1j. Open pipeline** — the Profile's "pipeline right now" section (# open, open value, closing this quarter). Include this in the step-1 batch; don't leave it to improvise later (issuing it after the batch was a measured slowdown). SOQL:
```
dispatch_readonly(method: "GET", url: "/services/data/v63.0/query",
  queryParams: { "q": "SELECT Id, Name, Amount, StageName, CloseDate FROM Opportunity WHERE OwnerId = '<UID>' AND IsClosed = false ORDER BY CloseDate ASC LIMIT 200" })
```
Compute # open, total open value, and the subset closing this quarter. (The Command Center artifact re-derives all of this client-side at render — this read is only to populate the Profile's inlined `PROFILE` object.)

## 2. Author the profile data ONCE

Everything downstream — the Profile card, the Command Center, the Memories store — is built from one dataset. Type it out **once, here**, then step 3 turns it into all four files in a single shell command. Do not restate these facts again in an `IDENTITY` literal or the schedule prompt — the build command derives those.

Author exactly these from your step-1 reads:
- **`PROFILE`** — the object the Profile card renders (shape below). The Profile artifact **is** the first-class, durable user-profile memory; it is re-derived from Salesforce every run, never read back.
- **`PROFILE_DESC`** — one line (who they are + what they sell). Used as the `salesforce-user-profile` artifact's description.
- **`MEMORIES`** — an array of records for the general **Memories store** (the `salesforce-memories` artifact) — durable facts worth keeping *separately from the profile*: working preferences the user stated (autonomy, notification style, opt-outs), standout accounts/renewals to watch, cadence quirks, anything the user asks you to remember. Each record: `{ "name": kebab-id, "type": "pref|person|account|ops|note|…", "tags": [lowercase…], "summary": "one rich standalone line", "body": "optional markdown detail" }`. **Omit `updated` — step 3 stamps it.** Seed only what's genuinely durable and separable from the profile; an **empty array is fine** on a first run — never invent memories. (The `summary` is the agent's cross-session read surface — see the Rules — so make each one stand alone.)

The PROFILE object shape (omit anything you don't have):
  - `name` (first name), `role`, optional `subtitle`, `sources` (array of the connected sources you actually read, e.g. `["Salesforce","Slack","Gmail","Calendar"]` — list only the ones you truly reached this session).
  - `highlights` — up to **3** cards for "The short version", each `{ title, value, body, sources[] }` (e.g. *How you sell* → "Relationship-led, technical sale"). Synthesize these from the data; skip if you have nothing substantive.
  - `sections` — the Detailed Profile. Each `{ title, kind, intro, fields[{label, value, source}] }`. The Profile renders a **sticky jump-nav** whose five links map to these sections by title/kind — **Summary** (the highlights above), **Who you are**, **Salesforce context**, **Working preferences**, **What I can't see** — so keep those section titles and kinds intact for the nav to resolve. Use these sections where you have data:
    - **Who you are** (`kind: "confirm"`) — role, segment/territory, manager, tenure.
    - **Your ICP** (`kind: "review"`) — industries, company-size band, avg/largest deal size, deal velocity (all from step 1h, `source: "Inferred"`).
    - **Your pipeline right now** (`kind: "auto"`) — # open, open value, closing this quarter (this is the "Salesforce context" nav target).
    - **Outcomes** (`kind: "thin"`) — win rate, methodology signal.
    - **How you work** (`kind: "system"`) — timezone, activity cadence, and (if you gathered them in 1f/1g) team/channels from Slack and meeting cadence from Calendar.
    - **How you like to work with me** (`kind: "tell"`) — the "Working preferences" nav target. Only what the *user* tells you (you can't infer it): autonomy level (ask first / draft & notify / autonomous), notification style, digest cadence, deal focus, opt-outs. Omit the section entirely if you haven't asked — never invent preferences.

    `kind` ∈ `confirm | review | auto | tell | thin | system | none`. Set each field's `source` to the connection it came from — `source` ∈ `Salesforce | Slack | Gmail | Calendar | Inferred` (or omit) — and the Profile renders that source's inlined brand icon in the pill. Never fabricate a field — omit it.
  - `cantSee` — array of `{ label, value }` naming honest gaps (e.g. Google Drive not connected, no call transcripts, Slack limited to member channels). Only list sources genuinely unavailable this session.

## 3. Build all the files with ONE shell command

`create_artifact` takes an **`html_path`** (a scratch file), not inline HTML — so a single `python3` block substitutes the data you authored in step 2 into the four templates all at once. **Never Read a template into your reply and retype it** (hundreds of lines each) — the only content you type is the small step-2 data. Use Python `.replace`, not `sed` — the JSON contains `/`, `&`, and quotes that break `sed s///`.

The block **self-resolves the template dir** (`$CLAUDE_PLUGIN_ROOT` is often unset in the shell — don't waste a turn running `find`; the fallback globs the installed-plugin locations). It stamps each memory's `updated` timestamp itself (so you never author that) and **prints the `salesforce-memories` description index** — copy that printed line verbatim into the memories artifact's `description` in step 4:

```bash
python3 - <<'PY'
import os, json, glob, pathlib, datetime

# --- resolve the plugin template dir: env var first, then installed-plugin globs ---
def plugin_root():
    home = str(pathlib.Path.home())
    cands = [os.environ.get("CLAUDE_PLUGIN_ROOT")] if os.environ.get("CLAUDE_PLUGIN_ROOT") else []
    cands += glob.glob(home + "/.claude/plugins/marketplaces/*/plugins/headless-360-for-sales")
    cands += glob.glob(home + "/.claude/plugins/repos/*/*/headless-360-for-sales")
    for c in cands:
        if c and pathlib.Path(c, "skills/configure/profile.html").exists():
            return pathlib.Path(c)
    raise SystemExit("templates not found; set CLAUDE_PLUGIN_ROOT")
ROOT = plugin_root()

# --- build-injected: the plugin version this run was generated with. SKILL.md is a
# template, so `1.0.0-pilot.1` is replaced at plugin build time with the shipped
# version — leave this line EXACTLY as rendered; do not edit, retype, or author it.
# It is stamped into all three artifacts (and the step-5 schedule) so a later plugin
# update can detect what version built them and refresh anything stale. ---
PLUGIN_VERSION = "1.0.0-pilot.1"

# --- the ONLY things you type out (from step 2 / step 0) ---
PROFILE = {   # the Profile card object (shape in step 2)
  # "name": ..., "role": ..., "sources": [...], "highlights": [...], "sections": [...], "cantSee": [...]
}
DISPATCH_TOOL = "mcp__salesforce-h360__dispatch_readonly"   # EXACT name verified in step 0
OWNER_ID      = "<UID>"                                     # running user's Id
QUOTA, FY_START_MONTH = None, 1                             # QUOTA only if sourced in 1i; else None
PROFILE_DESC = "<one line: who they are + what they sell>"  # salesforce-user-profile description
MEMORIES = [  # general Memories store (step 2). [] is fine on a first run. Omit "updated" — stamped below.
  # {"name": "acme-net60", "type": "pref", "tags": ["acme","pricing"],
  #  "summary": "Acme insists on net-60 terms", "body": "..."},
]

ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

# --- profile artifact (data inlined; no MCP calls). This IS the first-class user-profile memory. ---
p = pathlib.Path(ROOT, "skills/configure/profile.html").read_text()
p = p.replace("var PROFILE = {};", "var PROFILE = " + json.dumps(PROFILE) + ";")
p = p.replace("__PLUGIN_VERSION__", PLUGIN_VERSION)
assert "var PROFILE = {};" not in p and "__PLUGIN_VERSION__" not in p, "a profile placeholder was not replaced"
pathlib.Path("profile.artifact.html").write_text(p)

# --- command center artifact (IDENTITY is DERIVED from PROFILE — don't retype name/role) ---
IDENTITY = {"userName": PROFILE.get("name"), "role": PROFILE.get("role"), "quota": QUOTA, "fyStartMonth": FY_START_MONTH}
c = pathlib.Path(ROOT, "skills/configure/command-center.html").read_text()
c = (c.replace('var DISPATCH_TOOL = "__DISPATCH_TOOL__";', 'var DISPATCH_TOOL = ' + json.dumps(DISPATCH_TOOL) + ';')
      .replace('var OWNER_ID = "__OWNER_ID__";',           'var OWNER_ID = ' + json.dumps(OWNER_ID) + ';')
      .replace('var IDENTITY = __IDENTITY__;',             'var IDENTITY = ' + json.dumps(IDENTITY) + ';')
      .replace('var PLUGIN_VERSION = "__PLUGIN_VERSION__";', 'var PLUGIN_VERSION = ' + json.dumps(PLUGIN_VERSION) + ';'))
assert "__DISPATCH_TOOL__" not in c and "__OWNER_ID__" not in c and "__IDENTITY__" not in c and "__PLUGIN_VERSION__" not in c, "a placeholder was not replaced"
pathlib.Path("command-center.artifact.html").write_text(c)

# --- memories artifact (the general store; data inlined; no MCP calls). Stamp `updated` on
# each record, inline the full records, and build the DESCRIPTION INDEX the agent must copy
# into create_artifact's `description` in step 4 (the only durable, greppable search surface). ---
for m in MEMORIES:
    m.setdefault("updated", ts)
mem_json = json.dumps(MEMORIES)
mm = pathlib.Path(ROOT, "skills/configure/memories.html").read_text()
mm = mm.replace('<script type="application/json" id="h360-memories">[]</script>',
                '<script type="application/json" id="h360-memories">' + mem_json + '</script>')
mm = mm.replace("__PLUGIN_VERSION__", PLUGIN_VERSION)
assert '>[]</script>' not in mm and "__PLUGIN_VERSION__" not in mm, "a memories placeholder was not replaced"
pathlib.Path("memories.artifact.html").write_text(mm)

def _idx(m):
    tags = ",".join(m.get("tags") or [])
    return "mem:" + m.get("name","") + "[" + m.get("type","note") + ";" + tags + "] " + m.get("summary","")
MEMORIES_DESC = ("Salesforce memories (" + str(len(MEMORIES)) + "). " + "; ".join(_idx(m) for m in MEMORIES)) \
                if MEMORIES else "Salesforce memories (0). Empty — no memories saved yet."

# --- plugin-info artifact (data inlined; no MCP calls). This is the DURABLE, human-visible
# record of what the plugin installed: version, managed artifacts, and the daily schedule.
# (The migration baseline itself lives in the step-5 schedule's version line — the one thing
# `update` can read back — not here; this card mirrors that state for a human to see.) ---
PLUGIN_INFO = {
  "name": "Headless 360 for Sales",
  "configuredAt": ts, "updatedAt": ts,
  "artifacts": [
    {"id": "salesforce-user-profile",  "title": "User Profile",   "description": PROFILE_DESC, "version": PLUGIN_VERSION},
    {"id": "salesforce-command-center","title": "Command Center", "description": "Live sales cockpit", "version": PLUGIN_VERSION},
    {"id": "salesforce-memories",      "title": "Memories",       "description": "Durable, searchable memories", "version": PLUGIN_VERSION},
    {"id": "salesforce-plugin-info",   "title": "Plugin Info",    "description": "This card — what the plugin manages", "version": PLUGIN_VERSION},
  ],
  # The daily job (step 5). createdWithVersion is the migration baseline the job carries.
  "schedule": {"identity": "Salesforce Updates", "cadence": "Daily",
               "createdWithVersion": PLUGIN_VERSION, "status": "active"},
}
i = pathlib.Path(ROOT, "skills/configure/plugin-info.html").read_text()
i = i.replace("var PLUGIN_INFO = {};", "var PLUGIN_INFO = " + json.dumps(PLUGIN_INFO) + ";")
i = i.replace("__PLUGIN_VERSION__", PLUGIN_VERSION)
assert "var PLUGIN_INFO = {};" not in i and "__PLUGIN_VERSION__" not in i, "a plugin-info placeholder was not replaced"
pathlib.Path("plugin-info.artifact.html").write_text(i)

print("wrote profile.artifact.html, command-center.artifact.html, memories.artifact.html, plugin-info.artifact.html")
print("MEMORIES_DESC>>> " + MEMORIES_DESC)
PY
```

`IDENTITY.quota` is `null` unless you sourced a quota in 1i (the Attainment donut degrades to a closed-won summary); `fyStartMonth` defaults to `1` if you don't know the org's fiscal year start. On a re-run the files are overwritten with fresh data and a fresh timestamp — that's the intent, don't create a second copy. **Keep the printed `MEMORIES_DESC>>>` line** — it's the memories artifact's description in step 4.

**If your session has no shell** (the command can't run): copy each template into scratch and use the **Edit** tool to replace the placeholders in place — `var PROFILE = {};` for the profile; the four `__…__`/`var …={};`/`var …=__…__;` tokens for the command center; `<script type="application/json" id="h360-memories">[]</script>` (swap `[]` for your JSON array) and `__PLUGIN_VERSION__` for the memories store; `var PLUGIN_INFO = {};` and `__PLUGIN_VERSION__` for the plugin-info card — then build the memories `description` index by hand in the `mem:<name>[<type>;<tag>,…] <summary>` format. Never Read-then-Write a whole template — that re-emits it.

## 4. Create all four artifacts (ONE message)

The files exist from step 3. Issue **all four `create_artifact` calls in a single message** — they're independent, so don't serialize them. Use the exact `id` shown for each below: each template already carries a matching machine-managed `@h360-artifact-id:` HTML comment (its stable identity, so the artifact stays identifiable even if the user renames it in Claude), so the `id` you pass **must equal that stamp** — never invent a different one. For `salesforce-memories`, use the **exact `MEMORIES_DESC` line step 3 printed** as the `description` (that index is the agent's only durable, greppable search surface — don't paraphrase it):

```
create_artifact({ "id": "salesforce-user-profile", "html_path": "profile.artifact.html", "description": "<PROFILE_DESC: who they are + what they sell>" })
create_artifact({ "id": "salesforce-command-center", "html_path": "command-center.artifact.html", "description": "Live sales command center", "mcp_tools": ["<DISPATCH_TOOL>"] })
create_artifact({ "id": "salesforce-memories", "html_path": "memories.artifact.html", "description": "<the MEMORIES_DESC line printed by step 3, verbatim>" })
create_artifact({ "id": "salesforce-plugin-info", "html_path": "plugin-info.artifact.html", "description": "Headless 360 plugin info — version, artifacts, and schedule" })
```

- **Profile** — titled `Salesforce User Profile`, **NO `mcp_tools`** (data inlined, makes no MCP calls). This artifact **is** the first-class, durable user-profile memory. It uses `window.cowork.askClaude` for a one-line role narrative (with a composed fallback) and caches via `window.storage`.
- **Command Center** — titled `Salesforce Command Center`, with **exactly one `mcp_tools` entry: `<DISPATCH_TOOL>`** (verbatim the value from step 0; the host blocks any tool not declared and not called this session). It pulls live data by calling only `<DISPATCH_TOOL>` via `window.cowork.callMcpTool`, running owner-scoped **SOQL** over `/services/data/v63.0/query` (flat records — no GraphQL envelopes, no memory dependency), and computes everything client-side: the **KPI strip** (open pipeline, weighted, closed-won this year, win rate), the **"What needs attention"** signals (quiet deals >30d, closing this week, new leads), the **Attainment** donut, and **pipeline-by-stage** + **amount-by-close-month** charts; caches via `window.storage`.
- **Memories** — titled `Headless 360 — Memories`, **NO `mcp_tools`** (data inlined, makes no MCP calls). It's the durable, searchable store of many smaller memories; its `description` carries the frontmatter index a future session greps to find and pull only relevant memories. `update` refreshes it. Its `description` **must** be the `MEMORIES_DESC` line from step 3 verbatim.
- **Plugin Info** — titled `Headless 360 — Plugin Info`, **NO `mcp_tools`** (data inlined, makes no MCP calls). It's the durable, human-visible record of the installed plugin version, the artifacts the plugin manages, and the daily maintenance schedule. `update` refreshes this card (with fresh timestamps and the then-current version) after every run.

Close by telling the user the Command Center is their live cockpit and stays current on its own, and to confirm the Profile looks right (re-run configure if anything's off).

## 5. Create the daily refresh schedule (do this before step 6)

**Always create this — do not ask, do not make it optional, and do it before the step 6 launcher.** The job defers to the **`update`** skill — the stable, version-aware maintenance entrypoint that applies any pending artifact migrations and then refreshes the data. This skill (`configure`) does not describe the refresh itself; `update` owns it.

**Name the task `Salesforce Updates`.** If the scheduling tool has a name/title field, set it to exactly `Salesforce Updates`. Regardless, the prompt's **first line must be `Salesforce Updates`** — some schedulers (e.g. `CronCreate`) have no title field, so the first line is the only durable identity, and `update` reads the baseline off this same task. **Create a scheduled task** to run daily (at an off-:00/:30 minute so it doesn't pile up with other jobs) with the prompt below **verbatim** — the `Created with plugin version 1.0.0-pilot.1` line is build-injected (SKILL.md is a template) and records which plugin version set the job up, so a later run can detect a job created by an older version and re-create it; leave it exactly as rendered.

> Salesforce Updates. Created with plugin version 1.0.0-pilot.1. Run `/update` for the current user: it applies any pending artifact migrations for the current plugin version, then refreshes the Command Center and user-profile from Salesforce. Invoke the `update` skill explicitly by that name (it is not model-auto-invoked). Emit no chat narration unless something fails. (Follow the `update` skill body — don't reproduce its steps or any HTML here.)

Use whatever scheduling capability is available in the session to create a recurring, durable daily task with that instruction as its prompt. **First check for an existing scheduled task that already does this refresh** — list the current scheduled tasks and look for one named `Salesforce Updates` or whose prompt starts with `Salesforce Updates` (match on that stable identity line, NOT the whole prompt — the `Created with plugin version …` line differs between versions). Also match a legacy job — one starting with `Daily Headless 360 update` or `Daily configure refresh` (earlier wordings) — as the same task. Then:
- **No existing refresh task** → create it now with the prompt above.
- **An existing refresh task whose version line matches `1.0.0-pilot.1`** → leave it; do NOT create a second (re-running configure at the same version won't duplicate it).
- **An existing refresh task created with a DIFFERENT (older) plugin version, or a legacy `Daily Headless 360 update` / `Daily configure refresh` job** → it's stale: delete it and create a fresh one with the prompt above, so the job is named `Salesforce Updates`, carries the current version, and defers to `update`. This is exactly the update-on-new-version path.

Either way this is silent setup — don't narrate it or ask permission; just ensure exactly one refresh task exists and it carries the current version, then move on to step 6. If some scheduled tasks auto-expire (e.g. after a fixed number of days), you may note once that they can re-run configure to renew.

## 6. "Four places I'll be most useful" launcher (last step)

Finish with **one** `display_widget` call, in `dynamic` mode, on the connected Salesforce MCP. It shows two things stacked: (a) a **fixed capability card** naming the four places the plugin helps, plus a "You stay in control" callout — **copy this block verbatim, changing nothing**; then (b) a row of exactly **4 personalized buttons** — the only part you author.

`display_widget` lives on the connected Salesforce MCP (`salesforce-h360`; the local `salesforce-ui` stand-in in dev). If it isn't available (e.g. a terminal that mounts no widget host), skip it silently and instead list the same 4 suggested actions as plain text — one line each, so the user still sees them.

**The capability card + callout are static — paste them exactly as written below.** They summarize the plugin's four areas and the control guarantee; they do not vary by user.

**Personalize only the 4 buttons.** Each is the highest-value next thing *this* user can do — derived from step 1 (role, dominant objects, book of business, open work), never a generic set. Each button's `onClick` posts a first-person prompt via `action/sendMessage`, must map to a real plugin skill (e.g. `daily-briefing`, `deal-signals`, `call-prep`, `renewal-radar`, `lead-triage`, `draft-outreach`, `inbox-sweep`, `expansion-whitespace`), and every one's `content` must carry a real name/number from step 1 (a specific account, opp, renewal, lead, or amount) — none may be a generic verb-only prompt. E.g. an AE with a big open renewal → *"Review my Acme Corp renewal and tell me what's at risk"*; an SDR heavy in Leads → *"Triage my new leads and tell me who to call first."* Resolve every value to a literal (no `<...>` or `{{token}}` left). Keep each button `label` short (2–4 words).

```jsonc
display_widget({
  "resourceType": "dynamic",
  "widgetDefinition": { "renderer": { "componentOverrides": { "$": {
    "type": "mosaic", "definition": "tile/mosaic", "children": [

      // ---- STATIC: capability card + control callout (copy verbatim) ----
      { "definition": "tile/card", "attributes": { "variant": "elevated", "padding": "lg" }, "children": [
        { "definition": "tile/text", "attributes": { "text": "Here are the four places I'll be most useful:", "variant": "section-title" } },
        { "definition": "tile/row", "attributes": { "gap": "md", "align": "stretch", "isWrapped": true }, "children": [

          { "definition": "tile/card", "attributes": { "variant": "outlined", "padding": "md", "width": "stretch", "minWidth": "md" }, "children": [
            { "definition": "tile/row", "attributes": { "gap": "sm", "align": "center" }, "children": [
              { "definition": "tile/icon", "attributes": { "name": "dashboard", "size": "md", "alt": "" } },
              { "definition": "tile/text", "attributes": { "text": "Start informed", "variant": "h5", "weight": "semibold" } } ] },
            { "definition": "tile/text", "attributes": { "text": "Get a morning briefing that combines your calendar, inbox, pipeline movement, and urgent follow-ups.", "variant": "body", "color": "muted" } },
            { "definition": "tile/text", "attributes": { "text": "DAILY BRIEFING · CALENDAR · INBOX SWEEP", "variant": "caption", "color": "primary" } } ] },

          { "definition": "tile/card", "attributes": { "variant": "outlined", "padding": "md", "width": "stretch", "minWidth": "md" }, "children": [
            { "definition": "tile/row", "attributes": { "gap": "sm", "align": "center" }, "children": [
              { "definition": "tile/icon", "attributes": { "name": "trending-up", "size": "md", "alt": "" } },
              { "definition": "tile/text", "attributes": { "text": "Move deals forward", "variant": "h5", "weight": "semibold" } } ] },
            { "definition": "tile/text", "attributes": { "text": "Catch stalled deals, prep for calls, map stakeholders, and leave every conversation with a clear next step.", "variant": "body", "color": "muted" } },
            { "definition": "tile/text", "attributes": { "text": "DEAL SIGNALS · CALL PREP · FOLLOW-UP", "variant": "caption", "color": "primary" } } ] },

          { "definition": "tile/card", "attributes": { "variant": "outlined", "padding": "md", "width": "stretch", "minWidth": "md" }, "children": [
            { "definition": "tile/row", "attributes": { "gap": "sm", "align": "center" }, "children": [
              { "definition": "tile/icon", "attributes": { "name": "message", "size": "md", "alt": "" } },
              { "definition": "tile/text", "attributes": { "text": "Communicate like you", "variant": "h5", "weight": "semibold" } } ] },
            { "definition": "tile/text", "attributes": { "text": "Draft outreach, objection responses, and follow-ups using the voice and patterns captured in your Profile.", "variant": "body", "color": "muted" } },
            { "definition": "tile/text", "attributes": { "text": "VOICE PROFILE · DRAFT OUTREACH · OBJECTIONS", "variant": "caption", "color": "primary" } } ] },

          { "definition": "tile/card", "attributes": { "variant": "outlined", "padding": "md", "width": "stretch", "minWidth": "md" }, "children": [
            { "definition": "tile/row", "attributes": { "gap": "sm", "align": "center" }, "children": [
              { "definition": "tile/icon", "attributes": { "name": "search", "size": "md", "alt": "" } },
              { "definition": "tile/text", "attributes": { "text": "Find the next opportunity", "variant": "h5", "weight": "semibold" } } ] },
            { "definition": "tile/text", "attributes": { "text": "Prioritize leads, research prospects, uncover account whitespace, and spot renewals that need attention.", "variant": "body", "color": "muted" } },
            { "definition": "tile/text", "attributes": { "text": "LEAD TRIAGE · RESEARCH · EXPANSION · RENEWALS", "variant": "caption", "color": "primary" } } ] }

        ] },
        { "definition": "tile/callout", "attributes": { "variant": "success", "iconName": "lock", "title": "You stay in control.", "description": "I'll show you proposed Salesforce updates before writing them, and drafts stay drafts until you approve them." } }
      ] },

      // ---- PERSONALIZED: 4 buttons (author these from step 1; resolve every value to a literal) ----
      { "definition": "tile/text", "attributes": { "text": "What next, <FirstName>?", "variant": "h3" } },
      { "definition": "tile/text", "attributes": { "text": "Pick one — I'll get started.", "variant": "body", "color": "muted" } },
      { "definition": "tile/row", "attributes": { "gap": "sm", "isWrapped": true }, "children": [
        { "definition": "tile/button", "attributes": { "label": "<short label>", "variant": "primary",
          "onClick": { "definition": "action/sendMessage", "attributes": { "content": "<first-person, user-specific prompt>" } } } },
        { "definition": "tile/button", "attributes": { "label": "<short label>",
          "onClick": { "definition": "action/sendMessage", "attributes": { "content": "<first-person, user-specific prompt>" } } } },
        { "definition": "tile/button", "attributes": { "label": "<short label>",
          "onClick": { "definition": "action/sendMessage", "attributes": { "content": "<first-person, user-specific prompt>" } } } },
        { "definition": "tile/button", "attributes": { "label": "<short label>",
          "onClick": { "definition": "action/sendMessage", "attributes": { "content": "<first-person, user-specific prompt>" } } } }
      ] }

    ] } } } }
})
```

**Close in the SAME turn as the launcher — one short line, then stop.** In the message that carries the `display_widget` call, add a single closing sentence (e.g. "You're all set — pick one above and I'll get started.") and nothing more: no summary of what you did, no recap of the profile, no list of the buttons, no follow-up questions. Do not end on the tool call alone and wait — a bare tool-call turn makes the harness re-prompt you for a follow-up, costing a full extra round. (If `display_widget` was unavailable and you fell back to text, the four plain-text actions plus that one closing line are the last thing you emit.)

## Appendix — artifact HTML source

The four artifacts render from sibling template files: `skills/configure/profile.html`, `skills/configure/command-center.html`, `skills/configure/memories.html`, and `skills/configure/plugin-info.html` under the plugin root (step 3's shell command self-resolves that root — `$CLAUDE_PLUGIN_ROOT` if set, else the installed-plugin globs). `create_artifact`/`update_artifact` take an **`html_path`**, not inline HTML — so the substitution is a file operation (a `python3` `.replace` writing to your scratch dir), and you pass that path. **Never Read a template into your reply and retype it** — reproducing hundreds of lines of HTML as output tokens was the dominant cost of this skill; the only content you should ever type out is the small step-2 dataset (`PROFILE`, `PROFILE_DESC`, the `MEMORIES` array, and the `OWNER_ID`/`DISPATCH_TOOL`/quota values). Memory is stored **only** in artifacts (never a disk file or a `salesforce-memory` MCP) — in Claude Desktop the shell home is ephemeral, so those wouldn't persist; artifacts do.
