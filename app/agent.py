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
ADK Multi-Agent Orchestration for Contractor Vetting Platform.
Defines specialized sub-agents (Quote Auditor, License Verifier, Interview Coach, Trust & Decisioning)
and a lead Coordinator agent.
"""

import os
from functools import cached_property
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
from google.genai import Client

from app.vetting_tools import (
    audit_estimate, 
    verify_credentials, 
    calculate_trust_score, 
    list_contractors_by_project_type,
    request_human_approval,
    evaluate_security_policy
)

# Set GCP location and auth environment variables for standard Vertex AI usage
os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

class GlobalGemini(Gemini):
    """Custom Gemini wrapper that forces the 'global' location on Vertex AI,
    which is required for preview models and global GCP workspaces.
    """
    @cached_property
    def api_client(self) -> Client:
        from google.genai import Client
        use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() in ("true", "1", "yes")
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        
        base_url, api_version = self._base_url_and_api_version
        kwargs_for_http_options = {
            'headers': self._tracking_headers(),
            'retry_options': self.retry_options,
            'base_url': base_url,
        }
        if api_version:
            kwargs_for_http_options['api_version'] = api_version

        kwargs = {
            'http_options': types.HttpOptions(**kwargs_for_http_options),
            'vertexai': use_vertex,
            'location': 'global',
        }
        if project:
            kwargs['project'] = project
        return Client(**kwargs)

    @cached_property
    def _live_api_client(self) -> Client:
        from google.genai import Client
        use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() in ("true", "1", "yes")
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        
        base_url, _ = self._base_url_and_api_version
        kwargs = {
            'http_options': types.HttpOptions(
                headers=self._tracking_headers(),
                api_version=self._live_api_version,
                base_url=base_url,
            ),
            'vertexai': use_vertex,
            'location': 'global',
        }
        if project:
            kwargs['project'] = project
        return Client(**kwargs)

# Common Model Configurations for Strategic Routing
gemini_flash = GlobalGemini(
    model="gemini-3.5-flash",
    retry_options=types.HttpRetryOptions(attempts=3),
)

gemini_pro = GlobalGemini(
    model="gemini-2.5-pro",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# -------------------------------------------------------------
# 1. SPECIALIZED SUB-AGENT: Quote & Estimate Auditor
# -------------------------------------------------------------
quote_auditor_agent = Agent(
    name="quote_auditor_agent",
    model=gemini_flash,
    instruction=(
        "You are the Quote & Estimate Auditor Agent.\n"
        "Your role is to analyze a contractor's cost estimates against market rates and evaluate the scope of work.\n"
        "1. Read the contractor's bid details (bid amount, average market rate, and scope of work).\n"
        "2. Invoke the `audit_estimate` tool to calculate the cost discrepancy and identify risk levels.\n"
        "3. Interpret underpricing risks (low-ball, bait-and-switch) or overpricing risks (gouging) clearly.\n"
        "4. Output a summary of your financial audit including the discrepancy percentage and risk level.\n\n"
        "CRITICAL EXPERIENCE RULE:\n"
        "Every time you invoke a tool, output a descriptive sentence in real-time explaining what you are doing (e.g. 'I am now auditing the estimate of $X compared to the typical market rate of $Y...')."
    ),
    tools=[audit_estimate],
)

# -------------------------------------------------------------
# 2. SPECIALIZED SUB-AGENT: Credentials & License Verifier
# -------------------------------------------------------------
license_verifier_agent = Agent(
    name="license_verifier_agent",
    model=gemini_flash,
    instruction=(
        "You are the Credentials & License Verifier Agent.\n"
        "Your role is to check the legal standing, professional licensing, and insurance of the contractor.\n"
        "1. Use the `verify_credentials` tool with the provided contractor ID.\n"
        "2. Examine the results carefully to check if the license is valid/active and if any lawsuits exist.\n"
        "3. If any lawsuit details are returned, highlight them as active warnings.\n"
        "4. Report your findings (license validity, lawsuits found, and insurance standing) back to the system.\n\n"
        "CRITICAL EXPERIENCE RULE:\n"
        "Every time you invoke a tool, output a descriptive sentence in real-time explaining what you are doing (e.g. 'I am now querying the state registry and lawsuit databases for contractor ID X...')."
    ),
    tools=[verify_credentials],
)

# -------------------------------------------------------------
# 3. SPECIALIZED SUB-AGENT: Homeowner Interview Coach
# -------------------------------------------------------------
interview_coach_agent = Agent(
    name="interview_coach_agent",
    model=gemini_flash,
    instruction=(
        "You are the Homeowner Interview Coach Agent.\n"
        "Your role is to review the contractor's audit findings and construct a customized interview script for the homeowner.\n"
        "1. Identify key risk areas based on findings (e.g., severe underpricing, license issues, lawsuits, or high hidden fees).\n"
        "2. Draft 3 to 5 targeted, tactical questions with guidance on what answer the homeowner should look for.\n"
        "3. Keep the tone supportive, empowering, and strategic to prepare the homeowner for negotiating or interviewing."
    ),
)

# -------------------------------------------------------------
# 4. SPECIALIZED SUB-AGENT: Trust and Decisioning
# -------------------------------------------------------------
trust_decisioning_agent = Agent(
    name="trust_decisioning_agent",
    model=gemini_pro,
    instruction=(
        "You are the Trust & Decisioning Agent.\n"
        "Your role is to compile all vetting outputs, run calculations, and formulate the final Decision Card.\n"
        "1. Fetch the outputs from `license_verifier_agent` and `quote_auditor_agent`.\n"
        "2. Invoke the `calculate_trust_score` tool, providing license validity, lawsuit found, discrepancy percentage, and customer rating.\n"
        "3. Enforce the AUTO-DISQUALIFICATION rule immediately: if license is invalid OR lawsuit is found, GPA is instantly 0.0.\n"
        "4. Provide the final GPA, letter grade, and the summary text back to the coordinator.\n\n"
        "CRITICAL EXPERIENCE RULE:\n"
        "Every time you invoke a tool, output a descriptive sentence in real-time explaining what you are doing (e.g. 'I am now calculating the overall vetting GPA and checking for auto-disqualification parameters...')."
    ),
    tools=[calculate_trust_score, request_human_approval],
)

# -------------------------------------------------------------
# 5. PARENT/ROOT COORDINATOR: Contractor Vetting Coordinator
# -------------------------------------------------------------
coordinator_agent = Agent(
    name="contractor_vetting_coordinator",
    model=gemini_flash,
    instruction=(
        "You are the Lead Contractor Vetting Coordinator Agent.\n"
        "Your goal is to guide homeowners through a comprehensive multi-agent vetting of residential contractors.\n"
        "You supervise the following specialized sub-agents:\n"
        "- `quote_auditor_agent`: Audits cost quotes and flags anomalies.\n"
        "- `license_verifier_agent`: Verifies licensing, legal lawsuits, and insurance.\n"
        "- `interview_coach_agent`: Generates strategic homeowner interview coaching guides.\n"
        "- `trust_decisioning_agent`: Compiles findings, calculates weighted GPA, and produces the final Decision Card.\n\n"
        "OPERATION & STREAMING WORKFLOW:\n"
        "1. You must be highly communicative and explain step-by-step progress logs to the user before calling any sub-agent.\n"
        "2. When a user asks to vet a contractor (e.g., CON-1001, CON-1002, etc.):\n"
        "   - First, delegate to `license_verifier_agent` to check credentials.\n"
        "   - Second, delegate to `quote_auditor_agent` to audit the quote/bid details.\n"
        "   - Third, delegate to `trust_decisioning_agent` to compile everything, run calculations, and determine the final GPA and vetting status.\n"
        "   - Fourth, delegate to `interview_coach_agent` to prepare a personalized homeowner coaching guide based on findings.\n"
        "3. Synthesize the final outcomes. Display a beautiful, structured markdown response for the homeowner including:\n"
        "   - A clear **Contractor Vetting Decision Card** (with GPA, Letter Grade, and status like APPROVED or AUTO-DISQUALIFIED).\n"
        "   - A comparison of findings (Licensing status, Lawsuit records, Quote audit discrepancy, Customer rating).\n"
        "   - A tailored Homeowner Coaching Interview Guide."
    ),
    sub_agents=[quote_auditor_agent, license_verifier_agent, interview_coach_agent, trust_decisioning_agent],
    tools=[list_contractors_by_project_type, evaluate_security_policy]
)

# Top-level ADK App Container
app = App(
    root_agent=coordinator_agent,
    name="contractor_vetting_app",
)
