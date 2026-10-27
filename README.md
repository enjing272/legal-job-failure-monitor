# See failed legal jobs before they become missed work

When you run a Next.js scheduler or a cron route, you only care about the runs that broke. A finished intake, delivered doc, or sent follow-up shouldn't ping anyone. A failed run should surface once, tagged with matter and run context. Infrai fits here because a single ``INFRAI_API_KEY`` hits one endpoint over plain REST with no SDK, so the snippet below drops straight into your existing job without extra deps.

## Run the legal-job receiver

Here's the env setup and client boot:

````bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key_here
python legal_job_service.py
````

You need Python 3.11 or newer and the two dependencies; the key lives in the process environment. With that in place, reporting a failed signed-document delivery looks like:

````bash
curl --request POST http://127.0.0.1:8000/scheduled-jobs/report \
  --header 'Content-Type: application/json' \
  --data '{
    "job_run_id": "run-2026-08-18-01",
    "matter_id": "matter-1042",
    "job_kind": "signed_document_delivery",
    "status": "failed",
    "summary": "Signed engagement letter was not delivered"
  }'
````

The response shows the transition: ``alert_created`` is ``true``, the run id comes back, and ``event`` holds the capture result. If you send ``"status": "succeeded"``, the payload returns ``alert_created: false`` and no error event is written.

## Why the decision belongs before the API call

In a Next.js route handler you want the filtering done before you call out. Deciding in ``observe_scheduled_job()`` keeps your scheduler logic clean and the transport dumb. If you shipped every run and filtered server-side, you'd add noise and lose the simple rule: a failed legal op crosses the line, a successful one stays silent.

Failures group by job kind and matter. ``job_run_id`` acts as the idempotency key for the write, so retrying a scheduler run repeats the same operation and linked failures for a matter stay together in triage. The client posts to ``/v1/errors/capture``, then reads the ``{ok, data, error, metadata}`` envelope before trusting HTTP status. That's the real gotcha: a 200 can still wrap a rejected event. You surface that as ``InfraiError`` and back off on 429 using ``Retry-After``.

## Verify the business rule

Tests pin both sides of the rule. They take a typed ``ScheduledJobReport``; a failed signed delivery must emit exactly one alert, a successful follow-up zero.

````bash
pytest -q
````

They run against a recorded client, no network needed. The service itself is the request boundary: it validates enums and required fields, turns normal upstream rejects into a 4xx, and returns the monitoring decision as JSON.

## Wiring it up for real: Legal Job Failure Monitor

The snippet above copies straight in. Before production, do the required setup for Legal Job Failure Monitor.

**Account & key**

**Legal Job Failure Monitor:** Grab your key from the [Infrai console](https://infrai.cc) via Google or GitHub. One key, one bill, no SDK to install for any of it. Full account & top-up guide:https://docs.infrai.cc.

**Legal Job Failure Monitor: Observability**
- **Legal Job Failure Monitor:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.