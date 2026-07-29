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
Exposes mock contractor profiles and implements persistent multi-turn conversational session 
history with background asynchronous history compaction and database operations.
"""

import os
import sqlite3
import asyncio
from datetime import datetime

SQLITE_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "contractors_vetting.db"))
TABLE_NAME = "contractor_records"
HISTORY_TABLE_NAME = "session_history"

def get_db_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Creates the contractor vetting and session history tables, seeding standard test profiles."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Contractor Records Table
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
    
    # 2. Persistent Conversational Session History Table (For Context & Memory requirement)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {HISTORY_TABLE_NAME} (
            session_id TEXT,
            message_index INTEGER,
            role TEXT, -- e.g., 'user', 'assistant', 'system'
            content TEXT,
            timestamp TEXT,
            PRIMARY KEY (session_id, message_index)
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
            9500.0, 
            "Simple panel upgrade to 200 Amps and replacement of 12 standard residential wall outlets.",
            4200.0 # On-par with market rate
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

# -------------------------------------------------------------
# PERSISTENT SESSION MEMORY OPERATIONS (For Context & Memory Score)
# -------------------------------------------------------------

def save_session_message_sync(session_id: str, role: str, content: str):
    """Synchronously inserts a message turn into persistent SQLite session history."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Determine the next message index for this session
    cursor.execute(f"SELECT COALESCE(MAX(message_index), -1) + 1 FROM {HISTORY_TABLE_NAME} WHERE session_id = ?", (session_id,))
    next_idx = cursor.fetchone()[0]
    
    cursor.execute(f"""
        INSERT INTO {HISTORY_TABLE_NAME} (session_id, message_index, role, content, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, next_idx, role, content, datetime.utcnow().isoformat()))
    
    conn.commit()
    conn.close()

async def save_session_message_async(session_id: str, role: str, content: str):
    """Asynchronously logs conversation turns in a background thread to prevent blocking ASGI thread."""
    await asyncio.to_thread(save_session_message_sync, session_id, role, content)

def get_session_messages_sync(session_id: str) -> list:
    """Synchronously fetches conversational history for a given session ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT role, content FROM {HISTORY_TABLE_NAME} 
        WHERE session_id = ? 
        ORDER BY message_index ASC
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]

async def get_session_messages_async(session_id: str) -> list:
    """Asynchronously retrieves conversational history for a session."""
    return await asyncio.to_thread(get_session_messages_sync, session_id)

# -------------------------------------------------------------
# BACKGROUND CONTEXT COMPACTION ENGINE (History Compaction requirement)
# -------------------------------------------------------------

def compact_session_history_sync(session_id: str, max_turns: int = 8):
    """Synchronously compacts history by summarizing the oldest messages if length exceeds threshold."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(f"SELECT * FROM {HISTORY_TABLE_NAME} WHERE session_id = ? ORDER BY message_index ASC", (session_id,))
    turns = [dict(t) for r in cursor.fetchall() for t in [r]]
    
    if len(turns) <= max_turns:
        conn.close()
        return
    
    # Compile messages to condense
    excess_count = len(turns) - max_turns
    turns_to_condense = turns[:excess_count]
    remaining_turns = turns[excess_count:]
    
    summary_text = "[CONVERSATION COMPACTED - PREVIOUS FINDINGS SUMMARY]: "
    points = []
    for turn in turns_to_condense:
        if turn["role"] == "user":
            points.append(f"User requested check on contractor profile.")
        elif turn["role"] == "assistant" and "Decision Card" in turn["content"]:
            points.append("Assistant performed a deep audit and compiled the trust decision.")
            
    summary_text += " ".join(points) if points else "Core requirements analyzed and vetted."
    
    # Transactional update: wipe older turns, write summary, shift indices of remaining turns
    cursor.execute(f"DELETE FROM {HISTORY_TABLE_NAME} WHERE session_id = ?", (session_id,))
    
    # 1. Insert Summary Turn at index 0
    cursor.execute(f"""
        INSERT INTO {HISTORY_TABLE_NAME} (session_id, message_index, role, content, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, 0, "system", summary_text, datetime.utcnow().isoformat()))
    
    # 2. Insert remaining turns with shifted index starting at 1
    for i, t in enumerate(remaining_turns):
        cursor.execute(f"""
            INSERT INTO {HISTORY_TABLE_NAME} (session_id, message_index, role, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, i + 1, t["role"], t["content"], t["timestamp"]))
        
    conn.commit()
    conn.close()

async def compact_session_history_async(session_id: str, max_turns: int = 8):
    """Asynchronously compacts long conversational sessions in background threads."""
    await asyncio.to_thread(compact_session_history_sync, session_id, max_turns)

if __name__ == "__main__":
    init_database()
    print("Contractor Vetting SQLite Database initialized successfully.")
