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
Interactive CLI Demo Runner for the Multi-Agent Contractor Vetting Platform.
Showcases real-time multi-agent execution, tool calls, and final decision synthesis.
"""

import sys
import time
from app.mock_data import init_database, get_all_contractors
from app.agent import coordinator_agent as root_agent

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ANSI Color codes for premium terminal formatting
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RESET = "\033[0m"

def print_header(title: str):
    print(f"\n{BOLD}{BLUE}" + "="*80)
    print(f" {title.center(78)} ")
    print("="*80 + f"{RESET}")

def run_agent_vetting(contractor_id: str):
    """Initializes the ADK Runner and runs a live chat turn to vet a specific contractor."""
    print_header(f"VETTING RUN FOR {contractor_id}")
    print(f"{BOLD}Initializing Google ADK Multi-Agent Session...{RESET}\n")
    
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="demo_user", app_name="vetting_app")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="vetting_app")
    
    prompt = f"Please perform a complete vetting analysis for contractor {contractor_id}."
    message = types.Content(
        role="user", 
        parts=[types.Part.from_text(text=prompt)]
    )
    
    print(f"{BOLD}{CYAN} homeowner_user:{RESET} \"{prompt}\"")
    print(f"{BOLD}{YELLOW}--------------------------------------------------------------------------------{RESET}")
    print(f"{BOLD}{YELLOW}                       LIVE MULTI-AGENT EXECUTION STREAM                        {RESET}")
    print(f"{BOLD}{YELLOW}--------------------------------------------------------------------------------{RESET}")
    
    # Run the agent stream
    events = runner.run(
        new_message=message,
        user_id="demo_user",
        session_id=session.id,
        run_config=RunConfig(streaming_mode=StreamingMode.SSE),
    )
    
    # Simple, clean parser to output standard text streams in real-time
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    # Print chunks as they stream in
                    sys.stdout.write(part.text)
                    sys.stdout.flush()
                elif part.function_call:
                    # Highlight tool executions inside the stream
                    tool_name = part.function_call.name
                    args = part.function_call.args
                    print(f"\n\n{BOLD}{MAGENTA}🛠 [Tool Call] Invoking `{tool_name}` with args: {dict(args)}{RESET}\n")
                    
    print(f"\n{BOLD}{YELLOW}--------------------------------------------------------------------------------{RESET}\n")

def main():
    print_header("RESIDENTIAL HOMEOWNER - CONTRACTOR VETTING PLATFORM")
    print("Initializing local contractor database...")
    init_database()
    print(f"{GREEN}✔ Database initialized successfully.{RESET}\n")
    
    contractors = get_all_contractors()
    
    print(f"{BOLD}Available Contractor Profiles in Registry:{RESET}")
    print("-" * 80)
    for c in contractors:
        valid_symbol = f"{GREEN}Valid{RESET}" if c["license_valid"] else f"{RED}EXPIRED/INVALID{RESET}"
        lawsuit_symbol = f"{RED}YES{RESET}" if c["lawsuit_found"] else f"{GREEN}None{RESET}"
        
        print(f"• {BOLD}{c['contractor_id']}{RESET}: {c['business_name']}")
        print(f"  - Project Type: {c['project_type']} | Bid: ${c['bid_amount']:,.2f} (Market avg: ${c['average_market_rate']:,.2f})")
        print(f"  - License: {c['license_id']} ({valid_symbol}) | Lawsuit Records: {lawsuit_symbol} | Rating: {c['customer_rating']}/5.0")
        print("-" * 80)
        
    print(f"\n{BOLD}Select an Option:{RESET}")
    print("1. Vet CON-1001 (Apex Roofing - Low-risk standard case)")
    print("2. Vet CON-1002 (Shady Brothers - Unlicensed, active lawsuits, extremely underpriced)")
    print("3. Vet CON-1003 (Golden Touch - Overpriced electrician panel upgrade)")
    print("4. Vet CON-1004 (Lawsuit Masters - Valid license but severe lawsuit issues)")
    print("5. Custom (Enter a specific Contractor ID)")
    print("6. Exit")
    
    try:
        choice = input(f"\n{BOLD}Enter selection (1-6): {RESET}").strip()
        if choice == "1":
            run_agent_vetting("CON-1001")
        elif choice == "2":
            run_agent_vetting("CON-1002")
        elif choice == "3":
            run_agent_vetting("CON-1003")
        elif choice == "4":
            run_agent_vetting("CON-1004")
        elif choice == "5":
            cid = input(f"{BOLD}Enter Contractor ID (e.g. CON-1005): {RESET}").strip()
            run_agent_vetting(cid)
        else:
            print("Exiting. Thank you for using the Contractor Vetting Platform!")
    except KeyboardInterrupt:
        print("\nExiting. Goodbye!")

if __name__ == "__main__":
    main()
