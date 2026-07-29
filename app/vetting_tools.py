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
These tools are exposed directly to the specialized ADK agents.
"""

from typing import Dict, Any, Optional
from app.mock_data import get_contractor_by_id, get_all_contractors

def audit_estimate(bid_amount: float, average_market_rate: float, scope_of_work: str) -> Dict[str, Any]:
    """Audits contractor bids/quotes against typical market rates for cost anomalies.
    
    Args:
        bid_amount: The total project cost estimated by the contractor.
        average_market_rate: The typical market rate for this specific project type.
        scope_of_work: The written description of the services and materials.
        
    Returns:
        A dictionary containing cost discrepancy statistics, risk categorization,
        and helpful descriptions of potential cost pitfalls (low-ball or gouging).
    """
    if average_market_rate <= 0:
        return {"error": "Average market rate must be greater than zero."}
        
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
        
    return {
        "bid_amount": bid_amount,
        "average_market_rate": average_market_rate,
        "discrepancy_percentage": round(discrepancy_percentage, 2),
        "finding_category": finding_category,
        "risk_level": risk_level,
        "analysis_details": analysis_details
    }

def verify_credentials(contractor_id: str) -> Dict[str, Any]:
    """Verifies state professional licenses, lawsuit/legal filings, and insurance standing.
    
    Args:
        contractor_id: The unique registration identifier of the contractor (e.g. CON-1001).
        
    Returns:
        A dictionary containing official credential check results including license status,
        active lawsuit filings, and business insurance standing.
    """
    contractor = get_contractor_by_id(contractor_id)
    if not contractor:
        # Fallback dynamic simulation if a contractor is queried that isn't in database
        return {
            "contractor_id": contractor_id,
            "business_name": "Unknown Contractor",
            "license_id": "UNKNOWN",
            "state": "UNKNOWN",
            "license_valid": False,
            "lawsuit_found": True,
            "lawsuit_details": "No records found in database. Marked unlicensed and unverified for safety.",
            "insurance_valid": False,
            "status": "UNVERIFIED"
        }
        
    return {
        "contractor_id": contractor["contractor_id"],
        "business_name": contractor["business_name"],
        "license_id": contractor["license_id"],
        "state": contractor["state"],
        "license_valid": bool(contractor["license_valid"]),
        "lawsuit_found": bool(contractor["lawsuit_found"]),
        "lawsuit_details": contractor["lawsuit_details"],
        "insurance_valid": bool(contractor["insurance_valid"]),
        "customer_rating": contractor["customer_rating"],
        "status": "VERIFIED"
    }

def calculate_trust_score(
    license_valid: bool, 
    lawsuit_found: bool, 
    discrepancy_percentage: float, 
    customer_rating: float
) -> Dict[str, Any]:
    """Computes an objective, overall contractor vetting GPA and final decision card.
    
    Args:
        license_valid: Boolean indicating if professional business license is valid and active.
        lawsuit_found: Boolean indicating if there are any pending consumer fraud or breach lawsuits.
        discrepancy_percentage: Percentage difference between contractor bid and market rate.
        customer_rating: Historical customer satisfaction rating (0.0 to 5.0).
        
    Returns:
        A dictionary containing the calculated overall Trust GPA (0.0 to 4.0),
        the vetting status category, and detailed grading breakdown.
    """
    # 1. AUTO-DISQUALIFICATION OVERRIDE RULE
    # If the license is invalid OR if there is an active lawsuit, the contractor is instantly DQ'd (GPA = 0.0)
    if not license_valid or lawsuit_found:
        dq_reasons = []
        if not license_valid:
            dq_reasons.append("Invalid, expired, or non-existent business license.")
        if lawsuit_found:
            dq_reasons.append("Active or pending lawsuit involving structural fraud/breach of contract.")
            
        return {
            "gpa": 0.0,
            "rating": "F",
            "status": "AUTO-DISQUALIFIED",
            "is_approved": False,
            "reasons_for_disqualification": dq_reasons,
            "breakdown": {
                "license_score": 0.0,
                "rating_score": 0.0,
                "pricing_score": 0.0
            },
            "summary_card": (
                "❌ AUTO-DISQUALIFIED (GPA: 0.0)\n"
                "CRITICAL WARNING: This contractor failed mandatory legal and professional guidelines. "
                f"Reasons: {' and '.join(dq_reasons)}"
            )
        }
        
    # 2. STANDARD WEIGHTED MULTI-DIMENSIONAL GPA (0.0 - 4.0 scale)
    # Dimension A: Customer Rating (50% Weight) - Scaled to a max of 2.0 GPA points
    # Formula: (rating / 5.0) * 2.0
    rating_contribution = (customer_rating / 5.0) * 2.0
    
    # Dimension B: Pricing cost accuracy (50% Weight) - Scaled to a max of 2.0 GPA points
    # Minimal deviation from average market rate is rewarded.
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
        
    return {
        "gpa": total_gpa,
        "rating": rating_grade,
        "status": status,
        "is_approved": is_approved,
        "reasons_for_disqualification": [],
        "breakdown": {
            "customer_rating_contribution": round(rating_contribution, 2),
            "pricing_accuracy_contribution": round(pricing_score, 2)
        },
        "summary_card": summary_text.format(gpa=total_gpa)
    }

def list_contractors_by_project_type(project_type: str):
    """Auxiliary helper to search and return contractors of a specific project type."""
    contractors = get_all_contractors()
    return [c for c in contractors if c["project_type"].lower() == project_type.lower()]
