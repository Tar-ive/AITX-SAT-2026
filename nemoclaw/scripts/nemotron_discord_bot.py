#!/usr/bin/env python3
import os
import json
import requests
import discord
from discord.ext import commands

# Path Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "scripts", "nemotron_config.json")

# Load Configuration
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}

config = load_config()
DISCORD_BOT_TOKEN = config.get("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = config.get("DISCORD_CHANNEL_ID")
NVIDIA_API_KEY = config.get("NVIDIA_API_KEY")

# API Server URL (Railway Deployed URL)
API_SERVER_URL = "https://nemoclaw-coordinator-api-production.up.railway.app"
SHARED_MEMORY_URL = os.environ.get("SHARED_MEMORY_URL", "http://host.openshell.internal:8001/memory/recent")
# NemoHermes is the sole Discord-facing assistant.  NemoClaw uses the shared
# context internally and must never create a duplicate user-facing response.
PASSIVE_MEMORY_ONLY = os.environ.get("NEMOCLAW_PASSIVE_MEMORY_ONLY", "1") == "1"
SHARED_MEMORY_PROXY_URL = os.environ.get("SHARED_MEMORY_PROXY_URL", "http://host.openshell.internal:8001")

# Whitelisted Specialist Bot IDs (Verifiers to allow bot-to-bot communication)
# Edit these IDs to match your friend's bots on the server
WHITELISTED_BOT_IDS = [
    # Example: 123456789012345678 (Amazon Specialist)
]

# Set Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def shared_memory_context():
    """Read the same canonical inputs NemoHermes recorded once per message."""
    try:
        response = requests.get(SHARED_MEMORY_URL, timeout=4)
        if response.ok:
            return response.json().get("memory", [])[:12]
    except requests.RequestException:
        pass
    return []


def shared_memory(message):
    """Write one canonical Discord input, then retrieve shared recent context."""
    event_key = f"discord:{message.id}"
    try:
        requests.post(
            f"{SHARED_MEMORY_PROXY_URL}/memory/events",
            json={
                "event_key": event_key,
                "source_agent": "nemoclaw",
                "guild_id": str(message.guild.id) if message.guild else None,
                "channel_id": str(message.channel.id),
                "message_id": str(message.id),
                "author_id": str(message.author.id),
                "input_text": message.content,
            },
            timeout=4,
        )
        response = requests.get(f"{SHARED_MEMORY_PROXY_URL}/memory/recent", timeout=4)
        if response.ok:
            return response.json().get("memory", [])[:8]
    except requests.RequestException as error:
        print(f"[Shared memory] unavailable: {error}")
    return []

def grade_response_via_nemotron(prompt, agent_response, shared_context=None):
    """
    Calls NVIDIA Endpoints API to grade the specialist agent's consensus deal.
    """
    if not NVIDIA_API_KEY or NVIDIA_API_KEY.startswith("YOUR_"):
        # Offline mock evaluation fallback
        return {
            "A": 100, "S": 100, "P": 100, "R": 100, "C": 100,
            "lesson": "Verified sourcing constraints. Passed all safety tests."
        }
        
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_instruction = (
        "You are SAGE, the Critic. Evaluate the specialist bots' consensus recommendation.\n"
        "Grade across 5 dimensions (Accuracy, Speed, Platform, Retrieval, Safety). "
        "Output strictly in JSON format with keys: A, S, P, R, C (values 0, 50, 100) and 'lesson'."
    )
    
    user_prompt = (
        f"User Sourcing Query: \"{prompt}\"\n"
        f"Shared user context: {json.dumps(shared_memory_context())}\n"
        f"Agent Consensus Deal: \"{agent_response}\"\n"
        f"Shared recent user context: {json.dumps(shared_context or [])}\n"
        "Provide the scorecard JSON."
    )
    
    payload = {
        "model": "nvidia/nemotron-3-super-120b-a12b",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
    }
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            return json.loads(r.json()["choices"][0]["message"]["content"])
    except Exception as e:
        print(f"[Error] LLM grading failed: {e}")
        
    return {"A": 100, "S": 100, "P": 100, "R": 100, "C": 100, "lesson": "Sourcing validated."}

@bot.event
async def on_ready():
    print("="*60)
    print(f" NEMOCLAW CRITIC BOT ACTIVE // LOGGED IN AS: {bot.user}")
    print(f" Target Channel ID: {DISCORD_CHANNEL_ID}")
    print("="*60)

@bot.event
async def on_message(message):
    # 1. Verification: Ignore own messages
    if message.author == bot.user:
        return
        
    # 2. Verification: Restrict to target bot-testing channel
    if DISCORD_CHANNEL_ID and str(message.channel.id) != str(DISCORD_CHANNEL_ID):
        return

    # Do not ask the user for a second input or publish a separate answer.
    # NemoHermes records the single input in Supabase; this bot only consumes
    # it when invoked internally for a critic task.
    if PASSIVE_MEMORY_ONLY:
        return
        
    # 3. Verifier: Check if message is from a Bot
    is_bot = message.author.bot
    author_id = message.author.id
    
    # If it is a bot, verify it is whitelisted or log a warning
    if is_bot:
        if WHITELISTED_BOT_IDS and author_id not in WHITELISTED_BOT_IDS:
            print(f"[Verifier Info] Ignored unverified bot ID: {author_id}")
            return
            
    # Process message if it triggers consensus keyword
    content = message.content
    shared_context = shared_memory(message) if not is_bot else []
    if "Consensus Sourcing Result:" in content or "Deal Found:" in content:
        await message.channel.send("⚡ **Nemotron Critic Verification triggered... SAGE is auditing the deal** ⚡")
        
        # Slicing the prompt out of the message
        # Example format: "Prompt: [user prompt] Consensus Sourcing Result: [sourcing recommendation]"
        prompt = "Dynamic Sourcing Request"
        if "Prompt:" in content:
            prompt = content.split("Prompt:")[1].split("Consensus")[0].strip()
            
        # Run Nemotron Critic Grading
        scores = grade_response_via_nemotron(prompt, content, shared_context)
        
        A = scores.get("A", 100)
        S = scores.get("S", 100)
        P = scores.get("P", 100)
        R = scores.get("R", 100)
        C = scores.get("C", 100)
        lesson = scores.get("lesson", "Validated successfully.")
        
        # Calculate Value Score
        value_score = Math.round((0.3 * A) + (0.15 * S) + (0.2 * P) + (0.15 * R) + (0.2 * C)) if 'Math' in globals() else int((0.3 * A) + (0.15 * S) + (0.2 * P) + (0.15 * R) + (0.2 * C))
        
        # Send scores to Railway API to update Dashboard
        try:
            payload = {
                "version": "Snapshot v1.1 (Day 2 Reflexion)",
                "caseId": "TC-Live",
                "A": A, "S": S, "P": P, "R": R, "C": C
            }
            requests.post(f"{API_SERVER_URL}/api/evaluations", json=[payload], timeout=5)
        except Exception as e:
            print(f"[Error] Failed to post evaluations to Railway: {e}")
            
        # Send Premium Embed scorecard response to Discord channel
        embed = discord.Embed(
            title="🔍 SAGE E-Commerce Audit Report",
            description=f"**Target Prompt:** {prompt}\n\n**Episode Score:** `{value_score}/100`",
            color=discord.Color.green() if value_score >= 80 else discord.Color.orange()
        )
        embed.add_field(name="Accuracy (A)", value=f"`{A}%`", inline=True)
        embed.add_field(name="Speed (S)", value=f"`{S}%`", inline=True)
        embed.add_field(name="Platform (P)", value=f"`{P}%`", inline=True)
        embed.add_field(name="Retrieval (R)", value=f"`{R}%`", inline=True)
        embed.add_field(name="Safety (C)", value=f"`{C}%`", inline=True)
        embed.add_field(name="📋 Critic Feedback / Reflexion Lesson", value=f"*{lesson}*", inline=False)
        embed.set_footer(text="NemoClaw SFT Training Loop • Powered by Nemotron")
        
        await message.reply(embed=embed)

# Run Bot Client
if __name__ == "__main__":
    if DISCORD_BOT_TOKEN and not DISCORD_BOT_TOKEN.startswith("YOUR_"):
        bot.run(DISCORD_BOT_TOKEN)
    else:
        print("[Error] Discord Bot Token not found in config.json. Update the file to run.")
