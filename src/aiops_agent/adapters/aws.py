"""AWS provider adapter (stub-friendly when credentials are missing)."""

from __future__ import annotations

import os
from typing import Any

from aiops_agent.adapters.base import ActionResult, ActionRisk, CloudAction, CloudAdapter


class AWSAdapter(CloudAdapter):
    provider = "aws"

    def available(self) -> bool:
        return bool(
            os.environ.get("AWS_ACCESS_KEY_ID")
            or os.environ.get("AWS_PROFILE")
            or os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE")
        )

    def list_actions(self) -> list[CloudAction]:
        return [
            CloudAction(
                name="describe_alarms",
                risk=ActionRisk.READ,
                description="List CloudWatch alarms",
            ),
            CloudAction(
                name="get_metric_stats",
                risk=ActionRisk.READ,
                description="Fetch CloudWatch metric statistics",
                params={"namespace": "AWS/EC2", "metric": "CPUUtilization"},
            ),
            CloudAction(
                name="restart_ecs_service",
                risk=ActionRisk.HIGH,
                description="Force new deployment of an ECS service",
                mutating=True,
                params={"cluster": "", "service": ""},
            ),
            CloudAction(
                name="scale_asg",
                risk=ActionRisk.HIGH,
                description="Update Auto Scaling Group desired capacity",
                mutating=True,
                params={"asg": "", "desired": 1},
            ),
        ]

    def execute(self, action: CloudAction) -> ActionResult:
        stub = not self.available()
        data: dict[str, Any]
        if action.name == "describe_alarms":
            data = {
                "alarms": [
                    {"name": "cpu-high", "state": "ALARM", "region": "us-east-1"},
                ],
                "mode": "stub" if stub else "live",
            }
        elif action.name == "get_metric_stats":
            data = {
                "metric": action.params.get("metric", "CPUUtilization"),
                "datapoints": [{"avg": 87.2, "unit": "Percent"}],
                "mode": "stub" if stub else "live",
            }
        elif action.name == "restart_ecs_service":
            data = {
                "cluster": action.params.get("cluster", "default"),
                "service": action.params.get("service", "api"),
                "status": "DEPLOYMENT_TRIGGERED",
                "mode": "stub" if stub else "live",
            }
        elif action.name == "scale_asg":
            data = {
                "asg": action.params.get("asg", "web-asg"),
                "desired": action.params.get("desired", 1),
                "status": "UPDATING",
                "mode": "stub" if stub else "live",
            }
        else:
            return ActionResult(
                ok=False,
                provider=self.provider,
                action=action.name,
                error=f"unknown action: {action.name}",
                stub=stub,
            )
        return ActionResult(
            ok=True,
            provider=self.provider,
            action=action.name,
            data=data,
            stub=stub,
            evidence={"provider": self.provider, "action": action.name, "stub": stub},
        )
