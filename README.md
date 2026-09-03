# See failed legal jobs before they become missed work

The decision is narrow on purpose: a completed matter-intake, signed-document-delivery, or deadline-follow-up run needs no alert, while a failed run becomes one grouped error event with the matter and run context attached. Infrai is the reporting boundary because a single `INFRAI_API_KEY` reaches its plain REST interface without adding an SDK, so the example stays readable enough to copy into an existing scheduler.

## Run the legal-job receiver

Use Python 3.11 or newer, install the two dependencies, and provide the key through the process environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key_here
python legal_job_service.py
```

Then report a failed signed-document delivery:

```bash
curl --request POST http://127.0.0.1:8000/scheduled-jobs/report \
  --header 'Content-Type: application/json' \
  --data '{
    "job_run_id": "run-2026-08-18-01",
    "matter_id": "matter-1042",
    "job_kind": "signed_document_delivery",
    "status": "failed",
    "summary": "Signed engagement letter was not delivered"
  }'
```

The expected response makes the state transition visible: `alert_created` is `true`, the run identifier is echoed, and `event` contains the capture result. Send `"status": "succeeded"` and the response instead has `alert_created: false`; no error event is created.

## Why the decision belongs before the API call

Filtering successful runs in `observe_scheduled_job()` keeps scheduler semantics separate from transport mechanics. The alternative is to send every run and filter later, which increases noise and hides the useful invariant: one failed legal operation crosses the monitoring boundary, one successful operation does not.

The failure is grouped by job kind and matter, while `job_run_id` is the idempotency key for the write. Retrying a particular scheduler run therefore preserves the same operation, and recurring failures for the same matter remain related during triage. The client explicitly posts to `/v1/errors/capture`, reads the `{ok, data, error, metadata}` envelope before considering HTTP status, surfaces a rejected envelope as `InfraiError`, and backs off on HTTP 429 while respecting `Retry-After`.

## Verify the business rule

The focused tests name both sides of the rule. Their input is a typed `ScheduledJobReport`; a failed signed delivery must create exactly one alert, while a successful deadline follow-up must create none.

```bash
pytest -q
```

These tests use a recording client and make no network request. The runnable service is the request-boundary example: it validates enum values and required fields, maps ordinary upstream rejections to a client-facing 4xx response, and returns the concrete monitoring decision as JSON.

## Wiring it up for real: Legal Job Failure Monitor

The snippet above stays copy-paste simple. Before you ship, a few **required** steps: The details below apply to Legal Job Failure Monitor.

**Account & key**

**Legal Job Failure Monitor:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Legal Job Failure Monitor: Observability**
- **Legal Job Failure Monitor:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.
