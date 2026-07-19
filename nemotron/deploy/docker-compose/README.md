# Deploying the GPU-buying agent team

Single-host Docker Compose deployment, adapted from
[NVIDIA/nemoclaw-community `examples/retail-assistant`](https://github.com/NVIDIA/nemoclaw-community/tree/main/examples/retail-assistant)
(Apache-2.0), simplified for this project: hosted **NVIDIA Endpoints** instead
of local vLLM, **Discord** instead of Telegram, no database tier.

## What it deploys

One `workspace` container (host network, Docker socket mounted) that:
1. installs NemoClaw non-interactively,
2. onboards the `openclaw` sandbox with the **scout / inspector / concierge**
   sub-agent team from [`config/agents.yaml`](../../config/agents.yaml),
3. injects the Discord team protocol from
   [`identity/AGENTS.team.md`](../../identity/AGENTS.team.md),
4. tails the sandbox logs.

The agent itself still runs in its own OpenShell sandbox container managed via
the host Docker daemon — same isolation as a manual install.

## Prerequisites

- Docker + Docker Compose on the host
- NVIDIA API key (build.nvidia.com), Tavily API key, Discord bot token
  (bot invited to the server with Message Content intent — see
  `docs/multi-agent-architecture.md`)
- ~15 GB free disk for the sandbox image

## Deploy

```bash
cd deploy/docker-compose
cp .env.example .env      # fill in the three keys — .env is git-ignored
docker compose up -d
docker compose logs -f    # watch install + onboard (first run takes minutes)
```

Verify: the bot comes online in Discord; `@Brain hello` gets a reply.

## Operate

```bash
docker compose logs -f            # follow agent activity
docker compose restart workspace  # re-run onboard + identity injection
docker compose down               # stop (sandbox container stops with gateway)
```

Update identity or agents: edit `identity/AGENTS.team.md` or
`config/agents.yaml`, commit, then `docker compose restart workspace`.

## Known limits (honest notes)

- First `docker compose up` performs a multi-GB sandbox image build.
- This scaffold follows the community example's proven flags (shared
  `NEMOCLAW_BIN_PATH` on an identical host/container path, host networking)
  but has not yet been burned in on a fresh host — expect one debugging pass.
- Secrets live in `.env` on the host. For anything beyond the hackathon, move
  them to a secret store and run `openclaw secrets configure` post-onboard.
