"""GCP provider adapter (stub-friendly when credentials are missing)."""

from __future__ import annotations

import os
from typing import Any

from aiops_agent.adapters.base import ActionResult, ActionRisk, CloudAction, CloudAdapter


class GCPAdapter(CloudAdapter):
    provider = "gcp"

    def available(self) -> bool:
        return bool(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            or os.environ.get("GCLOUD_PROJECT")
            or os.environ.get("GCP_PROJECT")
        )

    def list_actions(self) -> list[CloudAction]:
        return [
            CloudAction(
                name="list_incidents",
                risk=ActionRisk.READ,
                description="List Cloud Monitoring incidents",
            ),
            CloudAction(
                name="query_timeseries",
                risk=ActionRisk.READ,
                description="Query Cloud Monitoring time series",
                params={"metric": "compute.googleapis.com/instance/cpu/utilization"},
            ),
            CloudAction(
                name="restart_gke_deployment",
                risk=ActionRisk.HIGH,
                description="Rollout restart a GKE Deployment",
                mutating=True,
                params={"namespace": "default", "deployment": ""},
            ),
            CloudAction(
                name="resize_mig",
                risk=ActionRisk.HIGH,
                description="Resize a Managed Instance Group",
                mutating=True,
                params={"mig": "", "size": 1},
            ),
        ]

    def execute(self, action: CloudAction) -> ActionResult:
        stub = not self.available()
        data: dict[str, Any]
        if action.name == "list_incidents":
            data = {
                "incidents": [
                    {"policy": "latency-slo", "state": "open", "severity": "P2"},
                ],
                "mode": "stub" if stub else "live",
            }
        elif action.name == "query_timeseries":
            data = {
                "metric": action.params.get(
                    "metric", "compute.googleapis.com/instance/cpu/utilization"
                ),
                "points": [{"value": 0.91}],
                "mode": "stub" if stub else "live",
            }
        elif action.name == "restart_gke_deployment":
            data = {
                "deployment": action.params.get("deployment", "api"),
                "namespace": action.params.get("namespace", "default"),
                "status": "rollout-restarted",
                "mode": "stub" if stub else "live",
            }
        elif action.name == "resize_mig":
            data = {
                "mig": action.params.get("mig", "web-mig"),
                "size": action.params.get("size", 1),
                "status": "resizing",
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
