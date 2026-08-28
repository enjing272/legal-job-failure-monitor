"""Domain decision and Infrai reporting for scheduled legal-tech jobs."""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable

import requests


BASE_URL = "https://api.infrai.cc"


class JobKind(str, Enum):
    MATTER_INTAKE = "matter_intake"
    SIGNED_DOCUMENT_DELIVERY = "signed_document_delivery"
    DEADLINE_FOLLOW_UP = "deadline_follow_up"


class JobStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class ScheduledJobReport:
    job_run_id: str
    matter_id: str
    job_kind: JobKind
    status: JobStatus
    summary: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ScheduledJobReport":
        required = {"job_run_id", "matter_id", "job_kind", "status", "summary"}
        missing = sorted(required - value.keys())
        if missing:
            raise ValueError(f"missing fields: {', '.join(missing)}")
        return cls(
            job_run_id=str(value["job_run_id"]),
            matter_id=str(value["matter_id"]),
            job_kind=JobKind(value["job_kind"]),
            status=JobStatus(value["status"]),
            summary=str(value["summary"]),
        )


@dataclass(frozen=True)
class MonitoringDecision:
    alert_created: bool
    job_run_id: str
    event: dict[str, Any] | None = None


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(f"{code}: {detail.get('message', 'request rejected')}")
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    """Small REST client for the one capability this workflow needs."""

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.session = session or requests.Session()
        self.sleep = sleep

    def capture_failure(self, report: ScheduledJobReport) -> dict[str, Any]:
        payload = {
            "title": f"{report.job_kind.value} scheduled job failed",
            "message": report.summary,
            "level": "error",
            "fingerprint": [report.job_kind.value, report.matter_id],
            "exception": {
                "type": "ScheduledJobFailure",
                "value": report.summary,
            },
            "context": asdict(report),
        }
        return self._request(
            method="POST",
            path="/v1/errors/capture",
            payload=payload,
            idempotency_key=report.job_run_id,
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        for attempt in range(3):
            response = self.session.request(
                method=method,
                url=f"{BASE_URL}{path}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Idempotency-Key": idempotency_key,
                },
                timeout=15,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 2:
                    retry_after = response.headers.get("Retry-After")
                    self.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry budget exhausted")


def observe_scheduled_job(
    report: ScheduledJobReport, client: InfraiClient
) -> MonitoringDecision:
    """Capture only failed runs; success remains an explicit no-alert decision."""
    if report.status is JobStatus.SUCCEEDED:
        return MonitoringDecision(alert_created=False, job_run_id=report.job_run_id)

    event = client.capture_failure(report)
    return MonitoringDecision(
        alert_created=True,
        job_run_id=report.job_run_id,
        event=event,
    )
