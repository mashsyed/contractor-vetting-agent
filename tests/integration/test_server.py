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

"""
Integration tests for the FastAPI Contractor Vetting Backend.
Verifies REST query routing and streaming SSE event emitters.
"""

from fastapi.testclient import TestClient
from app.server import app

client = TestClient(app)

def test_list_contractors() -> None:
    """Verifies that the server returns preloaded contractors from SQLite."""
    response = client.get("/api/contractors")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["contractor_id"] == "CON-1001"

def test_retrieve_contractor() -> None:
    """Verifies that the server can retrieve details for a single contractor profile."""
    response = client.get("/api/contractors/CON-1001")
    assert response.status_code == 200
    data = response.json()
    assert data["business_name"] == "Apex Roofing & Construction"

def test_retrieve_contractor_not_found() -> None:
    """Verifies that the server correctly returns 404 for invalid contractor IDs."""
    response = client.get("/api/contractors/CON-9999")
    assert response.status_code == 404

def test_vet_contractor_sse_headers() -> None:
    """Verifies that the live vetting API returns the correct text/event-stream headers."""
    response = client.get("/api/vet/CON-1001", headers={"Accept": "text/event-stream"})
    assert response.status_code == 200
    # Ensure standard SSE streaming header is set
    assert "text/event-stream" in response.headers["content-type"]
