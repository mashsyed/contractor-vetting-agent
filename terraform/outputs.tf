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

output "cloud_run_url" {
  value       = google_cloud_run_service.agent_service.status[0].url
  description = "The public-facing URL of the deployed FastAPI multi-agent contractor vetting application."
}

output "firestore_database_id" {
  value       = google_firestore_database.history_db.id
  description = "The Firestore database provisioning locator used to persist agent histories."
}
