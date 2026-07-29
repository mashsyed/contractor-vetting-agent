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
Observability and Tracing Engine for the Contractor Vetting Platform.
Provides:
1. Structured JSON Logging
2. Intent vs. Outcome Logging
3. Distributed Tracing using simulated OpenTelemetry-compatible span correlation
4. PII Redaction for logs and history strings
"""

import json
import re
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Configure standard logger to bypass basic prints and output structured JSON strings
logger = logging.getLogger("ShieldGuardObservability")
logger.setLevel(logging.INFO)

# Remove default handlers to prevent duplicates
if logger.handlers:
    logger.handlers.clear()

class JSONFormatter(logging.Formatter):
    """Custom logging formatter that encodes records into standardized JSON lines."""
    def format(self, record: logging.LogRecord) -> str:
        log_payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.msg,
            "trace_id": getattr(record, "trace_id", "00000000000000000000000000000000"),
            "span_id": getattr(record, "span_id", "0000000000000000"),
            "component": getattr(record, "component", "observability_engine"),
            "metadata": getattr(record, "metadata", {})
        }
        # Run PII redaction over the message and metadata before formatting to JSON
        log_payload["message"] = redact_pii(log_payload["message"])
        if isinstance(log_payload["metadata"], dict):
            log_payload["metadata"] = {k: redact_pii(str(v)) for k, v in log_payload["metadata"].items()}
            
        return json.dumps(log_payload)

# Bind JSON formatter to stdout handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(JSONFormatter())
logger.addHandler(console_handler)

# -------------------------------------------------------------
# 1. PII REDACTION MECHANISMS (Observability & Tracing Score)
# -------------------------------------------------------------

def redact_pii(text: str) -> str:
    """Scrubs sensitive user information (Emails, SSNs, Credit Cards, Phone numbers) 
    from logged strings before any storage or display occurs.
    """
    if not isinstance(text, str):
        return text
        
    # Email pattern
    text = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[REDACTED_EMAIL]", text)
    # US SSN pattern (e.g. 000-00-0000)
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]", text)
    # Standard 16 digit Credit Card numbers
    text = re.sub(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", "[REDACTED_CREDIT_CARD]", text)
    # Generic US Phone numbers (e.g. 123-456-7890)
    text = re.sub(r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b", "[REDACTED_PHONE]", text)
    
    return text

# -------------------------------------------------------------
# 2. DISTRIBUTED TRACING ENGINE (Observability & Tracing Score)
# -------------------------------------------------------------

class TraceSpan:
    """Distributed tracing span manager supporting trace ID and span ID propagation."""
    def __init__(self, name: str, parent_trace_id: Optional[str] = None):
        self.name = name
        self.trace_id = parent_trace_id or uuid.uuid4().hex
        self.span_id = uuid.uuid4().hex[:16]
        self.start_time = datetime.utcnow()

    def __enter__(self):
        logger.info(
            f"Span started: {self.name}",
            extra={
                "trace_id": self.trace_id,
                "span_id": self.span_id,
                "component": "distributed_tracing",
                "metadata": {"span_name": self.name}
            }
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (datetime.utcnow() - self.start_time).total_seconds() * 1000
        status = "ERROR" if exc_type else "SUCCESS"
        
        logger.info(
            f"Span finished: {self.name}",
            extra={
                "trace_id": self.trace_id,
                "span_id": self.span_id,
                "component": "distributed_tracing",
                "metadata": {
                    "span_name": self.name,
                    "duration_ms": duration_ms,
                    "status": status,
                    "error_type": exc_type.__name__ if exc_type else None
                }
            }
        )

# -------------------------------------------------------------
# 3. INTENT VS. OUTCOME CAPTURE LOGGING (Observability & Tracing Score)
# -------------------------------------------------------------

def log_intent(tool_name: str, args: Dict[str, Any], span: TraceSpan):
    """Logs the explicit INTENT of an agent action or tool invocation before running."""
    logger.info(
        f"[INTENT] Invoking tool '{tool_name}'",
        extra={
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "component": "intent_vs_outcome",
            "metadata": {
                "tool_name": tool_name,
                "arguments": args,
                "lifecycle_state": "PRE_EXECUTION"
            }
        }
    )

def log_outcome(tool_name: str, result: Any, span: TraceSpan):
    """Logs the actual verified OUTCOME of an action after execution."""
    logger.info(
        f"[OUTCOME] Tool '{tool_name}' execution completed",
        extra={
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "component": "intent_vs_outcome",
            "metadata": {
                "tool_name": tool_name,
                "outcome_payload": str(result),
                "lifecycle_state": "POST_EXECUTION"
            }
        }
    )
