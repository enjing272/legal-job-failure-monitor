from legal_job_monitor import JobKind, JobStatus, ScheduledJobReport, observe_scheduled_job


class RecordingClient:
    def __init__(self) -> None:
        self.reports = []

    def capture_failure(self, report: ScheduledJobReport) -> dict[str, str]:
        self.reports.append(report)
        return {"event_id": "evt-test"}


def test_failed_signed_delivery_creates_one_alert() -> None:
    client = RecordingClient()
    report = ScheduledJobReport(
        job_run_id="run-2026-08-18-01",
        matter_id="matter-1042",
        job_kind=JobKind.SIGNED_DOCUMENT_DELIVERY,
        status=JobStatus.FAILED,
        summary="Signed engagement letter was not delivered",
    )

    decision = observe_scheduled_job(report, client)

    assert decision.alert_created is True
    assert decision.event == {"event_id": "evt-test"}
    assert client.reports == [report]


def test_successful_deadline_follow_up_does_not_create_alert() -> None:
    client = RecordingClient()
    report = ScheduledJobReport(
        job_run_id="run-2026-08-18-02",
        matter_id="matter-1042",
        job_kind=JobKind.DEADLINE_FOLLOW_UP,
        status=JobStatus.SUCCEEDED,
        summary="Client received the deadline reminder",
    )

    decision = observe_scheduled_job(report, client)

    assert decision.alert_created is False
    assert client.reports == []
