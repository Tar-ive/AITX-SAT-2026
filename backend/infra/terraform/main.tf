# AITX SAT 2026 — always-on agent host (2-day hackathon lifetime).
# Provisions one EC2 VM that runs the deploy/docker-compose stack, backs up
# agent state and SELF-STOPS on July 20 (05:00 UTC = July 20 00:00 CDT).
# Apply/destroy commands: see infra/README.md. State stays local (gitignored).

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws   = { source = "hashicorp/aws", version = "~> 6.0" }
    tls   = { source = "hashicorp/tls", version = "~> 4.0" }
    local = { source = "hashicorp/local", version = "~> 2.5" }
  }
}

provider "aws" {
  region  = "us-east-1"
  profile = "dev_sso_giftmaxxing"
}

# Ubuntu 24.04 LTS arm64-agnostic: use x86_64 for t3 family
data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

resource "tls_private_key" "agent_host" {
  algorithm = "ED25519"
}

resource "aws_key_pair" "agent_host" {
  key_name   = "aitx-agent-host"
  public_key = tls_private_key.agent_host.public_key_openssh
}

# Private key lands next to the TF state, git-ignored.
resource "local_sensitive_file" "ssh_key" {
  content         = tls_private_key.agent_host.private_key_openssh
  filename        = "${path.module}/aitx-agent-host.pem"
  file_permission = "0600"
}

resource "aws_security_group" "agent_host" {
  name        = "aitx-agent-host"
  description = "SSH in (key-only, 2-day box); all egress"

  ingress {
    description      = "SSH (key auth only; box self-stops July 20)"
    from_port        = 22
    to_port          = 22
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  ingress {
    description      = "Live autoresearch leaderboard (read-only page + /radar)"
    from_port        = 8787
    to_port          = 8787
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}

# The account's VPC has a restrictive subnet NACL (allows only 6379 +
# ephemeral). Add SSH to it; rule is Terraform-managed and removed on destroy.
resource "aws_network_acl_rule" "leaderboard_in" {
  network_acl_id = "acl-0e5ab1f5cc5480f8c"
  rule_number    = 91
  egress         = false
  protocol       = "tcp"
  rule_action    = "allow"
  cidr_block     = "0.0.0.0/0"
  from_port      = 8787
  to_port        = 8787
}

resource "aws_network_acl_rule" "ssh_in" {
  network_acl_id = "acl-0e5ab1f5cc5480f8c"
  rule_number    = 90
  egress         = false
  protocol       = "tcp"
  rule_action    = "allow"
  cidr_block     = "0.0.0.0/0"
  from_port      = 22
  to_port        = 22
}

resource "aws_instance" "agent_host" {
  ami                                  = nonsensitive(data.aws_ssm_parameter.ubuntu_ami.value)
  instance_type                        = "t3.xlarge" # 4 vCPU / 16 GB — NVIDIA's recommended minimum is 4 vCPU
  key_name                             = aws_key_pair.agent_host.key_name
  vpc_security_group_ids               = [aws_security_group.agent_host.id]
  instance_initiated_shutdown_behavior = "stop" # self-shutdown => stopped (EBS + agent backup preserved)

  root_block_device {
    volume_size = 40
    volume_type = "gp3"
  }

  user_data = file("${path.module}/user-data.sh")

  tags = {
    Name     = "aitx-agent-host"
    project  = "aitx-sat-2026"
    lifetime = "self-stops-2026-07-20"
  }

  # Never replace the running box just because Canonical published a newer
  # Ubuntu AMI or the user-data file changed — a replace would wipe the live
  # stack (sandbox, autoresearch, search-cache). The box self-stops July 20.
  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

# Cost guard: alert at 80% of a $15 monthly budget.
resource "aws_budgets_budget" "aitx" {
  name         = "aitx-sat-2026"
  budget_type  = "COST"
  limit_amount = "15"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["tarive22@gmail.com"]
  }
}

output "public_ip" {
  value = aws_instance.agent_host.public_ip
}

output "ssh_command" {
  value = "ssh -i infra/terraform/aitx-agent-host.pem ubuntu@${aws_instance.agent_host.public_ip}"
}

output "estimated_cost" {
  value = "t3.xlarge ~$0.166/h + 40GB gp3 ~$3.2/mo => ~$8.20 for the 2-day run; ~$3/mo for the stopped EBS after July 20"
}
