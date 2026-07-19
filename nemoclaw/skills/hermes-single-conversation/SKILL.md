---
name: single-conversation-owner
description: Keep a Discord job with Hermes from start to finish while using other agents only internally.
---

# One user, one agent conversation

For any job that Hermes accepts in Discord:

1. Hermes gathers requirements and asks follow-up questions directly in the
   same Discord conversation.
2. Hermes may use database queries, Tavily, skills, scripts, or internal
   subagents, but their work stays private.
3. Hermes provides the final audit card, recommendation, progress update, or
   clarification itself. No other bot should ask the user for a response or
   post a competing final answer for that job.
4. Preserve continuity: refer to earlier requirements, feedback reactions, and
   constraints from the same conversation rather than making the user repeat
   them to another bot.

Keep all research and delegation private. Do not post progress or intermediate
messages in the user's channel; show only Hermes' completed final response.

Sage is limited to adding feedback reactions and recording aggregate feedback;
it is not a conversational participant.
