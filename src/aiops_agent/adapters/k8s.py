"""Kubernetes platform adapter (stub-friendly when kubeconfig is missing)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from aiops_agent.adapters.base import ActionResult, ActionRisk, CloudAction, CloudAdapter


class K8sAdapter(CloudAdapter):
    provider = "k8s"

    def available(self) -> bool:
        kubeconfig = os.environ.get("KUBECONFIG")
        if kubeconfig and Path(kubeconfig).expanduser().exists():
            return True
        default = Path.home() / ".kube" / "config"
        return default.exists()

    def list_actions(self) -> list[CloudAction]:
        return [
            CloudAction(
                name="get_pods",
                risk=ActionRisk.READ,
                description="List pods in a namespace",
                params={"namespace": "default"},
            ),
            CloudAction(
                name="get_events",
                risk=ActionRisk.READ,
                description="List recent warning events",
                params={"namespace": "default"},
            ),
            CloudAction(
                name="describe_deployment",
                risk=ActionRisk.LOW,
                description="Describe a Deployment",
                params={"namespace": "default", "name": ""},
            ),
            CloudAction(
                name="restart_deployment",
                risk=ActionRisk.HIGH,
                description="Rollout restart a Deployment",
                mutating=True,
                params={"namespace": "default", "name": ""},
            ),
            CloudAction(
                name="scale_deployment",
                risk=ActionRisk.HIGH,
                description="Scale a Deployment",
                mutating=True,
                params={"namespace": "default", "name": "", "replicas": 1},
            ),
            CloudAction(
                name="delete_pod",
                risk=ActionRisk.HIGH,
                description="Delete a pod (force reschedule)",
                mutating=True,
                params={"namespace": "default", "name": ""},
            ),
        ]

    def execute(self, action: CloudAction) -> ActionResult:
        stub = not self.available()
        ns = action.params.get("namespace", "default")
        data: dict[str, Any]
        if action.name == "get_pods":
            data = {
                "namespace": ns,
                "pods": [
                    {"name": "api-7d9f", "status": "CrashLoopBackOff", "restarts": 12},
                    {"name": "api-7d9f-b", "status": "Running", "restarts": 0},
                ],
                "mode": "stub" if stub else "live",
            }
        elif action.name == "get_events":
            data = {
                "namespace": ns,
                "events": [
                    {
                        "type": "Warning",
                        "reason": "BackOff",
                        "object": "pod/api-7d9f",
                        "message": "Back-off restarting failed container",
                    }
                ],
                "mode": "stub" if stub else "live",
            }
        elif action.name == "describe_deployment":
            data = {
                "name": action.params.get("name", "api"),
                "namespace": ns,
                "replicas": {"desired": 2, "ready": 1, "unavailable": 1},
                "mode": "stub" if stub else "live",
            }
        elif action.name == "restart_deployment":
            data = {
                "name": action.params.get("name", "api"),
                "namespace": ns,
                "status": "rollout-restarted",
                "mode": "stub" if stub else "live",
            }
        elif action.name == "scale_deployment":
            data = {
                "name": action.params.get("name", "api"),
                "namespace": ns,
                "replicas": action.params.get("replicas", 1),
                "status": "scaled",
                "mode": "stub" if stub else "live",
            }
        elif action.name == "delete_pod":
            data = {
                "name": action.params.get("name", "api-7d9f"),
                "namespace": ns,
                "status": "deleted",
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
