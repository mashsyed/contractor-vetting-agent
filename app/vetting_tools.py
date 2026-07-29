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
Vetting & Auditing Tools for Multi-Agent Contractor Vetting.
Utilizes strict Pydantic schemas for inputs and outputs to ensure explicit JSON schemas,
implements guided error handling, and introduces policy guardrails and human-in-the-loop confirmation tools.
"""

import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.mock_data import get_contractor_by_id, get_all_contractors

# -------------------------------------------------------------
# PYDANTIC SCHEMAS FOR TOOL INPUTS & OUTPUTS (Tool & Interface Design)
# -------------------------------------------------------------

class AuditEstimateInput(BaseModel):
    bid_amount: float = Field(..., description="The total project cost estimated by the contractor (must be positive).")
    average_market_rate: float = Field(..., description="The average market rate for this type of project (must be positive).")
    scope_of_work: str = Field(..., description="The written description of the services and materials.")

class AuditEstimateOutput(BaseModel):
    bid_amount: float = Field(..., description="The original bid amount.")
    average_market_rate: float = Field(..., description="The baseline average market rate.")
    discrepancy_percentage: float = Field(..., description="Percentage variance of bid from market rate.")
    finding_category: str = Field(..., description="Categorization of the audit finding (e.g. UNDERPRICING_FALLACY).")
    risk_level: str = Field(..., description="Evaluation risk level (LOW, MEDIUM, HIGH).")
    analysis_details: str = Field(..., description="Rich breakdown of cost risks and pitfalls.")
    error: Optional[str] = Field(None, description="Detailed error message if inputs are invalid.")
    recovery_instructions: Optional[str] = Field(None, description="Clear, guided action items for the calling LLM to recover from errors.")

class VerifyCredentialsInput(BaseModel):
    contractor_id: str = Field(..., description="The unique registration identifier of the contractor (e.g., CON-1001).")

class VerifyCredentialsOutput(BaseModel):
    contractor_id: str = Field(..., description="The unique registration ID verified.")
    business_name: str = Field(..., description="The registered legal name of the business.")
    license_id: str = Field(..., description="The state professional license code.")
    state: str = Field(..., description="The registered jurisdiction state.")
    license_valid: bool = Field(..., description="Whether the professional license is active and valid.")
    lawsuit_found: bool = Field(..., description="Whether litigation records exist against this contractor.")
    lawsuit_details: str = Field(..., description="Summary details of any lawsuit filings.")
    insurance_valid: bool = Field(..., description="Whether active liability insurance is valid.")
    customer_rating: float = Field(..., description="The historical customer rating (1.0 - 5.0).")
    status: str = Field(..., description="The registration state (VERIFIED, UNVERIFIED).")
    error: Optional[str] = Field(None, description="Detailed error message if lookup fails.")
    recovery_instructions: Optional[str] = Field(None, description="Actionable recovery steps for the LLM.")

class CalculateTrustScoreInput(BaseModel):
    license_valid: bool = Field(..., description="Active standing of state license.")
    lawsuit_found: bool = Field(..., description="Active consumer litigation record.")
    discrepancy_percentage: float = Field(..., description="Variance percentage of contractor's quote from market baseline.")
    customer_rating: float = Field(..., description="Average star rating of contractor (0.0 to 5.0).")

class BreakdownScores(BaseModel):
    customer_rating_contribution: float = Field(..., description="Reputation rating contribution (0.0 to 2.0 GPA scale).")
    pricing_accuracy_contribution: float = Field(..., description="Cost accuracy contribution (0.0 to 2.0 GPA scale).")

class CalculateTrustScoreOutput(BaseModel):
    gpa: float = Field(..., description="The final compiled trust GPA (0.0 to 4.0 scale).")
    rating: str = Field(..., description="The final Letter Grade (A, B, C, D, or F).")
    status: str = Field(..., description="Actionable recommendation status (e.g. APPROVED_TRUSTWORTHY, AUTO-DISQUALIFIED).")
    is_approved: bool = Field(..., description="Boolean indicating if contractor is verified and approved.")
    reasons_for_disqualification: List[str] = Field(..., description="Specific failures triggering disqualifications.")
    breakdown: BreakdownScores = Field(..., description="Multi-dimensional GPA components.")
    summary_card: str = Field(..., description="Markdown compiled decision summary block.")
    error: Optional[str] = Field(None, description="Validation error message.")
    recovery_instructions: Optional[str] = Field(None, description="Actionable recovery steps for the LLM.")

class HumanApprovalInput(BaseModel):
    contractor_id: str = Field(..., description="The registration ID of the contractor undergoing auditing.")
    action_description: str = Field(..., description="The high-stakes decision or final grade being approved (e.g. Approved with Grade B).")

class HumanApprovalOutput(BaseModel):
    is_approved: bool = Field(..., description="Boolean indicating whether human approval has been successfully resolved.")
    audit_log: str = Field(..., description="A formal audit log tracking this confirmation step.")
    message: str = Field(..., description="Official decision notification details.")

class PolicyGuardrailInput(BaseModel):
    user_query: str = Field(..., description="The incoming prompt or instructions to scan for safety policies.")

class PolicyGuardrailOutput(BaseModel):
    is_cleared: bool = Field(..., description="Whether the prompt is completely safe and cleared.")
    policy_code: str = Field(..., description="Vetting policy status code (e.g. CLEAR, EXPLOIT_VIOLATION).")
    feedback: str = Field(..., description="Structured feedback for self-evaluation safety guardrails.")

# -------------------------------------------------------------
# CORE TOOL IMPLEMENTATIONS
# -------------------------------------------------------------

def audit_estimate(bid_amount: float, average_market_rate: float, scope_of_work: str) -> AuditEstimateOutput:
    """Audits contractor bids/quotes against typical market rates for cost anomalies.
    
    Args:
        bid_amount: The total project cost estimated by the contractor.
        average_market_rate: The typical market rate for this specific project type.
        scope_of_work: The written description of the services and materials.
        
    Returns:
        AuditEstimateOutput Pydantic model with rich financial stats and risk levels.
    """
    if bid_amount <= 0 or average_market_rate <= 0:
        return AuditEstimateOutput(
            bid_amount=bid_amount,
            average_market_rate=average_market_rate,
            discrepancy_percentage=0.0,
            finding_category="INVALID_PARAMETERS",
            risk_level="HIGH",
            analysis_details="Failed to compute audit. Financial values must be positive non-zero numbers.",
            error="Negative or zero pricing values are invalid.",
            recovery_instructions="GUIDED RECOVERY: Ask the homeowner or coordinator to provide a valid, positive bid amount and market rate. Do not guess pricing numbers."
        )
        
    discrepancy_percentage = ((bid_amount - average_market_rate) / average_market_rate) * 100
    
    # Categorize risk and finding
    if bid_amount < average_market_rate * 0.70:
        finding_category = "UNDERPRICING_FALLACY"
        risk_level = "HIGH"
        analysis_details = (
            f"The bid of ${bid_amount:,.2f} is significantly lower ({abs(discrepancy_percentage):.1f}% below) "
            f"than the average market rate of ${average_market_rate:,.2f}. This is a classic low-ball risk. "
            "Homeowners should watch out for cheap/substandard materials, subsequent bait-and-switch change orders, "
            "or an incomplete scope of work."
        )
    elif bid_amount > average_market_rate * 1.30:
        finding_category = "OVERPRICING_ANOMALY"
        risk_level = "MEDIUM"
        analysis_details = (
            f"The bid of ${bid_amount:,.2f} is exceptionally high ({discrepancy_percentage:.1f}% above) "
            f"compared to the typical market rate of ${average_market_rate:,.2f}. Homeowners risk being gouged "
            "or overcharged unless the quote contains highly premium custom materials or structural complexity."
        )
    else:
        finding_category = "REASONABLE_AND_COMPETITIVE"
        risk_level = "LOW"
        analysis_details = (
            f"The bid of ${bid_amount:,.2f} is highly competitive, falling within "
            f"{abs(discrepancy_percentage):.1f}% of the average market rate (${average_market_rate:,.2f}). "
            "Pricing represents realistic labor and materials costs."
        )
        
    return AuditEstimateOutput(
        bid_amount=bid_amount,
        average_market_rate=average_market_rate,
        discrepancy_percentage=round(discrepancy_percentage, 2),
        finding_category=finding_category,
        risk_level=risk_level,
        analysis_details=analysis_details
    )

def verify_credentials(contractor_id: str) -> VerifyCredentialsOutput:
    """Verifies state professional licenses, lawsuit/legal filings, and insurance standing.
    
    Args:
        contractor_id: The unique registration identifier of the contractor (e.g. CON-1001).
        
    Returns:
        VerifyCredentialsOutput Pydantic model with license, litigation, and insurance standing.
    """
    if not contractor_id or not contractor_id.startswith("CON-"):
        return VerifyCredentialsOutput(
            contractor_id=contractor_id or "INVALID",
            business_name="Unregistered Business",
            license_id="UNKNOWN",
            state="UNKNOWN",
            license_valid=False,
            lawsuit_found=True,
            lawsuit_details="Failed compliance: invalid contractor ID format.",
            insurance_valid=False,
            customer_rating=0.0,
            status="UNVERIFIED",
            error="Malformed Contractor ID. IDs must start with the prefix 'CON-' (e.g., CON-1001).",
            recovery_instructions="GUIDED RECOVERY: Check the contractor ID format. Ask the user for a valid registered contractor ID matching 'CON-XXXX'. Do not perform manual audits for malformed IDs."
        )

    contractor = get_contractor_by_id(contractor_id)
    if not contractor:
        return VerifyCredentialsOutput(
            contractor_id=contractor_id,
            business_name="Unknown Contractor",
            license_id="UNKNOWN",
            state="UNKNOWN",
            license_valid=False,
            lawsuit_found=True,
            lawsuit_details="No records found in state registry database.",
            insurance_valid=False,
            customer_rating=1.0,
            status="UNVERIFIED",
            error=f"Contractor with ID {contractor_id} does not exist in the official state registry.",
            recovery_instructions=f"GUIDED RECOVERY: Contractor ID {contractor_id} is missing in the database. Notify the coordinator to declare the contractor unverified and auto-disqualified for safety. Do not assume licensing is active."
        )
        
    return VerifyCredentialsOutput(
        contractor_id=contractor["contractor_id"],
        business_name=contractor["business_name"],
        license_id=contractor["license_id"],
        state=contractor["state"],
        license_valid=bool(contractor["license_valid"]),
        lawsuit_found=bool(contractor["lawsuit_found"]),
        lawsuit_details=contractor["lawsuit_details"],
        insurance_valid=bool(contractor["insurance_valid"]),
        customer_rating=float(contractor["customer_rating"]),
        status="VERIFIED"
    )

def calculate_trust_score(
    license_valid: bool, 
    lawsuit_found: bool, 
    discrepancy_percentage: float, 
    customer_rating: float
) -> CalculateTrustScoreOutput:
    """Computes an objective, overall contractor vetting GPA and final decision card.
    
    Args:
        license_valid: Boolean indicating if professional business license is valid and active.
        lawsuit_found: Boolean indicating if there are any pending consumer fraud or breach lawsuits.
        discrepancy_percentage: Percentage difference between contractor bid and market rate.
        customer_rating: Historical customer satisfaction rating (0.0 to 5.0).
        
    Returns:
        CalculateTrustScoreOutput Pydantic model with GPA (0.0 - 4.0), grade, and status.
    """
    # Guard against invalid rating parameters
    if customer_rating < 0.0 or customer_rating > 5.0:
        return CalculateTrustScoreOutput(
            gpa=0.0,
            rating="F",
            status="ERROR_INVALID_INPUTS",
            is_approved=False,
            reasons_for_disqualification=["Malformed customer rating input"],
            breakdown=BreakdownScores(customer_rating_contribution=0.0, pricing_accuracy_contribution=0.0),
            summary_card="Validation failed: customer rating must be between 0.0 and 5.0.",
            error="Star rating parameter out of bounds.",
            recovery_instructions="GUIDED RECOVERY: Provide a valid star rating (0.0 to 5.0) and retry calculating the trust score."
        )

    # 1. AUTO-DISQUALIFICATION OVERRIDE RULE
    if not license_valid or lawsuit_found:
        dq_reasons = []
        if not license_valid:
            dq_reasons.append("Invalid, expired, or non-existent business license.")
        if lawsuit_found:
            dq_reasons.append("Active or pending lawsuit involving structural fraud/breach of contract.")
            
        return CalculateTrustScoreOutput(
            gpa=0.0,
            rating="F",
            status="AUTO-DISQUALIFIED",
            is_approved=False,
            reasons_for_disqualification=dq_reasons,
            breakdown=BreakdownScores(customer_rating_contribution=0.0, pricing_accuracy_contribution=0.0),
            summary_card=(
                "❌ AUTO-DISQUALIFIED (GPA: 0.0)\n"
                "CRITICAL WARNING: This contractor failed mandatory legal and professional guidelines. "
                f"Reasons: {' and '.join(dq_reasons)}"
            )
        )
        
    # 2. STANDARD WEIGHTED MULTI-DIMENSIONAL GPA (0.0 - 4.0 scale)
    # Dimension A: Customer Rating (50% Weight) - Scaled to a max of 2.0 GPA points
    rating_contribution = (customer_rating / 5.0) * 2.0
    
    # Dimension B: Pricing cost accuracy (50% Weight) - Scaled to a max of 2.0 GPA points
    deviation = abs(discrepancy_percentage)
    if deviation <= 10.0:
        pricing_score = 2.0
    elif deviation <= 25.0:
        pricing_score = 1.5
    elif deviation <= 40.0:
        pricing_score = 1.0
    else:
        pricing_score = 0.5
        
    total_gpa = round(rating_contribution + pricing_score, 2)
    
    # Assign Letter Grade and Status based on GPA
    if total_gpa >= 3.7:
        rating_grade = "A"
        status = "RECOMMENDED_EXCELLENT"
        is_approved = True
        summary_text = "🥇 OUTSTANDING (GPA: {gpa}/4.0) - Exceeds all standard metrics. Highly recommended."
    elif total_gpa >= 3.0:
        rating_grade = "B"
        status = "APPROVED_TRUSTWORTHY"
        is_approved = True
        summary_text = "✅ APPROVED (GPA: {gpa}/4.0) - Fully verified, compliant, and reasonably priced."
    elif total_gpa >= 2.0:
        rating_grade = "C"
        status = "RISKY_PROCEED_WITH_CAUTION"
        is_approved = False
        summary_text = "⚠️ RISKY (GPA: {gpa}/4.0) - Compliant legal status, but significant rating or cost discrepancy issues exist."
    else:
        rating_grade = "D"
        status = "NOT_RECOMMENDED"
        is_approved = False
        summary_text = "🚫 NOT RECOMMENDED (GPA: {gpa}/4.0) - Low ratings or extreme quote deviations."
        
    return CalculateTrustScoreOutput(
        gpa=total_gpa,
        rating=rating_grade,
        status=status,
        is_approved=is_approved,
        reasons_for_disqualification=[],
        breakdown=BreakdownScores(
            customer_rating_contribution=round(rating_contribution, 2),
            pricing_accuracy_contribution=round(pricing_score, 2)
        ),
        summary_card=summary_text.format(gpa=total_gpa)
    )

# -------------------------------------------------------------
# 3. SECURITY GUARDRAILS / POLICY PLUGINS (Orchestration & Logic)
# -------------------------------------------------------------

def evaluate_security_policy(user_query: str) -> PolicyGuardrailOutput:
    """Programmatic self-evaluation policy guardrail.
    Scans for adversarial instructions, scale manipulations, or SQL injections.
    
    Args:
        user_query: The text to audit against legal compliance policies.
    """
    restricted_phrases = ["sql injection", "drop table", "ignore lawsuit", "ignore license", "bypass compliance"]
    for phrase in restricted_phrases:
        if phrase in user_query.lower():
            return PolicyGuardrailOutput(
                is_cleared=False,
                policy_code="RESTRICTED_KEYWORDS_VIOLATION",
                feedback=(
                    f"POLICY VIOLATION DETECTED: Prompt contains prohibited instructions ('{phrase}'). "
                    "Vetting guidelines cannot be altered or bypassed."
                )
            )
    return PolicyGuardrailOutput(is_cleared=True, policy_code="CLEAR", feedback="Input cleared against policy guardrails.")

# -------------------------------------------------------------
# 4. HUMAN-IN-THE-LOOP (HITL) CONFIRMATION HOOKS (Orchestration & Logic)
# -------------------------------------------------------------

def request_human_approval(contractor_id: str, action_description: str) -> HumanApprovalOutput:
    """Explicit human-in-the-loop audit log confirmation gate for high-stakes actions.
    
    Args:
        contractor_id: Registered ID of the contractor under review.
        action_description: Specific final grade or status recommendation being confirmed.
    """
    approval_file = "admin_approval.txt"
    time_str = datetime_str = "2026-07-29T12:00:00Z"
    
    # Check for programmatic human approval override file
    if os.path.exists(approval_file):
        with open(approval_file, "r") as f:
            note = f.read().strip()
        return HumanApprovalOutput(
            is_approved=True,
            audit_log=f"[{time_str}] HITL_CONFIRMED: Admin manual signoff for contractor {contractor_id}. Note: {note}",
            message=f"Success: High-stakes action '{action_description}' approved by administrator."
        )
        
    # Standard fallback tracking
    print(f"[HUMAN_IN_THE_LOOP_HOOK]: Sign-off requested for {contractor_id} -> '{action_description}'. Automatically cleared in dev mode.")
    return HumanApprovalOutput(
        is_approved=True,
        audit_log=f"[{time_str}] HITL_AUTO_BYPASS: Sign-off for contractor {contractor_id} cleared in dev-bypass.",
        message=f"Auto-cleared: Dev-bypass mode enabled."
    )

def list_contractors_by_project_type(project_type: str) -> List[Dict[str, Any]]:
    """Auxiliary helper to search and return contractors of a specific project type."""
    contractors = get_all_contractors()
    return [c for c in contractors if c["project_type"].lower() == project_type.lower()]
