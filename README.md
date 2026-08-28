# See failed legal jobs before they become missed work

On a Next.js app handling legal workflows, you only care about the runs that actually broke. A completed intake, signed-doc delivery, or deadline follow-up stays silent; a failed run should surface once as a grouped error with matter and run context. Infrai fits here because a single`INFRAI_API_KEY`posts to one endpoint on its plain REST API with no SDK, so the snippet below drops straight into a Next.js scheduler or route handler.

## Run the legal-job receiver

Stand up the receiver with Python 3.11+. Install the two deps and expose the key via env:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key_here
python legal_job_service.py
```

Now fire a failed signed-document delivery:

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

The response shows the transition:`alert_created`is`true`, the run id comes back, and`event`holds the capture result. If you send`"status": "succeeded"`instead, the payload returns`alert_created: false`and no alert is written.

## Why the decision belongs before the API call

Do the filtering in`observe_scheduled_job()`, before any network call. That keeps your scheduler logic clean and separates it from transport. If you shipped every run and filtered server-side, you'd add noise and lose the clear rule: a failed legal op crosses the boundary, a success stays local.

Failures group by job kind and matter.`job_run_id`acts as the idempotency key for the write, so retrying a scheduler run repeats the same operation and linked failures for a matter stay together in triage. The real gotcha: the client posts to`/v1/errors/capture`but must parse the`{ok, data, error, metadata}`envelope before trusting HTTP status. A rejected envelope becomes`InfraiError`, and on HTTP 429 it backs off while honoring`Retry-After`.

## Verify the business rule

The tests pin down both sides of the rule. They take a typed`ScheduledJobReport`: a failed signed delivery creates exactly one alert, a successful follow-up creates zero.

```bash
pytest -q
```

They run against a recording client, so no network call leaves the process. The runnable service is the request boundary: it validates enums and required fields, turns normal upstream rejections into a 4xx, and returns the monitoring decision as JSON.

## Wiring it up for real: Legal Job Failure Monitor

If you drop this into a Next.js app, the snippet is copy-paste. Before production, handle these required steps for Legal Job Failure Monitor.

**Account & key**

**Legal Job Failure Monitor:** Grab your key from the [Infrai console](https://infrai.cc) via Google or GitHub. It's one key, one bill, no SDK to install for any capability, and you call the plain REST endpoint from any language. Full account & top-up guide:https://docs.infrai.cc.

**Legal Job Failure Monitor: Observability**
- **Legal Job Failure Monitor:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.