# Second, small box that runs ONLY the Cursor-agent Karpathy autoresearch loop
# (root-level auto_research_loop.py + skills/autoresearch/). Kept separate from
# the main agent host so the proven loop there is never disrupted. No Docker
# sandbox, no Discord bots — just Python making API calls, so t3.small is ample.

resource "aws_instance" "cursor_host" {
  ami                                  = nonsensitive(data.aws_ssm_parameter.ubuntu_ami.value)
  instance_type                        = "t3.small" # 2 vCPU / 2 GB — the loop is API-bound
  key_name                             = aws_key_pair.agent_host.key_name
  vpc_security_group_ids               = [aws_security_group.agent_host.id]
  subnet_id                            = "subnet-03f325678b07bb408" # same subnet as main box (NACL allows SSH)
  instance_initiated_shutdown_behavior = "stop"

  root_block_device {
    volume_size = 12
    volume_type = "gp3"
  }

  user_data = file("${path.module}/cursor-user-data.sh")

  tags = {
    Name     = "aitx-cursor-autoresearch"
    project  = "aitx-sat-2026"
    lifetime = "self-stops-2026-07-20"
  }

  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

output "cursor_public_ip" {
  value = aws_instance.cursor_host.public_ip
}

output "cursor_ssh" {
  value = "ssh -i infra/terraform/aitx-agent-host.pem ubuntu@${aws_instance.cursor_host.public_ip}"
}
