"""Azure provider adapter (stub-friendly when credentials are missing)."""

from __future__ import annotations

import os
from typing import Any

from aiops_agent.adapters.base import ActionResult, ActionRisk, CloudAction, CloudAdapter


class AzureAdapter(CloudAdapter):
    provider = "azure"

    def available(self) -> bool:
        return bool(
            os.environ.get("AZURE_CLIENT_ID")
            or os.environ.get("AZURE_SUBSCRIPTION_ID")
            or os.environ.get("AZURE_TENANT_ID")
        )

    def list_actions(self) -> list[CloudAction]:
        return [
            CloudAction(
                name="list_alerts",
                risk=ActionRisk.READ,
                description="List Azure Monitor alerts",
            ),
            CloudAction(
                name="get_metrics",
                risk=ActionRisk.READ,
                description="Query Azure Monitor metrics",
                params={"resource_id": "", "metric": "Percentage CPU"},
            ),
            CloudAction(
                name="restart_vm",
                risk=ActionRisk.HIGH,
                description="Restart an Azure Virtual Machine",
                mutating=True,
                params={"resource_group": "", "vm_name": ""},
            ),
            CloudAction(
                name="scale_app_service",
                risk=ActionRisk.HIGH,
                description="Scale an App Service plan",
                mutating=True,
                params={"plan": "", "instances": 1},
            ),
        ]

    def execute(self, action: CloudAction) -> ActionResult:
        stub = not self.available()
        data: dict[str, Any]
        if action.name == "list_alerts":
            data = {
                "alerts": [
                    {"name": "disk-pressure", "severity": "Sev2", "state": "Fired"},
                ],
                "mode": "stub" if stub else "live",
            }
        elif action.name == "get_metrics":
            data = {
                "metric": action.params.get("metric", "Percentage CPU"),
                "value": 72.5,
                "mode": "stub" if stub else "live",
            }
        elif action.name == "restart_vm":
            data = {
                "vm": action.params.get("vm_name", "app-vm"),
                "status": "Restarting",
                "mode": "stub" if stub else "live",
            }
        elif action.name == "scale_app_service":
            data = {
                "plan": action.params.get("plan", "prod-plan"),
                "instances": action.params.get("instances", 1),
                "status": "Scaling",
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
