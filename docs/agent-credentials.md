# Agent credentials and Discord bots

Store all private credentials in the root `.env` file. It is ignored by Git.
The committed `.env.example` contains only placeholders.

## NVIDIA model access

1. Add your NVIDIA Inference API key to `.env`:

   ```dotenv
   NVIDIA_INFERENCE_API_KEY=your_key_here
   ```

2. In a WSL terminal, register it with NemoClaw without placing the key inside
   a sandbox:

   ```bash
   set -a
   source /path/to/AITX-SAT-2026/.env
   set +a
   nemohermes credentials add nvidia-prod --type nvidia --credential NVIDIA_INFERENCE_API_KEY
   ```

3. Switch only the Hermes sandbox to Nemotron 3 Super 120B:

   ```bash
   nemohermes inference set --provider nvidia-prod --model nvidia/nemotron-3-super-120b-a12b --sandbox nemohermes
   ```

## Existing and future Discord bots

Give every bot its own Discord application and token. Put each token in `.env`
using the matching name, or add a new `DISCORD_<BOT_NAME>_BOT_TOKEN` entry for
future bots.

Do not paste tokens into chat or commit them to Git. Add a bot to its NemoClaw
sandbox through the local interactive command, which prompts for the token:

```bash
nemoclaw <sandbox-name> channels add discord
```

Use one sandbox and one Discord bot token per independently operating agent.
The channel permissions should allow every bot to read `#notes`, and let each
bot send only in its assigned work channel plus `#gpu-desk` when needed.
