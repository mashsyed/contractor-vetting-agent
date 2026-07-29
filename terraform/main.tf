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

terraform {
  required_version = ">= 1.3.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.80.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required Google Cloud APIs for Vertex AI and Serverless Agent hosting
resource "google_project_service" "apis" {
  for_each = toset([
    "aiplatform.googleapis.com",      # Vertex AI Platform
    "run.googleapis.com",             # Cloud Run hosting
    "firestore.googleapis.com",       # Firestore database
    "secretmanager.googleapis.com",   # Secret Manager for secure secrets
    "artifactregistry.googleapis.com" # Artifact Registry for Docker builds
  ])
  service            = each.key
  disable_on_destroy = false
}

# Create Firestore database in Native mode for secure persistent conversational history
resource "google_firestore_database" "history_db" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

# Create Secret Manager secret for secure API Keys and Database Credentials
resource "google_secret_manager_secret" "api_secret" {
  secret_id = "agent-vetting-secrets"

  replication {
    automatic = true
  }

  depends_on = [google_project_service.apis]
}

# Build and provision the Cloud Run service hosting the FastAPI Multi-Agent system
resource "google_cloud_run_service" "agent_service" {
  name     = "contractor-vetting-agent-service"
  location = var.region

  template {
    spec {
      containers {
        image = "gcr.io/${var.project_id}/contractor-vetting-agent:latest"
        
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "GOOGLE_CLOUD_LOCATION"
          value = "global"
        }
        env {
          name  = "GOOGLE_GENAI_USE_VERTEXAI"
          value = "True"
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.apis, google_firestore_database.history_db]
}

# Allow unauthenticated invocation for our FastAPI public browser-web-app interface
resource "google_cloud_run_service_iam_member" "noauth" {
  location = google_cloud_run_service.agent_service.location
  project  = google_cloud_run_service.agent_service.project
  service  = google_cloud_run_service.agent_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
