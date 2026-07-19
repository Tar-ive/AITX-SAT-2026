# EC2 Agent Host — provision, deploy, verify, teardown

Every command needed to reproduce the always-on agent host. Terraform is the
source of truth (`infra/terraform/`); state and the SSH key stay local and
git-ignored.

## What gets created
- 1× **t3.large** (2 vCPU / 8 GB, 40 GB gp3, Ubuntu 24.04) in us-east-1
- Security group: SSH only (key auth), all egress
- Generated SSH keypair (`aitx-agent-host.pem`, git-ignored)
- **Self-stop**: in-instance cron backs up all agent state
  (`/sandbox/.openclaw` → `/opt/aitx/backups/*.tar.gz`) and powers off at
  **July 20, 05:00 UTC (00:00 CDT)**; shutdown behavior = *stop*, so the disk
  and backups survive. Restart later with `aws ec2 start-instances`.
- **Cost guard**: AWS Budget, email alert at 80% of $15/mo.
  Estimated cost: **~$4.30 for the 2-day run**, ~$3/mo for stopped EBS after.

## Commands

```bash
# 0. login (browser)
aws sso login --profile dev_sso_giftmaxxing

# 1. provision
cd infra/terraform
terraform init
terraform plan          # review: 5 resources
terraform apply -auto-approve
IP=$(terraform output -raw public_ip)

# 2. wait ~2 min for bootstrap, then verify
ssh -i aitx-agent-host.pem ubuntu@$IP 'tail -5 /var/log/aitx-bootstrap.log'

# 3. ship secrets (never in git / user-data)
scp -i aitx-agent-host.pem ../../.env ubuntu@$IP:/opt/aitx/repo/deploy/docker-compose/.env

# 4. deploy the stack (fork is pre-cloned at /opt/aitx/repo)
ssh -i aitx-agent-host.pem ubuntu@$IP \
  'cd /opt/aitx/repo/deploy/docker-compose && sudo docker compose up -d && sudo docker compose logs -f --tail 50'

# 5. after onboard completes: wire per-agent Discord bots + OpenShell policies
ssh -i aitx-agent-host.pem ubuntu@$IP 'cd /opt/aitx/repo && sudo scripts/wire-discord-bots.sh'

# teardown early (destroys VM + key + budget; backups die with the disk):
terraform destroy
# stop/start manually:
aws ec2 stop-instances  --instance-ids <id> --profile dev_sso_giftmaxxing
aws ec2 start-instances --instance-ids <id> --profile dev_sso_giftmaxxing
```

## Notes
- The instance clones the **stable fork** `Tar-ive/AITX-SAT-2026`; keep it
  synced from upstream before deploys (`git push fork main`).
- OpenShell policies (balanced tier + discord/tavily presets) are applied by
  `nemoclaw onboard` inside the compose stack — identical to the local box.
- The Mac remains the dev environment; the EC2 box is the always-on runtime
  (daily 13:00 UTC digest fires regardless of laptop state).
