#!/usr/bin/env python3
"""Claim one Brain-approved request and create it through Hermes only."""

import json
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = "http://host.openshell.internal:8001"
HERMES = "/opt/hermes/.venv/bin/hermes"
SCRIPTS = Path("/sandbox/.hermes/scripts")


def post(path, payload):
    request = Request(
        f"{BASE_URL}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST"
    )
    return urlopen(request, timeout=20).read().decode()


def write_pipeline_script(name, task, request_id):
    """Create one safe, job-specific Scout -> Inspector handoff script."""
    path = SCRIPTS / f"cron_pipeline_{name}.py"
    script = f'''#!/usr/bin/env python3
import json
import subprocess

REQUEST_ID = {request_id!r}
TASK = {task!r}


def run_subagent(role, prompt):
    result = subprocess.run(
        ["/opt/hermes/.venv/bin/hermes", "-z", prompt],
        capture_output=True, text=True, timeout=180,
    )
    output = (result.stdout or result.stderr).strip()
    if result.returncode:
        raise RuntimeError(f"{{role}} failed: {{output[:500]}}")
    return output


scout_research = run_subagent(
    "Scout",
    "You are Scout, Hermes's dedicated cron research subagent. Research the following "
    "task yourself using the tavily-search skill whenever current or web evidence "
    "is needed. Return a concise evidence brief with source URLs, dates when "
    "relevant, uncertainties, and no final recommendation.\\n\\nTASK: " + TASK,
)
inspector_review = run_subagent(
    "Inspector",
    "You are Inspector, Hermes's dedicated cron review subagent. Independently judge "
    "the Scout evidence below for relevance, source quality, contradictions, "
    "missing information, and the appropriate confidence level. Do not research "
    "or write the final user-facing answer. Your scope is the Scout evidence only; "
    "do not browse or introduce new listings.\\n\\nTASK: " + TASK + "\\n\\nSCOUT EVIDENCE:\\n" + scout_research,
)
print(json.dumps({{
    "schema_version": 1,
    "request_id": REQUEST_ID,
    "task": TASK,
    "handoff": {{
        "scout": {{"role": "research", "evidence": scout_research}},
        "inspector": {{"role": "review", "judgment": inspector_review}},
    }},
}}))
'''
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    path.write_text(script)
    path.chmod(0o700)
    return path


try:
    try:
        response = urlopen(f"{BASE_URL}/cron-requests/next", timeout=20)
    except HTTPError as error:
        if error.code == 204:
            raise SystemExit(0)
        raise
    if response.status == 204:
        raise SystemExit(0)
    request_data = json.loads(response.read())
    pipeline_script = write_pipeline_script(request_data["name"], request_data["prompt"], request_data["id"])
    daily_deals = request_data.get("workflow") == "daily-deals"
    output_contract = (
        "For the final Sage delivery, use the heading `**Daily deals**` followed by at most "
        "three Markdown bullets. Every bullet must include a verified clickable product URL, "
        "price, store, and online/offline category. Do not include a run ID, job ID, raw traces, "
        "or an unlinked recommendation."
        if daily_deals else
        "Publish a concise final report with source URLs and no raw tool traces."
    )
    prompt = (
        "You are Hermes, the cron orchestrator. Execute the attached Scout-to-Inspector "
        "script first. Its JSON handoff is the only research input you may use: Scout owns "
        "Tavily-backed research and source URLs; Inspector owns quality review, contradiction "
        "checks, and confidence. Do not research again, invent listings, or override Inspector. "
        "Synthesize only their handoff into the final conclusion.\n\n"
        "Scout must check the read-only Supabase data before a single Tavily fallback of at "
        "most five sites. "
        "Use the attached scout-inspector-publisher skill to publish Scout's research "
        "through the Scout Discord bot and Inspector's review through the Inspector bot. "
        "Then use sage-cron-publisher to publish the final report to #daily through Sage. "
        + output_contract + " "
        "Do not send a direct Discord reply."
    )
    command = [
        HERMES, "cron", "create", request_data["schedule"]["cron"], prompt,
        "--name", request_data["name"], "--script", str(pipeline_script),
        "--skill", "database-first-research", "--skill", "scout-inspector-publisher",
        "--skill", "sage-cron-publisher",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=45)
    details = (result.stdout or result.stderr).strip()
    post(
        f"/cron-requests/{request_data['id']}/complete",
        {"claim_token": request_data["claim_token"], "success": result.returncode == 0, "result": details},
    )
except Exception as error:
    print(f"cron dispatcher error: {error}")
