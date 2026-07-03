#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
REPO="1729kent/dayone"
gcloud iam workload-identity-pools create github --location global 2>/dev/null || true
gcloud iam workload-identity-pools providers create-oidc github-oidc \
  --location global --workload-identity-pool github \
  --issuer-uri "https://token.actions.githubusercontent.com" \
  --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition "assertion.repository=='$REPO'" 2>/dev/null || true
gcloud iam service-accounts create dayone-deployer 2>/dev/null || true
for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:dayone-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role "$role" -q --condition=None >/dev/null
done
gcloud iam service-accounts add-iam-policy-binding \
  "dayone-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/${PROJECT_NUM}/locations/global/workloadIdentityPools/github/attribute.repository/${REPO}"
echo "provider: projects/${PROJECT_NUM}/locations/global/workloadIdentityPools/github/providers/github-oidc"
