# Daily capture deployment

## Daily-price research extension (October 7, 2026)

The deployment script now sets `MUSA_CAPTURE_DAILY_PRICES=1`. This adds immutable
daily NYH/USGC EIA wholesale snapshots to each run without changing production
forecast inputs. Locally, run:

```bash
.venv/bin/python -m musa_nowcast.daily_capture --local-root data/prospective/daily --daily-prices
```

This prepares the job configuration; it does not mean a cloud deployment or
scheduler was executed in this session. Existing billing/deployment requirements
below still apply. No subscriptions or paid-data purchases were made.

AAA automatic collection is **disabled**. One public snapshot was captured for
feasibility inspection; robots allowances and a crawl-delay are not a data
license. Enabling the standalone daily-price collector's `--aaa-permission`
requires a reviewed artifact naming the source, authorizing automated capture,
identifying a permission reference and scope. The cloud job does not enable AAA.
There is no supported historical daily-retail backtest yet. See
`docs/DAILY_PRICES_PEERS_AND_ACCOUNTING.md` for results and limitations.

The job runs at **23:17 UTC every day**. It archives official EIA workbooks, the Murphy USA
press-release RSS feed and every linked official release, then generates a current-quarter
production/risk checkpoint. Captured releases require disclosure review before numeric
assimilation. The RSS scope is not a completed five-source historical disclosure audit.

Every execution uses a unique archive prefix. Objects are uploaded with generation-match-zero
and a SHA-256 metadata field. The runtime has object-creation permission only, preventing
replacement/deletion of existing objects. `run.json` is uploaded last; `COMPLETE` means both
source captures and checkpoint creation succeeded. A checkpoint can legitimately contain
forecast blocks when required data or methodologies are missing. Failed runs return nonzero,
preserve partial evidence and get a Cloud Run retry. Retries produce distinct captures; do not
count them as independent forecast trials. The job has one task; the scheduler does not provide
an exactly-once guarantee, so unique prefixes also make duplicate/overlapping executions safe.

## Activate

Use authenticated Google Cloud Shell with a billing-enabled project. Commit the reviewed changes
and use that commit in Cloud Shell; the deploy script refuses a dirty tree so code revision
matches the built image.

```sh
export MUSA_PROJECT_ID=your-project-id
export MUSA_ARCHIVE_BUCKET=your-globally-unique-private-bucket
bash deploy/daily_capture.sh
```

The script enables APIs, creates runtime/scheduler service accounts, creates a private bucket,
deploys the container, installs one daily scheduler and executes a first capture. The default
region is `us-central1`; set `MUSA_REGION` to override it. An existing bucket must belong to your
chosen project; choose a new bucket name if it does not. You need deployment, IAM, API-enablement
and Cloud Build permissions. Source deployment may require granting Cloud Run Builder to your
project's build service account according to Google's source-deployment prerequisites.

No cloud project or credentials are bundled. Activation requires your project and authentication.
No cloud resources have been deployed from this workspace.

## Observe

```sh
gcloud run jobs executions list --job=musa-daily-capture --region=us-central1 --project="$MUSA_PROJECT_ID"
gcloud scheduler jobs describe musa-daily-capture --location=us-central1 --project="$MUSA_PROJECT_ID"
gcloud storage ls "gs://${MUSA_ARCHIVE_BUCKET}/prospective/daily/"
```

For alerts, configure a Cloud Monitoring notification channel and alerts for failed Cloud Run job
executions and missing successful captures for more than 26 hours. Notifications require your
chosen email/channel and are not automatically configured by the deployment script. Scheduler
HTTP success means the execution was launched, not that evidence was successfully captured.

Redeploy when training actuals, weights or methodology code change. The image freezes the
weights/actuals available at deployment; this job does not automatically scrape reported actuals
into the production calibration set. Historical availability is never backdated to publication
dates: source capture timestamps remain separate from RSS publication timestamps.

## Cost

Google Cloud needs a billing account. One Scheduler job fits the current allowance of three jobs
per billing account, and short daily Cloud Run jobs may fit within compute allowances. Storage,
builds, container registry, network and shared billing-account usage can still incur charges.
The default US region supports applicable Cloud Storage free-tier allowances. Free tier is not
a hard spending cap. Set a billing budget and email alerts in the project before activating.

Official references:

- https://cloud.google.com/scheduler/pricing
- https://cloud.google.com/run/pricing
- https://cloud.google.com/storage/pricing
- https://docs.cloud.google.com/free/docs/free-cloud-features
- https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule

## Local verification

```sh
pip install -e '.[cloud]'
musa-daily-capture --local-root data/prospective/daily
```

No Google credentials are needed for local capture. Cloud uploads use the attached Cloud Run
service account through Application Default Credentials; no downloaded service-account keys.
