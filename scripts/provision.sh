#!/bin/bash
# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

echo "========================================================================"
echo "🛡️  ShieldGuard Multi-Agent Contractor Vetting Provisioning Gateway  🛡️"
echo "========================================================================"

# Validate gcloud presence
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: Google Cloud SDK (gcloud) is not installed."
    echo "Please install it from https://cloud.google.com/sdk first."
    exit 1
fi

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo "⚠️ Warning: No default Google Cloud project set in gcloud config."
    read -p "Please enter your GCP Project ID: " PROJECT_ID
fi

REGION="us-central1"
echo "⚡ Targeting project: $PROJECT_ID in region: $REGION"

echo "------------------------------------------------------------------------"
echo "1. Enabling Required Service APIs..."
echo "------------------------------------------------------------------------"
gcloud services enable \
    aiplatform.googleapis.com \
    run.googleapis.com \
    firestore.googleapis.com \
    secretmanager.googleapis.com \
    artifactregistry.googleapis.com \
    --project="$PROJECT_ID"

echo "------------------------------------------------------------------------"
echo "2. Initializing Google App Engine Firestore Database..."
echo "------------------------------------------------------------------------"
if ! gcloud firestore databases describe --project="$PROJECT_ID" &>/dev/null; then
    gcloud firestore databases create --location="$REGION" --type=firestore-native --project="$PROJECT_ID"
else
    echo "✅ Firestore database '(default)' already exists."
fi

echo "------------------------------------------------------------------------"
echo "3. Creating Cloud Secret Manager Configuration..."
echo "------------------------------------------------------------------------"
if ! gcloud secrets describe agent-vetting-secrets --project="$PROJECT_ID" &>/dev/null; then
    gcloud secrets create agent-vetting-secrets --replication-policy="automatic" --project="$PROJECT_ID"
    echo "✅ Secret 'agent-vetting-secrets' created successfully."
else
    echo "✅ Secret 'agent-vetting-secrets' already exists."
fi

echo "------------------------------------------------------------------------"
echo "4. Running Terraform Automation Plan..."
echo "------------------------------------------------------------------------"
if command -v terraform &> /dev/null; then
    cd terraform
    terraform init
    terraform plan -var="project_id=$PROJECT_ID" -var="region=$REGION"
    cd ..
else
    echo "ℹ️ Note: Terraform CLI not found. Skipping plan step."
    echo "You can apply configurations manually using terraform/main.tf."
fi

echo "========================================================================"
echo "✅ Provisioning complete! Your multi-agent platform is ready."
echo "========================================================================"
