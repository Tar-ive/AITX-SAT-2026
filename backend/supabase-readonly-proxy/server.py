import json
import os
import re
import threading
import http.client
import time
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import discord
import psycopg

MAX_ROWS = 100
FORBIDDEN = re.compile(r"\b(insert|update|delete|merge|create|alter|drop|truncate|grant|revoke|copy|call|do|execute|set|reset|begin|commit|rollback|vacuum|analyze|watchlists)\b", re.I)
EPISODE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{2,127}\Z")
EPISODE_TASK_TYPES = {"price_watch", "review_audit", "shopping_research", "chat", "coordination"}
JOB_NAME = re.compile(r"[a-z0-9][a-z0-9-]{2,63}\Z")
REQUEST_LOCK = threading.Lock()
REQUESTS_PATH = Path(os.environ.get("CRON_BROKER_STATE_PATH", "/data/cron_requests.json"))
FEEDBACK_LOCK = threading.Lock()
FEEDBACK_PATH = Path(os.environ.get("HERMES_FEEDBACK_STATE_PATH", "/data/hermes_feedback.json"))
CDT_UTC_OFFSET_HOURS = 5
GPU_DESK_CHANNEL_ID = os.environ.get("DISCORD_GPU_DESK_CHANNEL_ID", "")
DEALS_COMMAND = re.compile(r"^!deals\s+(.+)$", re.I)
PUBLISH_TARGETS = {
    "/publish": ("DISCORD_DAILY_CHANNEL_ID", "DISCORD_SAGE_BOT_TOKEN", "[Sage daily update]"),
    "/publish/scout": (("DISCORD_SCOUT_RESEARCH_CHANNEL_ID", "DISCORD_SCOUT_Work_CHANNEL_ID"), "DISCORD_BOT_TOKEN_SCOUT", "[Scout research]"),
    "/publish/inspector": (("DISCORD_INSPECTOR_REVIEW_CHANNEL_ID", "DISCORD_INSPECTOR_Work_CHANNEL_ID"), "DISCORD_BOT_TOKEN_INSPECTOR", "[Inspector review]"),
}


def parse_time(value):
    match = re.fullmatch(r"(0?[1-9]|1[0-2])(?::([0-5][0-9]))?\s*(am|pm)", value)
    if match:
        hour = int(match.group(1)) % 12
        if match.group(3) == "pm":
            hour += 12
        return hour, int(match.group(2) or 0)
    match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", value)
    if match:
        return int(match.group(1)), int(match.group(2))
    raise ValueError("time must look like '9am', '9:30 pm', or '21:30'")


def cdt_to_utc(hour, minute):
    """Convert a CDT wall-clock time to the UTC-only Hermes scheduler."""
    total_minutes = hour * 60 + minute + CDT_UTC_OFFSET_HOURS * 60
    return (total_minutes // 60) % 24, total_minutes % 60, total_minutes // (24 * 60)


def format_time(hour, minute):
    return f"{hour:02d}:{minute:02d}"


def parse_schedule(text):
    value = " ".join(str(text).strip().lower().split())
    days = {"monday": "1", "tuesday": "2", "wednesday": "3", "thursday": "4", "friday": "5", "saturday": "6", "sunday": "0"}
    if match := re.fullmatch(r"every (\d{1,3}) minutes?", value):
        minutes = int(match.group(1))
        if 1 <= minutes <= 59:
            return {"cron": f"*/{minutes} * * * *", "description": f"every {minutes} minutes"}
    elif match := re.fullmatch(r"every (\d{1,2}) hours?", value):
        hours = int(match.group(1))
        if 1 <= hours <= 23:
            return {"cron": f"0 */{hours} * * *", "description": f"every {hours} hours"}
    elif match := re.fullmatch(r"daily at (.+)", value):
        hour, minute = parse_time(match.group(1))
        utc_hour, utc_minute, _ = cdt_to_utc(hour, minute)
        return {
            "cron": f"{utc_minute} {utc_hour} * * *",
            "description": f"daily at {format_time(hour, minute)} CDT ({format_time(utc_hour, utc_minute)} UTC)",
        }
    elif match := re.fullmatch(r"weekdays at (.+)", value):
        hour, minute = parse_time(match.group(1))
        utc_hour, utc_minute, day_offset = cdt_to_utc(hour, minute)
        utc_days = "1-5" if day_offset == 0 else "2-6"
        return {
            "cron": f"{utc_minute} {utc_hour} * * {utc_days}",
            "description": f"weekdays at {format_time(hour, minute)} CDT ({format_time(utc_hour, utc_minute)} UTC)",
        }
    elif match := re.fullmatch(r"weekly on (" + "|".join(days) + r") at (.+)", value):
        day, raw_time = match.groups()
        hour, minute = parse_time(raw_time)
        utc_hour, utc_minute, day_offset = cdt_to_utc(hour, minute)
        utc_day = (int(days[day]) + day_offset) % 7
        return {
            "cron": f"{utc_minute} {utc_hour} * * {utc_day}",
            "description": f"every {day} at {format_time(hour, minute)} CDT ({format_time(utc_hour, utc_minute)} UTC)",
        }
    elif match := re.fullmatch(r"monthly on day (\d{1,2}) at (.+)", value):
        day, raw_time = match.groups()
        if 1 <= int(day) <= 31:
            hour, minute = parse_time(raw_time)
            utc_hour, utc_minute, day_offset = cdt_to_utc(hour, minute)
            if day_offset:
                raise ValueError("monthly schedules after 6:59pm CDT cannot be converted safely; choose an earlier CDT time")
            return {
                "cron": f"{utc_minute} {utc_hour} {int(day)} * *",
                "description": f"monthly on day {day} at {format_time(hour, minute)} CDT ({format_time(utc_hour, utc_minute)} UTC)",
            }
    raise ValueError("supported schedules: every 15 minutes; every 2 hours; daily at 9am; weekdays at 17:30; weekly on monday at 9am; monthly on day 1 at 08:00 (all clock times are CDT)")


def load_requests():
    if not REQUESTS_PATH.exists():
        return []
    return json.loads(REQUESTS_PATH.read_text())


def save_requests(requests):
    REQUESTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = REQUESTS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(requests, indent=2))
    temporary.replace(REQUESTS_PATH)


def load_feedback():
    if not FEEDBACK_PATH.exists():
        return []
    try:
        return json.loads(FEEDBACK_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return []


def save_feedback(feedback):
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = FEEDBACK_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(feedback, indent=2))
    temporary.replace(FEEDBACK_PATH)


def write_review_feedback(event):
    """Persist one Discord feedback event to the shared Supabase ledger."""
    connection_string = os.environ.get("SUPABASE_EPISODE_WRITER_CONNECTION_STRING") or os.environ.get("SUPABASE_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("feedback writer is not configured")
    with psycopg.connect(connection_string) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.reviews_feedback
                    (event_key, guild_id, channel_id, thread_id, message_id,
                     parent_message_id, author_id, event_type, value, content,
                     metadata, occurred_at)
                values
                    (%(event_key)s, %(guild_id)s, %(channel_id)s, %(thread_id)s,
                     %(message_id)s, %(parent_message_id)s, %(author_id)s,
                     %(event_type)s, %(value)s, %(content)s, %(metadata)s::jsonb,
                     %(occurred_at)s)
                on conflict (event_key) do nothing
                """,
                {**event, "metadata": json.dumps(event.get("metadata", {}))},
            )


def record_feedback(message_id, channel_id, user_id, reaction):
    event = {
        "event_key": f"button:{message_id}:{user_id}:{reaction}",
        "guild_id": None,
        "channel_id": str(channel_id),
        "thread_id": None,
        "message_id": str(message_id),
        "parent_message_id": None,
        "author_id": str(user_id),
        "event_type": "button",
        "value": str(reaction),
        "content": None,
        "metadata": {"source": "discord_component"},
        "occurred_at": "now()",
    }
    # psycopg parameters cannot turn a string into SQL; use a real UTC value.
    event["occurred_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        write_review_feedback(event)
    except Exception as error:
        print(f"Supabase feedback write failed: {error}", flush=True)
    with FEEDBACK_LOCK:
        feedback = load_feedback()
        entry = {
            "message_id": str(message_id),
            "channel_id": str(channel_id),
            "user_id": str(user_id),
            "reaction": reaction,
            "recorded_at": int(time.time()),
        }
        if entry not in feedback:
            feedback.append(entry)
            save_feedback(feedback[-500:])


def record_reaction_feedback(payload):
    if payload.member and payload.member.bot:
        return
    emoji = str(payload.emoji)
    try:
        write_review_feedback({
            "event_key": f"reaction:{payload.message_id}:{payload.user_id}:{emoji}",
            "guild_id": str(payload.guild_id) if payload.guild_id else None,
            "channel_id": str(payload.channel_id),
            "thread_id": None,
            "message_id": str(payload.message_id),
            "parent_message_id": None,
            "author_id": str(payload.user_id),
            "event_type": "reaction",
            "value": emoji,
            "content": None,
            "metadata": {"source": "discord_reaction"},
            "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
    except Exception as error:
        print(f"Supabase reaction write failed: {error}", flush=True)


def record_reply_feedback(message):
    is_thread = isinstance(message.channel, discord.Thread)
    parent_message_id = message.reference.message_id if message.reference else None
    if not is_thread and parent_message_id is None:
        return
    try:
        write_review_feedback({
            "event_key": f"message:{message.id}",
            "guild_id": str(message.guild.id) if message.guild else None,
            "channel_id": str(message.channel.id),
            "thread_id": str(message.channel.id) if is_thread else None,
            "message_id": str(message.id),
            "parent_message_id": str(parent_message_id) if parent_message_id else None,
            "author_id": str(message.author.id),
            "event_type": "thread_reply" if is_thread else "reply",
            "value": None,
            "content": message.content[:2000] or None,
            "metadata": {"source": "discord_message"},
            "occurred_at": message.created_at.isoformat(),
        })
    except Exception as error:
        print(f"Supabase reply write failed: {error}", flush=True)


def sanitize_memory_text(value):
    """Keep reusable user context while excluding obvious credentials/secrets."""
    text = " ".join(str(value or "").split())[:1600]
    if not text or "#no-memory" in text.lower():
        return None
    if re.search(r"\b(api[ _-]?key|token|password|secret|postgres(?:ql)?://)\b", text, re.I):
        return None
    return text


def write_shared_memory(event):
    text = sanitize_memory_text(event.get("input_text"))
    if text is None:
        return False
    connection_string = os.environ.get("SUPABASE_EPISODE_WRITER_CONNECTION_STRING") or os.environ.get("SUPABASE_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("shared-memory writer is not configured")
    with psycopg.connect(connection_string) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.agent_shared_memory
                    (event_key, source_agent, guild_id, channel_id, message_id, author_id, input_text)
                values
                    (%(event_key)s, %(source_agent)s, %(guild_id)s, %(channel_id)s,
                     %(message_id)s, %(author_id)s, %(input_text)s)
                on conflict (event_key) do nothing
                """,
                {**event, "input_text": text},
            )
    return True


def record_discord_memory(message, source_agent):
    try:
        write_shared_memory({
            "event_key": f"discord:{message.id}",
            "source_agent": source_agent,
            "guild_id": str(message.guild.id) if message.guild else None,
            "channel_id": str(message.channel.id),
            "message_id": str(message.id),
            "author_id": str(message.author.id),
            "input_text": message.content,
        })
    except Exception as error:
        print(f"Shared memory write failed: {error}", flush=True)


def validate_request(payload):
    if payload.get("confirmed") is not True:
        raise ValueError("Brain may submit a request only after explicit user confirmation.")
    name = str(payload.get("name", "")).strip().lower()
    prompt = str(payload.get("prompt", "")).strip()
    timezone = str(payload.get("timezone", "")).strip().upper()
    if not JOB_NAME.fullmatch(name):
        raise ValueError("job name must be 3-64 lowercase letters, digits, or hyphens")
    if not 8 <= len(prompt) <= 1500:
        raise ValueError("task prompt must be between 8 and 1500 characters")
    if timezone != "CDT":
        raise ValueError("use timezone CDT; the broker converts CDT (UTC-5) to the UTC-only Hermes scheduler")
    return name, prompt, timezone, parse_schedule(payload.get("schedule", ""))


def queue_request(payload):
    """Validate and atomically enqueue one Brain-authorized Hermes job."""
    name, prompt, timezone, schedule = validate_request(payload)
    request = {
        "id": uuid4().hex,
        "status": "pending",
        "name": name,
        "prompt": prompt,
        "timezone": timezone,
        "schedule": schedule,
        "requested_by": str(payload.get("requested_by", "discord-user"))[:120],
        "workflow": str(payload.get("workflow", "general")),
    }
    with REQUEST_LOCK:
        requests = load_requests()
        if any(item["name"] == name and item["status"] in {"pending", "claimed", "created"} for item in requests):
            raise ValueError("an active cron request already uses this job name")
        requests.append(request)
        save_requests(requests)
    return request


def openrouter_turn(system, prompt):
    """Run one named Hermes specialist turn without exposing credentials to Discord."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("NemoHermes inference is not configured")
    body = json.dumps({
        "model": "nvidia/nemotron-3-super-120b-a12b",
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1200,
    }).encode()
    last_error = "no response"
    for attempt in range(3):
        connection = http.client.HTTPSConnection("openrouter.ai", timeout=75)
        try:
            connection.request("POST", "/api/v1/chat/completions", body=body, headers={
                "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
            })
            response = connection.getresponse()
            raw = response.read()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {}
            choices = payload.get("choices") if isinstance(payload, dict) else None
            if 200 <= response.status < 300 and isinstance(choices, list) and choices:
                content = choices[0].get("message", {}).get("content")
                if content:
                    return str(content).strip()
            provider_error = payload.get("error") if isinstance(payload, dict) else None
            last_error = str(provider_error or f"HTTP {response.status}; incomplete inference response")[:300]
            # Retrying provider/transient malformed responses is safe.  Do not
            # retry an explicit client configuration error.
            if 400 <= response.status < 500 and response.status != 429:
                break
        except (OSError, http.client.HTTPException) as error:
            last_error = str(error)[:300]
        finally:
            connection.close()
        if attempt < 2:
            time.sleep(1 + attempt)
    raise RuntimeError(f"NemoHermes inference is temporarily unavailable: {last_error}")


def tavily_research(query, limit=5):
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("Tavily research is not configured")
    body = json.dumps({"api_key": api_key, "query": query, "max_results": max(1, min(int(limit), 5)), "search_depth": "basic"}).encode()
    connection = http.client.HTTPSConnection("api.tavily.com", timeout=45)
    try:
        connection.request("POST", "/search", body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        payload = json.loads(response.read())
        if not 200 <= response.status < 300:
            raise RuntimeError(f"research request failed ({response.status})")
        return [{"title": item.get("title"), "url": item.get("url"), "content": item.get("content", "")[:700]} for item in payload.get("results", [])]
    finally:
        connection.close()


def database_candidates(question, limit=5):
    """Return recent marketplace listings matching the user's item request.

    The database is the first source of truth.  A deliberately small, escaped
    keyword query keeps the Discord path read-only and bounded.
    """
    keywords = []
    for word in re.findall(r"[a-z0-9][a-z0-9+.-]{1,30}", question.lower()):
        if word not in keywords and word not in {"find", "need", "want", "please", "best", "deal", "deals", "price", "prices", "for", "with"}:
            keywords.append(word)
        if len(keywords) == 4:
            break
    if not keywords:
        return []
    clauses = " OR ".join(
        "lower(coalesce(l.title, '') || ' ' || coalesce(p.canonical_name, '')) like "
        + "'%" + word.replace("'", "''") + "%'"
        for word in keywords
    )
    sql = f"""
        select l.title, l.url, l.condition, l.currency, l.item_price, l.shipping_price,
               l.total_price, l.availability, l.fulfillment, l.seller_name,
               l.seller_rating, l.location, l.last_seen_at,
               s.name as source_name, s.base_url as source_base_url,
               p.canonical_name, p.brand, p.model, p.category
        from public.listings l
        left join public.products p on p.id = l.product_id
        left join public.sources s on s.id = l.source_id
        where {clauses}
        order by l.last_seen_at desc nulls last, l.total_price asc nulls last
        limit {max(1, min(int(limit), 5))}
    """
    try:
        rows = read_query(sql)
    except Exception:
        # A temporary database failure must not prevent a user from receiving
        # a researched answer; Scout will disclose that it had no DB matches.
        return []
    return [{"origin": "linked database", **row} for row in rows]


def research_pipeline(question):
    """Use database matches first; Scout web-searches only the missing slots."""
    database_rows = database_candidates(question, 5)
    web_slots = max(0, 5 - len(database_rows))
    web_sources = tavily_research(question, web_slots) if web_slots else []
    feedback_summary = recent_feedback_context()
    memory_summary = shared_memory_context()
    scout = openrouter_turn(
        "You are Scout, NemoHermes's private product-research subagent. Start with the supplied linked-database listings. "
        "They are the preferred candidates. Web evidence is supplied only to fill any missing slots. Select the five most appropriate, distinct candidates where evidence supports them, retaining database candidates when appropriate. "
        "Return concise candidate facts with exact URLs, price/stock evidence, fulfillment type, and official local-stock URLs when present. Do not recommend a purchase or invent missing facts.",
        f"USER QUESTION:\n{question}\n\nSHARED RECENT USER CONTEXT:\n{json.dumps(memory_summary, default=str)}"
        f"\n\nRECENT AGGREGATED USER FEEDBACK:\n{json.dumps(feedback_summary, default=str)}"
        f"\n\nLINKED DATABASE CANDIDATES ({len(database_rows)}):\n{json.dumps(database_rows, default=str)}"
        f"\n\nWEB FILLER EVIDENCE ({len(web_sources)}):\n{json.dumps(web_sources)}",
    )
    inspector = openrouter_turn(
        "You are Inspector, NemoHermes's private review subagent. Review only Scout's evidence; do not browse or add offers. "
        "Flag untrusted, indirect, stale, contradictory, duplicate, or unsupported links. Verify that linked-database candidates were considered before web filler and state which five or fewer candidates are safe to present.",
        f"USER QUESTION:\n{question}\n\nSHARED RECENT USER CONTEXT:\n{json.dumps(memory_summary, default=str)}"
        f"\n\nRECENT AGGREGATED USER FEEDBACK:\n{json.dumps(feedback_summary, default=str)}\n\nSCOUT EVIDENCE:\n{scout}",
    )
    return openrouter_turn(
        "You are NemoHermes, the sole user-facing Discord assistant. Use Scout and Inspector below; do not mention internal agents. "
        "Return exactly five appropriate, distinct options when the evidence supports five; otherwise state why fewer verified options are available. Prefer appropriate linked-database entries, then use web results only to fill the remainder. "
        "Keep the complete response below 1,700 characters. Each option must be labelled **Online** or **In-store / pickup**. Online options need a trusted direct clickable URL. "
        "In-store options need a location (or selected-store caveat) plus a trusted official stock-check/store-locator URL. State unavailable or unverified stock plainly. "
        "Do not include run IDs, raw research, or tool traces.",
        f"USER QUESTION:\n{question}\n\nSCOUT:\n{scout}\n\nINSPECTOR:\n{inspector}",
    )


def read_query(sql):
    statement = sql.strip().rstrip(";").strip()
    if not statement.lower().startswith(("select ", "with ")) or ";" in statement or FORBIDDEN.search(statement):
        raise ValueError("Only SELECT queries to shared marketplace tables are allowed.")
    with psycopg.connect(os.environ["SUPABASE_AGENT_READONLY_CONNECTION_STRING"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '10s'")
            cursor.execute(statement)
            columns = [column.name for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchmany(MAX_ROWS)]


def recent_feedback_context():
    """Provide a compact, privacy-minimised feedback snapshot to all agents."""
    try:
        return read_query("""
            select event_type, value, count(*) as count, max(occurred_at) as latest_at
            from public.reviews_feedback
            where occurred_at > now() - interval '30 days'
            group by event_type, value
            order by latest_at desc
            limit 30
        """)
    except Exception:
        return []


def shared_memory_context():
    """Recent canonical user inputs, shared by NemoHermes and NemoClaw."""
    try:
        return read_query("""
            select source_agent, input_text, created_at
            from public.agent_shared_memory
            order by created_at desc
            limit 12
        """)
    except Exception:
        return []


def validate_episode(payload):
    """Validate the only write Hermes is permitted to request."""
    episode_id = str(payload.get("episode_id") or f"hermes-{uuid4().hex}").strip().lower()
    task_type = str(payload.get("task_type", "shopping_research")).strip().lower()
    request = str(payload.get("request", "")).strip()
    outcome = str(payload.get("outcome", "")).strip()
    lesson = str(payload.get("lesson", "")).strip()
    quality = str(payload.get("quality", "neutral")).strip().lower()
    episode_date = str(payload.get("episode_date", "")).strip() or None
    agent_chain = payload.get("agent_chain", ["hermes"])
    feedback = payload.get("feedback", {})

    if not EPISODE_ID.fullmatch(episode_id):
        raise ValueError("episode_id must be 3-128 lowercase letters, digits, dots, underscores, or hyphens")
    if task_type not in EPISODE_TASK_TYPES:
        raise ValueError("unsupported episode task_type")
    if quality not in {"good", "bad", "neutral"}:
        raise ValueError("quality must be good, bad, or neutral")
    if not 8 <= len(request) <= 800 or not 8 <= len(outcome) <= 1200:
        raise ValueError("episode request and outcome must be concise summaries")
    if len(lesson) > 600:
        raise ValueError("episode lesson must be at most 600 characters")
    if not isinstance(agent_chain, list) or not 1 <= len(agent_chain) <= 8:
        raise ValueError("agent_chain must contain 1-8 agent names")
    if not all(re.fullmatch(r"[a-z0-9_-]{1,40}", str(agent)) for agent in agent_chain):
        raise ValueError("agent_chain contains an invalid agent name")
    if not isinstance(feedback, dict) or len(json.dumps(feedback)) > 1000:
        raise ValueError("feedback must be a small JSON object")
    summary = " ".join([request, outcome, lesson]).lower()
    if re.search(r"\b(api[ _-]?key|token|password|connection string|postgres(?:ql)?://)\b", summary):
        raise ValueError("episodes must not contain credentials or connection details")
    return {
        "episode_id": episode_id,
        "episode_date": episode_date,
        "channel": "discord",
        "task_type": task_type,
        "request": request,
        "agent_chain": [str(agent) for agent in agent_chain],
        "outcome": outcome,
        "feedback": feedback,
        "quality": quality,
        "lesson": lesson or None,
    }


def write_episode(episode):
    """Write one bounded learning episode through the proxy's trusted connection."""
    connection_string = os.environ.get("SUPABASE_EPISODE_WRITER_CONNECTION_STRING") or os.environ.get("SUPABASE_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("episode writer is not configured")
    with psycopg.connect(connection_string) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into public.episodes
                    (episode_id, episode_date, channel, task_type, request, agent_chain, outcome, feedback, quality, lesson)
                values
                    (%(episode_id)s, %(episode_date)s::date, %(channel)s, %(task_type)s, %(request)s,
                     %(agent_chain)s::jsonb, %(outcome)s, %(feedback)s::jsonb, %(quality)s, %(lesson)s)
                on conflict (episode_id) do nothing
                """,
                {**episode, "agent_chain": json.dumps(episode["agent_chain"]), "feedback": json.dumps(episode["feedback"])},
            )
            return cursor.rowcount == 1


def discord_bot_user_id(token):
    """Return a bot's Discord user ID without logging its credential."""
    connection = http.client.HTTPSConnection("discord.com", timeout=15)
    try:
        connection.request(
            "GET",
            "/api/v10/users/@me",
            headers={"Authorization": f"Bot {token}"},
        )
        response = connection.getresponse()
        payload = response.read()
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Discord identity lookup failed ({response.status})")
        return int(json.loads(payload)["id"])
    finally:
        connection.close()


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, response):
        body = json.dumps(response, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/cron-requests/next":
            with REQUEST_LOCK:
                requests = load_requests()
                request = next((item for item in requests if item["status"] == "pending"), None)
                if request is None:
                    self.reply(204, {})
                    return
                request["status"] = "claimed"
                request["claim_token"] = uuid4().hex
                save_requests(requests)
            self.reply(200, request)
            return
        if self.path == "/feedback/recent":
            with FEEDBACK_LOCK:
                feedback = load_feedback()[-50:]
            self.reply(200, {"feedback": feedback})
            return
        if self.path == "/memory/recent":
            self.reply(200, {"memory": shared_memory_context()})
            return
        self.send_error(404)

    def do_POST(self):
        if self.path not in {"/query", "/episodes", "/memory/events", "/cron-parse", "/cron-requests", *PUBLISH_TARGETS} and not re.fullmatch(r"/cron-requests/[0-9a-f]+/complete", self.path):
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size))
            if self.path == "/query":
                result = read_query(payload["sql"])
                response = {"rows": result}
            elif self.path == "/episodes":
                episode = validate_episode(payload)
                response = {"stored": write_episode(episode), "episode_id": episode["episode_id"]}
            elif self.path == "/memory/events":
                source_agent = str(payload.get("source_agent", "")).strip().lower()
                if source_agent not in {"nemohermes", "nemoclaw", "sage"}:
                    raise ValueError("source_agent must be nemohermes, nemoclaw, or sage")
                event_key = str(payload.get("event_key", "")).strip()
                if not 6 <= len(event_key) <= 200:
                    raise ValueError("memory event_key must be 6-200 characters")
                response = {"stored": write_shared_memory({
                    "event_key": event_key,
                    "source_agent": source_agent,
                    "guild_id": str(payload.get("guild_id") or "") or None,
                    "channel_id": str(payload.get("channel_id") or "") or None,
                    "message_id": str(payload.get("message_id") or "") or None,
                    "author_id": str(payload.get("author_id") or "") or None,
                    "input_text": payload.get("input_text", ""),
                })}
            elif self.path == "/cron-parse":
                response = parse_schedule(payload.get("schedule", ""))
            elif self.path == "/cron-requests":
                request = queue_request(payload)
                schedule = request["schedule"]
                response = {"queued": True, "id": request["id"], **schedule}
            elif self.path.endswith("/complete"):
                request_id = self.path.split("/")[2]
                with REQUEST_LOCK:
                    requests = load_requests()
                    request = next((item for item in requests if item["id"] == request_id), None)
                    if request is None or request["status"] != "claimed" or payload.get("claim_token") != request.get("claim_token"):
                        raise ValueError("invalid or expired cron request claim")
                    request["status"] = "created" if payload.get("success") else "failed"
                    request["result"] = str(payload.get("result", ""))[:1000]
                    request.pop("claim_token", None)
                    save_requests(requests)
                response = {"updated": True}
            elif self.path in PUBLISH_TARGETS:
                content = str(payload.get("content", "")).strip()
                if not content:
                    raise ValueError("A cron-output message is required.")
                content = content[:1900]
                channel_key, token_key, prefix = PUBLISH_TARGETS[self.path]
                channel_keys = (channel_key,) if isinstance(channel_key, str) else channel_key
                channel_id = next((os.environ.get(key) for key in channel_keys if os.environ.get(key)), None)
                bot_token = os.environ.get(token_key)
                if not channel_id or not bot_token:
                    raise ValueError(f"{self.path} is not configured; set one of {', '.join(channel_keys)} and {token_key}")
                discord_connection = http.client.HTTPSConnection("discord.com", timeout=15)
                discord_connection.request(
                    "POST",
                    f"/api/v10/channels/{channel_id}/messages",
                    body=json.dumps({"content": f"{prefix}\n{content}"}),
                    headers={"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"},
                )
                discord_response = discord_connection.getresponse()
                if not 200 <= discord_response.status < 300:
                    raise RuntimeError(f"Discord rejected the post ({discord_response.status})")
                discord_response.read()
                discord_connection.close()
                response = {"published": True}
            self.reply(200, response)
        except Exception as error:
            self.reply(400, {"error": str(error)})

    def log_message(self, *_):
        pass


class FeedbackView(discord.ui.View):
    """Persistent feedback controls that survive coordinator restarts."""

    def __init__(self):
        super().__init__(timeout=None)
        # Stable IDs let discord.py register this view again after a restart.
        self.children[0].custom_id = "nemohermes:feedback:helpful"
        self.children[1].custom_id = "nemohermes:feedback:not-helpful"

    async def _record(self, interaction, reaction):
        # Acknowledge first: Discord otherwise declares a component interaction
        # failed after three seconds, even when a background write is healthy.
        await interaction.response.send_message(
            "Thanks — NemoHermes will use this feedback for future recommendations.",
            ephemeral=True,
        )
        asyncio.create_task(asyncio.to_thread(
            record_feedback,
            interaction.message.id if interaction.message else "unknown",
            interaction.channel_id,
            interaction.user.id,
            reaction,
        ))
        return
        record_feedback(self.source_message_id, interaction.channel_id, interaction.user.id, reaction)
        await interaction.response.send_message("Thanks — NemoHermes will use this feedback for future recommendations.", ephemeral=True)

    @discord.ui.button(label="Helpful", style=discord.ButtonStyle.success, emoji="👍")
    async def helpful(self, interaction, _button):
        await self._record(interaction, "👍")

    @discord.ui.button(label="Not helpful", style=discord.ButtonStyle.secondary, emoji="👎")
    async def not_helpful(self, interaction, _button):
        await self._record(interaction, "👎")


class CronConfirmationView(discord.ui.View):
    """Require the requesting Discord user to approve a parsed cron schedule."""

    def __init__(self, schedule, requester_id):
        super().__init__(timeout=900)
        self.schedule = schedule
        self.requester_id = requester_id

    async def _require_requester(self, interaction):
        if interaction.user.id == self.requester_id:
            return True
        await interaction.response.send_message("Only the user who requested this schedule can confirm it.", ephemeral=True)
        return False

    @discord.ui.button(label="Confirm cron", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction, _button):
        if not await self._require_requester(interaction):
            return
        try:
            request = queue_request({
                "confirmed": True,
                "name": "daily-deals",
                "schedule": self.schedule,
                "timezone": "CDT",
                "requested_by": str(interaction.user.id),
                "workflow": "daily-deals",
                "prompt": (
                    "Run the daily-deals workflow. Scout researches current offers, Inspector reviews "
                    "Scout's evidence, and Sage publishes a concise linked #daily digest. Label every "
                    "recommendation Online or In-store / pickup; use verified direct links and official "
                    "stock-check/store-locator links for in-store options. Never include internal IDs."
                ),
            })
            await interaction.response.edit_message(
                content="NemoHermes queued the daily-deals job. Hermes will create it and Sage will publish the result in #daily.",
                view=None,
            )
        except Exception as error:
            await interaction.response.send_message(f"NemoHermes could not queue this cron: {error}", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, _button):
        if not await self._require_requester(interaction):
            return
        await interaction.response.edit_message(content="NemoHermes cancelled this cron request.", view=None)


class NemoHermesClient(discord.Client):
    """Discord-facing coordinator when sandbox Discord egress is unavailable."""

    async def setup_hook(self):
        self.add_view(FeedbackView())

    async def on_ready(self):
        print(f"NemoHermes coordinator connected as {self.user}; gpu_desk={GPU_DESK_CHANNEL_ID}", flush=True)

    async def on_message(self, message):
        if message.author.bot or str(message.channel.id) != GPU_DESK_CHANNEL_ID:
            return
        content = message.content.strip()
        if not content:
            return
        # The Discord message ID is the canonical cross-bot memory key.  If
        # NemoClaw sees the same message later, its insert is a no-op.
        await asyncio.to_thread(record_discord_memory, message, "nemohermes")
        match = DEALS_COMMAND.fullmatch(content)
        if match:
            try:
                parsed = parse_schedule(match.group(1))
                await message.reply(
                    f"I parsed **{parsed['description']}** (`{parsed['cron']}`). Sage will publish the completed linked digest in #daily. Confirm before I activate it.",
                    view=CronConfirmationView(match.group(1), message.author.id),
                    mention_author=False,
                )
            except Exception as error:
                await message.reply(f"I could not parse that schedule: {error}", mention_author=False)
            return
        try:
            async with message.channel.typing():
                answer = await asyncio.to_thread(research_pipeline, content)
            await message.reply(answer[:1800], view=FeedbackView(), mention_author=False)
        except Exception as error:
            await message.reply(f"I could not complete the Scout and Inspector review: {error}", mention_author=False)


class SageClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hermes_user_id = None
        self.hermes_message_ids = set()

    async def setup_hook(self):
        self.add_view(FeedbackView())

    async def refresh_feedback_controls(self):
        """Replace legacy non-persistent Sage feedback buttons once."""
        channel_ids = {GPU_DESK_CHANNEL_ID, os.environ.get("DISCORD_DAILY_CHANNEL_ID", "")}
        for channel_id in filter(None, channel_ids):
            try:
                channel = await self.fetch_channel(int(channel_id))
                async for message in channel.history(limit=100):
                    if message.author.id == self.user.id and message.content == "Was this recommendation helpful?":
                        await message.edit(view=FeedbackView())
            except (discord.Forbidden, discord.HTTPException):
                # The new controls remain active even if historic messages
                # cannot be edited due to channel history permissions.
                continue

    async def on_ready(self):
        print(f"Sage connected as {self.user}; guild_count={len(self.guilds)}", flush=True)
        await self.refresh_feedback_controls()
        hermes_token = os.environ.get("DISCORD_NEMOHERMES_BOT_TOKEN")
        if hermes_token:
            try:
                self.hermes_user_id = discord_bot_user_id(hermes_token)
                print("Sage feedback: Hermes reactions enabled", flush=True)
            except Exception as error:
                print(f"Sage feedback: Hermes reaction setup failed: {error}", flush=True)
        else:
            print("Sage feedback: Hermes token unavailable; reactions disabled", flush=True)
        channel_id = int(os.environ["DISCORD_DAILY_CHANNEL_ID"])
        for guild in self.guilds:
            member = guild.me
            channel = guild.get_channel(channel_id)
            if member is None:
                print(f"Sage diagnostics: guild={guild.id}; member cache unavailable", flush=True)
            elif channel is None:
                print(f"Sage diagnostics: guild={guild.id}; daily channel not visible to Sage", flush=True)
            else:
                permissions = channel.permissions_for(member)
                print(
                    f"Sage diagnostics: daily_view={permissions.view_channel}; "
                    f"daily_send={permissions.send_messages}; roles={[role.name for role in member.roles]}",
                    flush=True,
                )

    async def on_message(self, message):
        """Capture human reply/thread feedback; NemoHermes owns one feedback UI."""
        if not message.author.bot:
            await asyncio.to_thread(record_reply_feedback, message)
        return
        """Attach feedback controls to fresh Hermes Discord replies."""
        if message.author.id != self.hermes_user_id:
            return
        try:
            await message.add_reaction("👍")
            await message.add_reaction("👎")
            self.hermes_message_ids.add(message.id)
            await message.reply("Was this recommendation helpful?", view=FeedbackView(), mention_author=False)
        except discord.Forbidden:
            print("Sage feedback: missing Add Reactions permission", flush=True)
        except discord.HTTPException as error:
            print(f"Sage feedback: could not add reactions: {error}", flush=True)

    async def on_raw_reaction_add(self, payload):
        if (self.user and payload.user_id == self.user.id) or (payload.member and payload.member.bot):
            return
        await asyncio.to_thread(record_reaction_feedback, payload)
        return
        if payload.message_id not in self.hermes_message_ids:
            return
        if self.user and payload.user_id == self.user.id:
            return
        if payload.member and payload.member.bot:
            return
        reaction = str(payload.emoji)
        if reaction in {"👍", "👎"}:
            record_feedback(payload.message_id, payload.channel_id, payload.user_id, reaction)


def run_sage_gateway():
    intents = discord.Intents.default()
    intents.message_content = True
    SageClient(intents=intents).run(
        os.environ["DISCORD_SAGE_BOT_TOKEN"], log_handler=None
    )


def run_nemohermes_gateway():
    if not GPU_DESK_CHANNEL_ID or not os.environ.get("DISCORD_NEMOHERMES_BOT_TOKEN"):
        print("NemoHermes coordinator disabled: Discord channel or token is not configured", flush=True)
        return
    intents = discord.Intents.default()
    intents.message_content = True
    NemoHermesClient(intents=intents).run(os.environ["DISCORD_NEMOHERMES_BOT_TOKEN"], log_handler=None)


threading.Thread(target=run_sage_gateway, daemon=True).start()
threading.Thread(target=run_nemohermes_gateway, daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", 8001), Handler).serve_forever()
