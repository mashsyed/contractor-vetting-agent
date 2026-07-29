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
Synthetic database initialization and manager for the Contractor Vetting Platform.
Exposes mock contractor profiles with varying license, legal, rating, and quote states.
"""

import os
import sqlite3

SQLITE_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "contractors_vetting.db"))
TABLE_NAME = "contractor_records"

def get_db_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Creates the contractor vetting table and populates standard test profiles."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            contractor_id TEXT PRIMARY KEY,
            business_name TEXT,
            license_id TEXT,
            state TEXT,
            license_valid INTEGER, -- 1=True, 0=False
            lawsuit_found INTEGER, -- 1=True, 0=False
            lawsuit_details TEXT,
            insurance_valid INTEGER, -- 1=True, 0=False
            customer_rating REAL,
            project_type TEXT,
            bid_amount REAL,
            scope_of_work TEXT,
            average_market_rate REAL
        )
    """)
    
    # Pre-populate table with high-value test scenarios to showcase vetting logic
    contractors = [
        (
            "CON-1001",
            "Apex Roofing & Construction",
            "LIC-ROOF-7788",
            "CO",
            1, # Valid License
            0, # No Lawsuits
            None,
            1, # Valid Insurance
            4.8,
            "Roofing",
            12500.0,
            "Full shingle tear-off, leak protection underlayment, and installation of premium asphalt shingles.",
            13000.0 # On-par with market rate
        ),
        (
            "CON-1002",
            "Shady Brothers Renovations",
            "LIC-EXPIRED-0000",
            "CO",
            0, # EXPIRED/INVALID LICENSE -> AUTO-DISQUALIFIED (GPA 0.0)
            1, # Lawsuit Found -> Overriding Disqualification
            "Active lawsuit: Pending litigation in Boulder County Court for fraud and incomplete structural remodeling.",
            0, # Invalid Insurance
            2.1,
            "Kitchen Remodeling",
            8500.0, # Drastically underpriced (market is ~20k)
            "Complete custom kitchen remodel, including brand-new quartz countertops, custom solid oak cabinetry, and appliance wiring.",
            22000.0
        ),
        (
            "CON-1003",
            "Golden Touch Electricians",
            "LIC-ELEC-4411",
            "NY",
            1, # Valid License
            0, # No Lawsuits
            None,
            1, # Valid Insurance
            4.9,
            "Electrical",
            9500.0, # Significantly overpriced (market is ~4k)
            "Simple panel upgrade to 200 Amps and replacement of 12 standard residential wall outlets.",
            42000.0 # Wait, let's make average rate 4200.0 so bid is 9500 (overpriced)
        ),
        (
            "CON-1004",
            "Lawsuit Masters Co.",
            "LIC-LEGAL-9999",
            "CA",
            1, # Valid License
            1, # Lawsuit Found -> AUTO-DISQUALIFIED (GPA 0.0)
            "Active lawsuit: Multiple pending consumer protection cases in CA Superior Court for breach of contract.",
            1, # Valid Insurance
            3.5,
            "Plumbing",
            5500.0,
            "Main sewer line trenchless excavation, structural pipe relining, and post-install camera inspection.",
            6000.0
        ),
        (
            "CON-1005",
            "Elite Painters & Finishers",
            "LIC-PAIN-5566",
            "CA",
            1, # Valid License
            0, # No Lawsuits
            None,
            1, # Valid Insurance
            4.6,
            "Painting",
            5000.0, # Standard pricing
            "Interior walls and trim painting for 4-bedroom house with premium washable matte-finish latex paint.",
            5200.0
        )
    ]
    
    cursor.execute(f"DELETE FROM {TABLE_NAME}")
    
    cursor.executemany(f"""
        INSERT INTO {TABLE_NAME} (
            contractor_id, business_name, license_id, state, license_valid,
            lawsuit_found, lawsuit_details, insurance_valid, customer_rating,
            project_type, bid_amount, scope_of_work, average_market_rate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, contractors)
    
    conn.commit()
    conn.close()

def get_all_contractors():
    """Queries and returns all contractor records in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {TABLE_NAME}")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_contractor_by_id(contractor_id: str):
    """Fetches a single contractor's complete profile by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE contractor_id = ?", (contractor_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

if __name__ == "__main__":
    init_database()
    print("Contractor Vetting SQLite Database initialized successfully.")
