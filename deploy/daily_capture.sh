#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root in authenticated Google Cloud Shell.
: "${MUSA_PROJECT_ID:?Set MUSA_PROJECT_ID to your billing-enabled project}"
: "${MUSA_ARCHIVE_BUCKET:?Set MUSA_ARCHIVE_BUCKET to a globally unique bucket name}"
MUSA_REGION="${MUSA_REGION:-us-central1}"
MUSA_JOB="musa-daily-capture"
MUSA_RUNTIME="musa-capture@${MUSA_PROJECT_ID}.iam.gserviceaccount.com"
MUSA_SCHEDULER="musa-scheduler@${MUSA_PROJECT_ID}.iam.gserviceaccount.com"
MUSA_REVISION="$(git rev-parse HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Commit the reviewed capture code before deployment so CODE_REVISION matches the image." >&2
  exit 1
fi

gcloud services enable run.googleapis.com cloudscheduler.googleapis.com storage.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com --project="$MUSA_PROJECT_ID"
gcloud iam service-accounts describe "$MUSA_RUNTIME" --project="$MUSA_PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam service-accounts create musa-capture --project="$MUSA_PROJECT_ID"
gcloud iam service-accounts describe "$MUSA_SCHEDULER" --project="$MUSA_PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam service-accounts create musa-scheduler --project="$MUSA_PROJECT_ID"
if ! gcloud storage buckets describe "gs://${MUSA_ARCHIVE_BUCKET}" --project="$MUSA_PROJECT_ID" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${MUSA_ARCHIVE_BUCKET}" --project="$MUSA_PROJECT_ID" \
    --location="$MUSA_REGION" --uniform-bucket-level-access --public-access-prevention
fi
# Runtime can create evidence, but cannot overwrite/delete existing archive objects.
gcloud storage buckets add-iam-policy-binding "gs://${MUSA_ARCHIVE_BUCKET}" \
  --member="serviceAccount:${MUSA_RUNTIME}" --role=roles/storage.objectCreator
gcloud run jobs deploy "$MUSA_JOB" --project="$MUSA_PROJECT_ID" --region="$MUSA_REGION" \
  --source=. --service-account="$MUSA_RUNTIME" --tasks=1 --parallelism=1 \
  --cpu=1 --memory=512Mi --task-timeout=15m --max-retries=1 \
  --set-env-vars="ARCHIVE_BUCKET=${MUSA_ARCHIVE_BUCKET},CODE_REVISION=${MUSA_REVISION},MUSA_CAPTURE_DAILY_PRICES=1"
gcloud run jobs add-iam-policy-binding "$MUSA_JOB" --project="$MUSA_PROJECT_ID" --region="$MUSA_REGION" \
  --member="serviceAccount:${MUSA_SCHEDULER}" --role=roles/run.invoker
MUSA_URI="https://run.googleapis.com/v2/projects/${MUSA_PROJECT_ID}/locations/${MUSA_REGION}/jobs/${MUSA_JOB}:run"
if gcloud scheduler jobs describe "$MUSA_JOB" --project="$MUSA_PROJECT_ID" --location="$MUSA_REGION" >/dev/null 2>&1; then
  MUSA_OPERATION=update
else
  MUSA_OPERATION=create
fi
gcloud scheduler jobs "$MUSA_OPERATION" http "$MUSA_JOB" \
  --project="$MUSA_PROJECT_ID" --location="$MUSA_REGION" --schedule='17 23 * * *' --time-zone=UTC \
  --uri="$MUSA_URI" --http-method=POST --oauth-service-account-email="$MUSA_SCHEDULER" \
  --attempt-deadline=180s --max-retry-attempts=2 --min-backoff=60s --max-backoff=300s
gcloud run jobs execute "$MUSA_JOB" --project="$MUSA_PROJECT_ID" --region="$MUSA_REGION" --wait
