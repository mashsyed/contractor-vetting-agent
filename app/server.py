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
FastAPI Server for Multi-Agent Contractor Vetting Platform.
Provides REST APIs for contractors and a live SSE (Server-Sent Events) endpoint 
for streaming real-time multi-agent cooperation and vetting runs.
"""

import asyncio
import json
import logging
import os
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from app.mock_data import init_database, get_all_contractors, get_contractor_by_id
from app.agent import coordinator_agent as root_agent

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure mock database is initialized on startup
init_database()

app = FastAPI(
    title="Contractor Vetting Multi-Agent API",
    description="Real-time multi-agent contractor vetting backend using Google ADK and FastAPI."
)

# Enable CORS for developer ease
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST Endpoint: Retrieve all mock contractor profiles
@app.get("/api/contractors")
def list_contractors():
    try:
        return get_all_contractors()
    except Exception as e:
        logger.error(f"Error listing contractors: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# REST Endpoint: Retrieve single contractor details
@app.get("/api/contractors/{contractor_id}")
def retrieve_contractor(contractor_id: str):
    c = get_contractor_by_id(contractor_id)
    if not c:
        raise HTTPException(status_code=404, detail="Contractor not found.")
    return c

# SSE Endpoint: Streams the live multi-agent execution
@app.get("/api/vet/{contractor_id}")
async def vet_contractor_sse(contractor_id: str):
    c = get_contractor_by_id(contractor_id)
    if not c:
        raise HTTPException(status_code=404, detail="Contractor not found.")

    async def event_generator() -> AsyncGenerator[dict, None]:
        # Initialize ADK Runner inside a thread-safe context
        session_service = InMemorySessionService()
        session = session_service.create_session_sync(user_id="web_user", app_name="web_vetting")
        runner = Runner(agent=root_agent, session_service=session_service, app_name="web_vetting")
        
        prompt = f"Please perform a complete vetting analysis for contractor {contractor_id}."
        message = types.Content(
            role="user", 
            parts=[types.Part.from_text(text=prompt)]
        )
        
        # We run the blocking generator inside a background thread pool to prevent blocking the async loop
        def run_adk():
            return list(runner.run(
                new_message=message,
                user_id="web_user",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ))

        try:
            logger.info(f"Starting multi-agent vetting stream for contractor {contractor_id}")
            events = await asyncio.to_thread(run_adk)
            
            for event in events:
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            yield {
                                "event": "text",
                                "data": json.dumps({"text": part.text})
                            }
                        elif part.function_call:
                            tool_name = part.function_call.name
                            args = dict(part.function_call.args) if part.function_call.args else {}
                            
                            if tool_name == "transfer_to_agent":
                                yield {
                                    "event": "agent_transfer",
                                    "data": json.dumps({"agent_name": args.get("agent_name")})
                                }
                            else:
                                yield {
                                    "event": "tool_call",
                                    "data": json.dumps({"name": tool_name, "args": args})
                                }
            # Yield a final completion signal
            yield {
                "event": "complete",
                "data": json.dumps({"status": "done"})
            }
        except Exception as e:
            logger.error(f"Error in multi-agent vetting stream: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())

# Ensure static files directory exists before serving it
os.makedirs("static", exist_ok=True)

# Mount the static directory for index.html, style.css, app.js
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def get_index():
    return FileResponse("static/index.html")
