#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-dayone-hack-2026}"
REGION="asia-northeast1"
BILLING="019D7A-DE4B13-2C4E16"

gcloud projects create "$PROJECT_ID" 2>/dev/null || echo "project exists"
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING"
gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com aiplatform.googleapis.com \
  firestore.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com iamcredentials.googleapis.com
gcloud artifacts repositories create dayone --repository-format=docker \
  --location="$REGION" 2>/dev/null || echo "AR exists"
gcloud firestore databases create --location="$REGION" 2>/dev/null || echo "firestore exists"

# rookie 用の最小権限 SA
gcloud iam service-accounts create dayone-rookie 2>/dev/null || true
for role in roles/aiplatform.user roles/datastore.user; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:dayone-rookie@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role" --condition=None -q >/dev/null
done
# app 用 SA（Job 起動 + Firestore）
gcloud iam service-accounts create dayone-app 2>/dev/null || true
for role in roles/run.developer roles/datastore.user roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:dayone-app@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$role" --condition=None -q >/dev/null
done
echo "OK: $PROJECT_ID"
