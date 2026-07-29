# **Technical Architecture Guide: Multi-Agent Contractor Vetting Platform**

# **1\. Executive Summary**

The construction and home services industry currently faces a significant operational bottleneck due to a persistent labor shortage and complex market dynamics. Finding reliable contractors is increasingly difficult as high-quality professionals "cherry-pick" large, high-margin projects, leaving residential homeowners to navigate a field often characterized by the "underpricing fallacy"—where low initial bids frequently result in poor quality or mid-project price spikes. Furthermore, vetting a contractor requires a breadth of skills spanning legal verification, financial auditing, and interpersonal assessment.

The value proposition of an agentic vetting solution lies in its ability to transform these fragmented, manual tasks into a coordinated, intelligent system. By utilizing specialized AI agents, the platform can autonomously verify licenses, analyze quotes for hidden costs, and coach homeowners on critical interview questions. This reduces manual effort, improves the accuracy of vetting, and ensures that homeowners make data-driven decisions when selecting labor.

# **2\. High-Level Architecture Pattern**

The system is built on a modular, enterprise-grade architecture that leverages the Gemini Enterprise Agent Platform to manage the full agent lifecycle.

* **Frontend:** A chat-based user interface deployed as a serverless Cloud Run service. This provides a scalable entry point for homeowners to interact with the multi-agent system.  
* **Agent Engine Runtime:** A fully managed runtime that hosts the agents, providing built-in security, scalability, and lifecycle management.  
* **Agent Development Kit (ADK):** A code-first framework used to design the custom logic and tools for each specialized agent. It enables rapid development while maintaining enterprise standards for testing and reliability.  
* **Agent-to-Agent (A2A) Protocol:** An open standard that enables seamless collaboration between specialized agents. It allows agents to share tasks, stream results, and discover each other's capabilities via "AgentCards" without needing to understand the internal implementation of their peers.

# **3\. Multi-Agent Design & Specialized Subagents**

The platform employs a hierarchical multi-agent pattern where specialized agents collaborate to fulfill the homeowner's request.

| Agent Name | Primary Responsibility | A2A Interaction Pattern |
| :---- | :---- | :---- |
| **Coordinator Agent** | Orchestrates the agentic flow and manages the main user interaction. | Dispatches tasks to subagents and synthesizes their findings for the user. |
| **Quote & Estimate Auditor Agent** | Analyzes contractor bids for cost anomalies and hidden fees. | Receives documents from the Coordinator and returns detailed audit reports. |
| **Credentials & License Verifier Agent** | Uses external tools to verify business licenses, insurance, and legal standing. | Operates as a specialized service provider to validate contractor identity. |
| **Homeowner Interview Coach Agent** | Generates tailored interview questions and evaluates contractor responses. | Provides contextual advice based on the findings of the Auditor and Verifier agents. |
| **Trust and Decisioning Agent** | Aggregates evaluation data, calculating the contractor's weighted vetting GPA, enforcing the critical Auto-Disqualification Rule, and generating the final Vetting Decision Card (AgentCard). It removes human bias and math errors by converting qualitative inputs into a transparent, structured trust score | Employs a Hierarchical Fan-In (Aggregator) Pattern \[1\]. It does not interact with the user or external APIs directly. Instead, it acts as a decision-making endpoint, consuming structured data published by specialized upstream worker agents and returning the final analysis to the parent orchestrator. |

Each agent utilizes the A2A protocol to maintain clear boundaries while ensuring interoperability across different functions. The **Coordinator Agent** uses the A2A message model to trigger subagents and track the state of complex, multi-step vetting workflows.

# **4\. Platform Integration & Tooling**

To ensure production-grade performance, the architecture integrates several core Vertex AI Agent Builder capabilities.

* **Persistent Sessions:** Managed in Agent Engine to maintain the conversation state across multiple user interactions, ensuring the system remembers previous contractor details and user preferences.  
* **RAG Memory Banks:** Used for long-term knowledge storage, such as local building codes or historical pricing data, to ground agent reasoning in factual evidence.  
* **Google Search Grounding:** Agents can ground their responses in real-time data from Google Search to verify current contractor reviews or public legal filings.  
* **Model Context Protocol (MCP):** A standardized protocol used to connect agents with external data sources and contractor databases, ensuring secure and consistent communication with third-party APIs.

# **5\. Deployment, Observability, and Governance**

The platform is deployed using enterprise-grade controls to ensure security and reliability.

* **Security Sandboxing:** Agents operate within secure runtime environments (sandboxes) in Agent Engine to prevent unauthorized code execution and ensure data isolation.  
* **Distributed Tracing:** Agent Engine provides native tracing capabilities, allowing developers to visualize how agents process requests, make decisions, and interact with various tools.  
* **Evaluation & Quality Control:** The system utilizes evaluation capabilities and user simulators to test agent performance against specific benchmarks, such as the accuracy of license verification or the helpfulness of interview coaching.  
* **Native Agent Identities:** Ensures that each agent in the system has a unique identity for secure auditing and governance.

# **6\. Agentic App Technical Requirements**

| Feature | Requirement | Description |
| :---- | :---- | :---- |
| **1\. Tool & Interface Design** | **Comprehensive Tool Docstrings** | Tool functions include clear, human-readable descriptions of their purpose and all parameters. |
|  | **Descriptive Naming** | Tool names are highly specific and clear (e.g., create\_critical\_bug instead of update\_jira). |
|  | **Explicit JSON Schemas** | The code utilizes strict input and output schemas to validate tool arguments and constrain LLMs. |
|  | **Guided Error Handling** | Tool error returns provide descriptive recovery instructions back to the LLM instead of just crashing. |
| **2\. Context & Memory** | **Robust System Instructions** | A clear "constitution" is defined in the system prompt for persona, domain knowledge, and constraints. |
|  | **History Compaction** | Code implements context bloat management (e.g., token-based truncation, sliding windows, summarization) via mechanisms and tools such as adk compaction, memory bank or context caching on google cloud |
|  | **Persistent Session State** | The agent connects to a persistent database, be it vector store or vertex ai search.  to  efficiently retrieve information ot manage conversational history across turns. |
|  | **Async Memory Operations** | Expensive memory generation and consolidation are coded as background or async tasks to prevent UI blocking. |
| **3\. Orchestration & Logic** | **Multi-Agent Patterns** | Complex tasks utilize proven design patterns (e.g., Coordinator, Sequential) rather than monolithic agents implemented in ADK |
|  | **Strategic Model Routing** | The codebase routes specific requests to the most appropriate model (e.g., Flash for fast tasks, Pro for planning). |
|  | **Guardrails & Policy Plugins** | Security  and evaluation guardrails ( i.e. self eval) implemented via existing google cloud or ADk or agentic tech |
|  | **Human-in-the-Loop Hooks** | High-stakes actions include explicit code stops requiring human confirmation before execution. |
| **4\. Observability & Tracing** | **Structured JSON Logging** | The codebase utilizes structured logging libraries to capture rich metadata rather than simple prints. |
|  | **Intent vs. Outcome Capture** | Logs explicitly record both the agent's *intended* action before execution and the *actual* outcome after. |
|  | **Distributed Tracing** | Implementation of OpenTelemetry (or equivalent) to link spans and trace a request from query to answer. |
|  | **PII Redaction** | Logging and memory pipelines include active scrubbing mechanisms to redact sensitive data before storage possibly using google cloud APIs |
| **5\. Infrastructure & CI/CD** | **Automated Evaluation Suites** | The repository contains a testing harness (e.g., against a golden dataset) to statically measure agent regressions. |
|  | **Infrastructure as Code** | The project includes IaC configurations (like Terraform) to programmatically provision necessary resources. Usage of tools such as Agent cli present in the documentation |
|  | **Secure Secret Management** | No hardcoded API keys; all tools and clients leverage a secure injection method like Secret Manager. |
| **Total** |  |  |

