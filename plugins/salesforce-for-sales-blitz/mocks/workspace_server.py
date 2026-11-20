"""Mock Google Workspace (Gmail, Calendar, Drive) MCP server for the Grok Bot Blitz.

Ships only in the "Salesforce for Sales (Blitz)" plugin copy. It stands in for the real
connectors, which procurement has not approved yet, with fixed data that matches the
Blitz org (aiforce.prod2): the same accounts, contacts, opportunities and meetings.

- Standard library only (Python 3.9+), so it runs in any agent VM without installs.
- Speaks MCP JSON-RPC over stdio (one JSON message per line). `--http PORT` serves the
  same tools over plain JSON POST as a fallback for hosts that cannot launch stdio.
- Writes (drafts, sends, new events) live in memory for this process only and are
  appended to a JSONL log (BLITZ_MOCK_LOG, default: the system temp dir). Nothing is
  ever sent or booked anywhere.
- "Now" is the real clock in America/Los_Angeles; BLITZ_MOCK_NOW (ISO) overrides it.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
import threading

SERVER_NAME = "workspace"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL = "2025-06-18"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TIME_NOTE = (
    "America/Los_Angeles (Pacific). The seller works in Pacific time: show times as given, in PT "
    "(the *_pt fields), not converted to the reader's time zone."
)
MOCK_NOTE = "Mock connector for the Salesforce Blitz test org: nothing was sent or booked."

try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo("America/Los_Angeles")
except Exception:  # no tz database in the VM: Pacific Standard Time covers the Blitz window
    TZ = dt.timezone(dt.timedelta(hours=-8), "PST")


class ToolError(Exception):
    """Bad arguments or unknown ids; returned to the agent as an isError tool result."""


# ---------------------------------------------------------------- time helpers


def now():
    override = os.environ.get("BLITZ_MOCK_NOW")
    if override:
        return parse_dt(override)
    return dt.datetime.now(TZ)


def parse_dt(value, field="datetime"):
    """ISO date or datetime (offset optional, naive = Pacific), or today/tomorrow/yesterday."""
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=TZ)
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{field} must be an ISO date or datetime string")
    text = value.strip()
    word = text.lower()
    if word in ("today", "tomorrow", "yesterday"):
        base = dt.datetime.combine(now().date(), dt.time(0, 0), tzinfo=TZ)
        return base + dt.timedelta(days={"today": 0, "tomorrow": 1, "yesterday": -1}[word])
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    try:
        if len(text) == 10:
            parsed = dt.datetime.combine(dt.date.fromisoformat(text), dt.time(0, 0))
        else:
            parsed = dt.datetime.fromisoformat(text.replace(" ", "T", 1))
    except ValueError:
        raise ToolError(f"{field} {value!r} is not an ISO date (YYYY-MM-DD) or datetime (YYYY-MM-DDTHH:MM)")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ)
    return parsed


def parse_day(value, field="date"):
    return parse_dt(value, field).astimezone(TZ).date()


def iso(value):
    return value.astimezone(TZ).isoformat(timespec="minutes")


def clock(value):
    """3:00 PM, in Pacific."""
    value = value.astimezone(TZ)
    return f"{value.hour % 12 or 12}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"


def pt(value):
    """Readable Pacific time, e.g. "Fri Nov 20, 3:00 PM PT", so the agent shows the seller's time as is."""
    value = value.astimezone(TZ)
    return f"{value.strftime('%a %b')} {value.day}, {clock(value)} PT"


def pt_range(start, end):
    """Fri Nov 20, 3:00 PM - 3:30 PM PT (end's date added if it is another day)."""
    start, end = start.astimezone(TZ), end.astimezone(TZ)
    tail = clock(end) if end.date() == start.date() else f"{end.strftime('%a %b')} {end.day}, {clock(end)}"
    return f"{start.strftime('%a %b')} {start.day}, {clock(start)} - {tail} PT"


def day_bounds(day):
    start = dt.datetime.combine(day, dt.time(0, 0), tzinfo=TZ)
    return start, start + dt.timedelta(days=1)


def hhmm(value, field):
    try:
        hours, minutes = (int(p) for p in str(value).split(":"))
        return dt.time(hours, minutes)
    except Exception:
        raise ToolError(f"{field} must be HH:MM")


# ---------------------------------------------------------------- data + state


def text_of(value):
    """Data files store long text as a list of lines for readable diffs."""
    if isinstance(value, list):
        return "\n".join(value)
    return value or ""


def load_json(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


class Store:
    def __init__(self):
        email = load_json("email.json")
        calendar = load_json("calendar.json")
        docs = load_json("docs.json")
        self.mailbox = email["mailbox"]
        self.directory = email["directory"]
        self.messages = []
        for m in email["messages"]:
            msg = dict(m)
            msg["body"] = text_of(m.get("body"))
            msg["_date"] = parse_dt(m["date"])
            self.messages.append(msg)
        self.events = []
        for e in calendar["events"]:
            self.events.append(self._event(e))
        self.busy = {}
        for addr, blocks in calendar.get("busy", {}).items():
            if addr.startswith("_"):
                continue
            self.busy[addr.lower()] = [
                {"start": parse_dt(b["start"]), "end": parse_dt(b["end"]), "label": b.get("label", "Busy")} for b in blocks
            ]
        self.working_hours = calendar.get("working_hours", {"start": "09:00", "end": "17:00"})
        self.docs = []
        for d in docs["docs"]:
            doc = dict(d)
            doc["content"] = text_of(d.get("content"))
            self.docs.append(doc)
        self.drafts = {}
        self.counter = 0
        self.lock = threading.Lock()

    @staticmethod
    def _event(e):
        ev = dict(e)
        ev["description"] = text_of(e.get("description"))
        if e.get("all_day"):
            day = parse_day(e["start"])
            last = parse_day(e.get("end", e["start"]))
            ev["_start"] = day_bounds(day)[0]
            ev["_end"] = day_bounds(last)[1] if last >= day else day_bounds(day)[1]
        else:
            ev["_start"] = parse_dt(e["start"])
            ev["_end"] = parse_dt(e["end"])
        return ev

    def visible(self):
        """Messages dated up to now: a run before Blitz day does not see tomorrow's mail."""
        cutoff = now()
        return [m for m in self.messages if m["_date"] <= cutoff]

    def next_id(self, prefix):
        self.counter += 1
        return f"{prefix}-{self.counter:03d}"

    # people

    def resolve_person(self, value):
        """Name or address -> {name, email}; unknown bare names are an error."""
        if not isinstance(value, str) or not value.strip():
            raise ToolError("recipient must be a non-empty string")
        text = value.strip()
        match = re.search(r"<([^>]+@[^>]+)>", text)
        if match:
            addr = match.group(1).strip()
            name = text[: match.start()].strip().strip('"') or addr
            known = self.person_by_email(addr)
            return {"name": known["name"] if known else name, "email": addr}
        if "@" in text:
            known = self.person_by_email(text)
            return {"name": known["name"] if known else text, "email": text}
        lowered = text.lower()
        hits = [p for p in self.directory if p["name"].lower() == lowered]
        if not hits:
            hits = [p for p in self.directory if lowered in p["name"].lower()]
        if len(hits) == 1:
            return {"name": hits[0]["name"], "email": hits[0]["email"]}
        if len(hits) > 1:
            names = ", ".join(f'{p["name"]} <{p["email"]}>' for p in hits)
            raise ToolError(f"{text!r} matches more than one contact: {names}. Use an email address.")
        raise ToolError(f"No email address on file for {text!r}. Ask the user for it.")

    def person_by_email(self, addr):
        lowered = addr.lower()
        for p in self.directory:
            if p["email"].lower() == lowered:
                return p
        if lowered == self.mailbox["email"].lower():
            return {"name": self.mailbox["name"], "email": self.mailbox["email"]}
        return None

    def recipients(self, value, field):
        if value is None:
            return []
        items = value if isinstance(value, list) else re.split(r"[;,]", value) if isinstance(value, str) else None
        if items is None:
            raise ToolError(f"{field} must be an address, a name, or a list of them")
        return [self.resolve_person(v) for v in items if str(v).strip()]


STORE = None


def store():
    global STORE
    if STORE is None:
        STORE = Store()
    return STORE


def log_write(tool, args, result):
    path = os.environ.get("BLITZ_MOCK_LOG") or os.path.join(tempfile.gettempdir(), "blitz-workspace-mock.jsonl")
    line = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "tool": tool, "args": args, "result": result}
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- shared helpers


def as_int(args, key, default, low, high):
    value = args.get(key, default)
    if value is None:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ToolError(f"{key} must be an integer")
    return max(low, min(high, number))


def terms_match(haystack, terms):
    lowered = haystack.lower()
    return all(t in lowered for t in terms)


def person_label(p):
    return f'{p["name"]} <{p["email"]}>'


def message_summary(m):
    return {
        "id": m["id"],
        "thread_id": m["thread_id"],
        "date": iso(m["_date"]),
        "date_pt": pt(m["_date"]),
        "from": person_label(m["from"]),
        "to": [person_label(p) for p in m.get("to", [])],
        "cc": [person_label(p) for p in m.get("cc", [])],
        "subject": m["subject"],
        "snippet": re.sub(r"\s+", " ", m["body"])[:220],
        "unread": "UNREAD" in m.get("labels", []),
        "labels": m.get("labels", []),
        "attachments": m.get("attachments", []),
    }


def message_full(m):
    out = message_summary(m)
    out.pop("snippet")
    out["body"] = m["body"]
    return out


def message_text(m):
    people = [m["from"]] + m.get("to", []) + m.get("cc", [])
    names = " ".join(f'{p["name"]} {p["email"]}' for p in people)
    return f'{m["subject"]}\n{m["body"]}\n{names}\n{m.get("account", "")}'


QUERY_OPERATOR = re.compile(r'(\w+):("[^"]*"|\S+)')


def parse_query(query):
    """Gmail-style query: free terms plus from: to: subject: is:unread after: before: label:."""
    ops = {}
    if not query:
        return [], ops

    def take(match):
        ops.setdefault(match.group(1).lower(), []).append(match.group(2).strip('"').lower())
        return " "

    rest = QUERY_OPERATOR.sub(take, query)
    terms = [t.lower() for t in re.findall(r'"[^"]+"|\S+', rest)]
    terms = [t.strip('"') for t in terms if t.upper() not in ("AND", "OR")]
    return terms, ops


def addr_match(person_list, needle):
    return any(needle in p["name"].lower() or needle in p["email"].lower() for p in person_list)


# ---------------------------------------------------------------- email tools


def search_email(args):
    s = store()
    terms, ops = parse_query(args.get("query"))
    limit = as_int(args, "limit", 10, 1, 50)
    from_filter = [v.lower() for v in ops.get("from", [])] + ([args["from"].lower()] if args.get("from") else [])
    to_filter = [v.lower() for v in ops.get("to", [])] + ([args["to"].lower()] if args.get("to") else [])
    after = args.get("after") or (ops.get("after") or [None])[0]
    before = args.get("before") or (ops.get("before") or [None])[0]
    after_dt = parse_dt(after.replace("/", "-"), "after") if after else None
    before_dt = parse_dt(before.replace("/", "-"), "before") if before else None
    hits = []
    for m in s.visible():
        if terms and not terms_match(message_text(m), terms):
            continue
        if any(not addr_match([m["from"]], f) for f in from_filter):
            continue
        if any(not addr_match(m.get("to", []) + m.get("cc", []), f) for f in to_filter):
            continue
        if any(t not in m["subject"].lower() for t in ops.get("subject", [])):
            continue
        if "unread" in ops.get("is", []) and "UNREAD" not in m.get("labels", []):
            continue
        labels = [lbl.lower() for lbl in m.get("labels", [])]
        if any(lbl not in labels for lbl in ops.get("label", []) + ops.get("in", [])):
            continue
        if after_dt and m["_date"] < after_dt:
            continue
        if before_dt and m["_date"] >= before_dt:
            continue
        hits.append(m)
    hits.sort(key=lambda m: m["_date"], reverse=True)
    return {"total": len(hits), "messages": [message_summary(m) for m in hits[:limit]]}


def list_unread_email(args):
    s = store()
    hours = as_int(args, "hours", 48, 1, 24 * 30)
    limit = as_int(args, "limit", 20, 1, 50)
    since = now() - dt.timedelta(hours=hours)
    hits = [m for m in s.visible() if "UNREAD" in m.get("labels", []) and m["_date"] >= since]
    hits.sort(key=lambda m: m["_date"], reverse=True)
    return {"since": iso(since), "total": len(hits), "messages": [message_summary(m) for m in hits[:limit]]}


def get_email_thread(args):
    s = store()
    key = args.get("thread_id") or args.get("message_id")
    if not key:
        raise ToolError("thread_id is required")
    thread_id = key
    for m in s.visible():
        if m["id"] == key:
            thread_id = m["thread_id"]
            break
    msgs = sorted((m for m in s.visible() if m["thread_id"] == thread_id), key=lambda m: m["_date"])
    if not msgs:
        raise ToolError(f"No thread or message with id {key!r}. Use search_email to find ids.")
    return {"thread_id": thread_id, "subject": msgs[0]["subject"], "messages": [message_full(m) for m in msgs]}


def list_sent_email(args):
    s = store()
    limit = as_int(args, "limit", 20, 1, 50)
    to_filter = (args.get("to") or "").lower()
    after_dt = parse_dt(args["after"], "after") if args.get("after") else None
    hits = [
        m
        for m in s.visible()
        if "SENT" in m.get("labels", [])
        and (not to_filter or addr_match(m.get("to", []) + m.get("cc", []), to_filter))
        and (not after_dt or m["_date"] >= after_dt)
    ]
    hits.sort(key=lambda m: m["_date"], reverse=True)
    return {"total": len(hits), "messages": [message_full(m) for m in hits[:limit]]}


def _require_text(args, key):
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{key} is required")
    return value


def create_email_draft(args):
    s = store()
    to = s.recipients(args.get("to"), "to")
    if not to:
        raise ToolError("to is required")
    cc = s.recipients(args.get("cc"), "cc")
    subject = _require_text(args, "subject")
    body = _require_text(args, "body")
    thread_id = None
    reply_to = args.get("reply_to_id")
    if reply_to:
        found = [m for m in s.messages if reply_to in (m["id"], m["thread_id"])]
        if not found:
            raise ToolError(f"reply_to_id {reply_to!r} is not a known message or thread id")
        thread_id = found[0]["thread_id"]
    with s.lock:
        draft_id = s.next_id("draft")
        draft = {"id": draft_id, "thread_id": thread_id, "to": to, "cc": cc, "subject": subject, "body": body}
        s.drafts[draft_id] = draft
    result = {
        "status": "draft_created",
        "mock": True,
        "draft_id": draft_id,
        "draft": {**draft, "to": [person_label(p) for p in to], "cc": [person_label(p) for p in cc]},
        "note": MOCK_NOTE + " The draft is saved in this mock mailbox only.",
    }
    log_write("create_email_draft", args, {"draft_id": draft_id})
    return result


def list_email_drafts(args):
    s = store()
    drafts = [{**d, "to": [person_label(p) for p in d["to"]], "cc": [person_label(p) for p in d["cc"]]} for d in s.drafts.values()]
    return {"total": len(drafts), "drafts": drafts}


def send_email(args):
    s = store()
    draft_id = args.get("draft_id")
    if draft_id:
        draft = s.drafts.get(draft_id)
        if not draft:
            raise ToolError(f"No draft with id {draft_id!r}")
        to, cc, subject, body, thread_id = draft["to"], draft["cc"], draft["subject"], draft["body"], draft["thread_id"]
    else:
        to = s.recipients(args.get("to"), "to")
        if not to:
            raise ToolError("to is required (or pass draft_id)")
        cc = s.recipients(args.get("cc"), "cc")
        subject = _require_text(args, "subject")
        body = _require_text(args, "body")
        thread_id = None
    with s.lock:
        message_id = s.next_id("msg-sent")
        msg = {
            "id": message_id,
            "thread_id": thread_id or f"thr-{message_id}",
            "from": {"name": s.mailbox["name"], "email": s.mailbox["email"]},
            "to": to,
            "cc": cc,
            "subject": subject,
            "body": body,
            "labels": ["SENT"],
            "_date": now(),
        }
        s.messages.append(msg)
        if draft_id:
            s.drafts.pop(draft_id, None)
    log_write("send_email", args, {"message_id": message_id})
    return {"status": "sent", "mock": True, "message_id": message_id, "thread_id": msg["thread_id"], "note": MOCK_NOTE}


# ---------------------------------------------------------------- calendar tools


def event_out(e):
    out = {k: v for k, v in e.items() if not k.startswith("_")}
    if e.get("all_day"):
        out["start"] = e["_start"].date().isoformat()
        out["end"] = (e["_end"] - dt.timedelta(days=1)).date().isoformat()
    else:
        out["start"] = iso(e["_start"])
        out["end"] = iso(e["_end"])
        out["when_pt"] = pt_range(e["_start"], e["_end"])
    return out


def window_from(args):
    if args.get("day") or args.get("date"):
        start, end = day_bounds(parse_day(args.get("day") or args.get("date"), "day"))
    elif args.get("start"):
        start = parse_dt(args["start"], "start")
        end = parse_dt(args["end"], "end") if args.get("end") else start + dt.timedelta(days=1)
        if len(str(args.get("end", ""))) == 10:
            end = day_bounds(end.date())[1]
    else:
        start, end = day_bounds(now().date())
    if end <= start:
        raise ToolError("end must be after start")
    if end - start > dt.timedelta(days=62):
        raise ToolError("window is limited to 62 days")
    return start, end


def list_calendar_events(args):
    s = store()
    start, end = window_from(args)
    terms = [t.lower() for t in (args.get("query") or "").split()]
    hits = [
        e
        for e in s.events
        if e["_start"] < end
        and e["_end"] > start
        and (not terms or terms_match(f'{e["title"]} {e.get("description", "")} {e.get("account", "")} {json.dumps(e.get("attendees", []))}', terms))
    ]
    hits.sort(key=lambda e: e["_start"])
    return {"timezone": TIME_NOTE, "start": iso(start), "end": iso(end), "events": [event_out(e) for e in hits]}


def get_calendar_event(args):
    key = args.get("event_id")
    if not key:
        raise ToolError("event_id is required")
    for e in store().events:
        if e["id"] == key:
            return event_out(e)
    raise ToolError(f"No event with id {key!r}. Use list_calendar_events to find ids.")


def merge(intervals):
    out = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def get_calendar_availability(args):
    s = store()
    first = parse_day(args.get("start_date") or "today", "start_date")
    last = parse_day(args["end_date"], "end_date") if args.get("end_date") else first
    if last < first:
        raise ToolError("end_date must be on or after start_date")
    if (last - first).days > 13:
        raise ToolError("availability is limited to 14 days")
    duration = dt.timedelta(minutes=as_int(args, "duration_minutes", 30, 5, 480))
    day_start = hhmm(args.get("working_hours_start") or s.working_hours["start"], "working_hours_start")
    day_end = hhmm(args.get("working_hours_end") or s.working_hours["end"], "working_hours_end")
    people = s.recipients(args.get("attendees"), "attendees")
    sources = {}
    for p in people:
        addr = p["email"].lower()
        sources[person_label(p)] = "free/busy shared" if addr in s.busy else "free/busy not shared (treated as free)"
    days = []
    day = first
    while day <= last:
        open_at = dt.datetime.combine(day, day_start, tzinfo=TZ)
        close_at = dt.datetime.combine(day, day_end, tzinfo=TZ)
        busy = []
        for e in s.events:
            if e["_start"] < close_at and e["_end"] > open_at and e.get("show_as", "busy") != "free":
                busy.append({"start": max(e["_start"], open_at), "end": min(e["_end"], close_at), "who": "you", "title": e["title"]})
        for p in people:
            for b in s.busy.get(p["email"].lower(), []):
                if b["start"] < close_at and b["end"] > open_at:
                    busy.append({"start": max(b["start"], open_at), "end": min(b["end"], close_at), "who": p["name"], "title": b["label"]})
        merged = merge((b["start"], b["end"]) for b in busy)
        free, cursor = [], open_at
        for start, end in merged:
            if start - cursor >= duration:
                free.append({"start": iso(cursor), "end": iso(start), "when_pt": pt_range(cursor, start)})
            cursor = max(cursor, end)
        if close_at - cursor >= duration:
            free.append({"start": iso(cursor), "end": iso(close_at), "when_pt": pt_range(cursor, close_at)})
        days.append(
            {
                "date": day.isoformat(),
                "weekday": day.strftime("%A"),
                "weekend": day.weekday() >= 5,
                "free": free,
                "busy": [{"start": iso(b["start"]), "end": iso(b["end"]), "when_pt": pt_range(b["start"], b["end"]), "who": b["who"], "title": b["title"]} for b in sorted(busy, key=lambda b: b["start"])],
            }
        )
        day += dt.timedelta(days=1)
    return {
        "timezone": TIME_NOTE,
        "working_hours": f"{day_start.strftime('%H:%M')}-{day_end.strftime('%H:%M')}",
        "duration_minutes": int(duration.total_seconds() // 60),
        "attendees": sources,
        "days": days,
    }


def create_calendar_event(args):
    s = store()
    title = _require_text(args, "title")
    start = parse_dt(_require_text(args, "start"), "start")
    if args.get("end"):
        end = parse_dt(args["end"], "end")
    else:
        end = start + dt.timedelta(minutes=as_int(args, "duration_minutes", 30, 5, 480))
    if end <= start:
        raise ToolError("end must be after start")
    attendees = [{**p, "response": "needsAction"} for p in s.recipients(args.get("attendees"), "attendees")]
    conflicts = [event_out(e)["title"] + " (" + pt(e["_start"]) + ")" for e in s.events if e["_start"] < end and e["_end"] > start and not e.get("all_day")]
    with s.lock:
        event_id = s.next_id("evt-new")
        event = {
            "id": event_id,
            "title": title,
            "start": iso(start),
            "end": iso(end),
            "when_pt": pt_range(start, end),
            "location": args.get("location") or "",
            "attendees": attendees,
            "description": args.get("description") or "",
            "organizer": person_label(s.mailbox),
            "source": "created in this session",
        }
        s.events.append(s._event(event))
    log_write("create_calendar_event", args, {"event_id": event_id})
    return {
        "status": "created",
        "mock": True,
        "event": event,
        "conflicts": conflicts,
        "note": MOCK_NOTE + " No invitations went out.",
    }


# ---------------------------------------------------------------- docs tools


def doc_summary(d):
    return {
        "id": d["id"],
        "title": d["title"],
        "account": d.get("account"),
        "type": d.get("type"),
        "owner": d.get("owner"),
        "modified": d.get("modified"),
        "url": d.get("url"),
        "snippet": re.sub(r"\s+", " ", d["content"])[:220],
    }


def search_docs(args):
    terms, _ = parse_query(args.get("query"))
    account = (args.get("account") or "").lower()
    limit = as_int(args, "limit", 10, 1, 50)
    hits = []
    for d in store().docs:
        if account and account not in (d.get("account") or "").lower():
            continue
        blob = f'{d["title"]} {d.get("account", "")} {d.get("type", "")} {d["content"]}'
        if terms and not terms_match(blob, terms):
            continue
        title_hits = sum(t in d["title"].lower() for t in terms)
        hits.append((title_hits, d.get("modified", ""), d))
    hits.sort(key=lambda h: (h[0], h[1]), reverse=True)
    return {"total": len(hits), "docs": [doc_summary(h[2]) for h in hits[:limit]]}


def get_doc(args):
    key = (args.get("doc_id") or args.get("title") or "").strip()
    if not key:
        raise ToolError("doc_id is required")
    docs = store().docs
    for d in docs:
        if d["id"] == key or d["title"].lower() == key.lower():
            return {**doc_summary(d), "content": d["content"]}
    fuzzy = [d for d in docs if key.lower() in d["title"].lower()]
    if len(fuzzy) == 1:
        return {**doc_summary(fuzzy[0]), "content": fuzzy[0]["content"]}
    raise ToolError(f"No doc with id or title {key!r}. Use search_docs to find ids.")


# ---------------------------------------------------------------- tool registry

S = {"type": "string"}
I = {"type": "integer"}
PEOPLE = {
    "description": "Email address, 'Name <address>', a contact's full name, or a list of these.",
    "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}],
}


def schema(props, required=()):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


TOOLS = [
    (
        "search_email",
        "Search the user's mailbox (Gmail) for messages, newest first. Free-text terms match subject, body, "
        "names and addresses; Gmail-style operators work too (from: to: subject: is:unread after:YYYY-MM-DD "
        "before:YYYY-MM-DD label:sent).",
        schema(
            {
                "query": {**S, "description": "Search terms and optional operators, e.g. 'Cobalt renewal from:victor'."},
                "from": {**S, "description": "Sender name or address fragment."},
                "to": {**S, "description": "Recipient name or address fragment."},
                "after": {**S, "description": "Only messages on or after this date (YYYY-MM-DD)."},
                "before": {**S, "description": "Only messages before this date (YYYY-MM-DD)."},
                "limit": {**I, "description": "Max results (default 10, max 50)."},
            }
        ),
        search_email,
    ),
    (
        "list_unread_email",
        "List unread inbox messages from the last N hours (default 48), newest first.",
        schema({"hours": {**I, "description": "Look-back window in hours (default 48)."}, "limit": I}),
        list_unread_email,
    ),
    (
        "get_email_thread",
        "Read a full email thread (every message with full body and attachments) by thread_id or message id.",
        schema({"thread_id": {**S, "description": "Thread id or message id from search results."}}, ["thread_id"]),
        get_email_thread,
    ),
    (
        "list_sent_email",
        "List messages the user sent, newest first, with full bodies (useful for learning their writing voice).",
        schema({"limit": I, "to": {**S, "description": "Recipient name or address fragment."}, "after": {**S, "description": "YYYY-MM-DD."}}),
        list_sent_email,
    ),
    (
        "create_email_draft",
        "Save an email draft in the user's mailbox. Does not send. Use reply_to_id to draft a reply in an existing thread.",
        schema(
            {
                "to": PEOPLE,
                "cc": PEOPLE,
                "subject": S,
                "body": {**S, "description": "Plain-text body."},
                "reply_to_id": {**S, "description": "Message or thread id this replies to."},
            },
            ["to", "subject", "body"],
        ),
        create_email_draft,
    ),
    (
        "list_email_drafts",
        "List drafts saved in this session.",
        schema({}),
        list_email_drafts,
    ),
    (
        "send_email",
        "Send an email, either a saved draft (draft_id) or a new message. Only call this after the user has "
        "explicitly confirmed sending this exact message.",
        schema({"draft_id": S, "to": PEOPLE, "cc": PEOPLE, "subject": S, "body": S}),
        send_email,
    ),
    (
        "list_calendar_events",
        "List the user's calendar events (Google Calendar) for a day or a time window, in Pacific time (PT; show "
        "times as PT, not converted). "
        "With no arguments, returns today. Accepts 'today', 'tomorrow', or YYYY-MM-DD.",
        schema(
            {
                "day": {**S, "description": "A single day: YYYY-MM-DD, 'today', or 'tomorrow'."},
                "start": {**S, "description": "Window start (date or datetime)."},
                "end": {**S, "description": "Window end (date or datetime; a date includes that whole day)."},
                "query": {**S, "description": "Optional text filter on title, description, account and attendees."},
            }
        ),
        list_calendar_events,
    ),
    (
        "get_calendar_event",
        "Get one calendar event with attendees, response status, location and description.",
        schema({"event_id": S}, ["event_id"]),
        get_calendar_event,
    ),
    (
        "get_calendar_availability",
        "Free/busy for the user and optional attendees across a date range (max 14 days). Returns free slots of "
        "at least duration_minutes inside working hours (default 09:00-17:00 Pacific) and the busy blocks behind them.",
        schema(
            {
                "start_date": {**S, "description": "YYYY-MM-DD, 'today', or 'tomorrow'."},
                "end_date": {**S, "description": "YYYY-MM-DD (inclusive). Defaults to start_date."},
                "attendees": PEOPLE,
                "duration_minutes": {**I, "description": "Minimum slot length (default 30)."},
                "working_hours_start": {**S, "description": "HH:MM, default 09:00."},
                "working_hours_end": {**S, "description": "HH:MM, default 17:00."},
            },
            ["start_date"],
        ),
        get_calendar_availability,
    ),
    (
        "create_calendar_event",
        "Create a calendar event and invite attendees. Only call this after the user has confirmed the time, "
        "attendees and title. Reports any conflicts with existing events.",
        schema(
            {
                "title": S,
                "start": {**S, "description": "Start datetime, e.g. 2026-11-23T10:00 (Pacific if no offset)."},
                "end": {**S, "description": "End datetime; or give duration_minutes."},
                "duration_minutes": I,
                "attendees": PEOPLE,
                "description": S,
                "location": S,
            },
            ["title", "start"],
        ),
        create_calendar_event,
    ),
    (
        "search_docs",
        "Search the user's documents (Google Drive): proposals, contracts, order forms, QBR notes, and internal "
        "policies such as the legal playbook and discount policy. Filter by account name and/or text.",
        schema(
            {
                "query": {**S, "description": "Text to match in title and content."},
                "account": {**S, "description": "Account name or fragment, e.g. 'Cobalt'."},
                "limit": I,
            }
        ),
        search_docs,
    ),
    (
        "get_doc",
        "Read a document's full text by doc_id (or exact title).",
        schema({"doc_id": {**S, "description": "Doc id from search_docs, or the doc title."}}, ["doc_id"]),
        get_doc,
    ),
]
HANDLERS = {name: fn for name, _, _, fn in TOOLS}
INSTRUCTIONS = (
    "Mock Google Workspace (Gmail, Google Calendar, Google Drive) for the Salesforce Blitz test org. Data matches "
    "the org's accounts, contacts, opportunities and meetings. The seller works in Pacific time: every time is "
    "America/Los_Angeles, and answers should show it in PT as given (the *_pt fields), not converted to the "
    "reader's time zone. Writes stay in "
    "this mock: nothing is sent or booked."
)


def tool_list():
    return [
        {"name": name, "title": name.replace("_", " ").capitalize(), "description": f"[Mock Google Workspace] {desc}", "inputSchema": sch}
        for name, desc, sch, _ in TOOLS
    ]


# ---------------------------------------------------------------- JSON-RPC


def call_tool(params):
    name = params.get("name")
    args = params.get("arguments") or {}
    if name not in HANDLERS:
        raise LookupError(name)
    if not isinstance(args, dict):
        return {"content": [{"type": "text", "text": "arguments must be an object"}], "isError": True}
    try:
        result = HANDLERS[name](args)
    except ToolError as err:
        return {"content": [{"type": "text", "text": json.dumps({"error": str(err)})}], "isError": True}
    return {"content": [{"type": "text", "text": json.dumps(result, indent=1)}], "isError": False}


def handle(message):
    """One JSON-RPC message in, one response dict (or None for notifications) out."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params") or {}
    if msg_id is None:
        return None  # notification (initialized, cancelled, ...): nothing to answer
    try:
        if method == "initialize":
            result = {
                "protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "title": "Mock Google Workspace (Blitz)", "version": SERVER_VERSION},
                "instructions": INSTRUCTIONS,
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": tool_list()}
        elif method == "tools/call":
            try:
                result = call_tool(params)
            except LookupError:
                return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": f"Unknown tool: {params.get('name')}"}}
        elif method in ("resources/list", "prompts/list"):
            result = {method.split("/")[0]: []}
        else:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    except Exception as err:  # never crash the server on one bad call
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": f"Internal error: {err}"}}
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def handle_payload(payload):
    if isinstance(payload, list):
        replies = [r for r in (handle(m) for m in payload) if r is not None]
        return replies or None
    return handle(payload)


def serve_stdio():
    store()
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            reply = handle_payload(payload)
        if reply is not None:
            out.write(json.dumps(reply) + "\n")
            out.flush()


def serve_http(port, host):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    token = os.environ.get("BLITZ_MOCK_TOKEN")
    store()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body=None):
            data = b"" if body is None else json.dumps(body).encode("utf-8")
            self.send_response(code)
            if body is not None:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if token and self.headers.get("Authorization") != f"Bearer {token}":
                return self._send(401, {"error": "unauthorized"})
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"null")
            except ValueError:
                return self._send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            reply = handle_payload(payload)
            return self._send(202) if reply is None else self._send(200, reply)

        def do_GET(self):
            self._send(405, {"error": "use POST"})

        def log_message(self, fmt, *a):
            sys.stderr.write("workspace-mock: " + fmt % a + "\n")

    server = ThreadingHTTPServer((host, port), Handler)
    sys.stderr.write(f"workspace-mock: listening on http://{host}:{port}/\n")
    server.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--http", type=int, metavar="PORT", help="serve JSON-RPC over HTTP POST instead of stdio")
    parser.add_argument("--host", default="127.0.0.1")
    opts = parser.parse_args(argv)
    if opts.http:
        serve_http(opts.http, opts.host)
    else:
        serve_stdio()


if __name__ == "__main__":
    main()
