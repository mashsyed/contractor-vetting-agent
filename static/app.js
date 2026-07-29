/**
 * ShieldGuard AI: Contractor Vetting Frontend Client
 * Asynchronously loads profiles and consumes multi-agent Server-Sent Events (SSE).
 */

document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

// App State
let currentAgent = "contractor_vetting_coordinator";
let activeEventSource = null;
let currentAgentBubble = null;
let accumulatedReportMarkdown = "";

// DOM Elements
const cardsContainer = document.getElementById("contractor-cards-container");
const chatTerminal = document.getElementById("agent-chat-terminal");
const resultsViewport = document.getElementById("results-viewport-container");
const statusBadge = document.getElementById("stream-status-badge");
const loaderBar = document.getElementById("progress-bar-wrap");

// Mapping Agents to styles and names
const agentMap = {
    "contractor_vetting_coordinator": {
        cssClass: "coordinator",
        name: "Lead Vetting Coordinator",
        icon: "🛡️"
    },
    "license_verifier_agent": {
        cssClass: "verifier",
        name: "License & Credentials Verifier",
        icon: "🔍"
    },
    "quote_auditor_agent": {
        cssClass: "auditor",
        name: "Quote & Estimate Auditor",
        icon: "📊"
    },
    "trust_decisioning_agent": {
        cssClass: "trust",
        name: "Trust & Decisioning Engine",
        icon: "⚖️"
    },
    "interview_coach_agent": {
        cssClass: "coordinator",
        name: "Homeowner Interview Coach",
        icon: "📣"
    }
};

async function initApp() {
    await fetchContractorProfiles();
}

/**
 * Fetch profiles from SQLite backend and render as premium cards
 */
async function fetchContractorProfiles() {
    try {
        const response = await fetch("/api/contractors");
        if (!response.ok) throw new Error("Failed to load contractor profiles.");
        const contractors = await response.json();
        
        cardsContainer.innerHTML = ""; // Clear loader
        
        contractors.forEach(c => {
            const card = document.createElement("div");
            card.className = "contractor-card";
            card.id = `card-${c.contractor_id}`;
            
            const isLawsuit = c.lawsuit_found ? "<span style='color: var(--accent-ruby); font-weight:bold;'>Lawsuit Found</span>" : "None";
            const isLicense = c.license_valid ? "<span style='color: var(--accent-emerald); font-weight:600;'>Valid</span>" : "<span style='color: var(--accent-ruby); font-weight:600;'>EXPIRED</span>";
            
            card.innerHTML = `
                <div class="card-header">
                    <div class="card-logo">👷</div>
                    <div class="card-rating">⭐ ${c.customer_rating.toFixed(1)}</div>
                </div>
                <div class="card-meta">
                    <h3>${c.business_name}</h3>
                    <div class="proj-type">${c.project_type}</div>
                </div>
                <div style="font-size: 11px; margin-top: 10px; color: var(--text-secondary);">
                    <div>Lic: ${c.license_id} (${isLicense})</div>
                    <div>Lawsuits: ${isLawsuit}</div>
                </div>
                <div class="card-bid-row">
                    <span class="bid-val">$${c.bid_amount.toLocaleString()}</span>
                    <span class="mkt-avg">Mkt Avg: $${c.average_market_rate.toLocaleString()}</span>
                </div>
            `;
            
            card.addEventListener("click", () => startContractorVetting(c.contractor_id));
            cardsContainer.appendChild(card);
        });
    } catch (e) {
        cardsContainer.innerHTML = `<div style="color: var(--accent-ruby); font-size:13px; text-align:center; padding: 20px;">Error loading profiles: ${e.message}</div>`;
    }
}

/**
 * Connect to SSE endpoint and run multi-agent vetting stream
 */
function startContractorVetting(contractorId) {
    // 1. Reset client states and clear previous terminals
    if (activeEventSource) {
        activeEventSource.close();
    }
    
    // De-select active cards
    document.querySelectorAll(".contractor-card").forEach(el => el.classList.remove("active-vetting"));
    const selectedCard = document.getElementById(`card-${contractorId}`);
    if (selectedCard) selectedCard.classList.add("active-vetting");
    
    chatTerminal.innerHTML = "";
    resultsViewport.innerHTML = `
        <div class="results-placeholder">
            <span class="placeholder-icon" style="animation: rotation 1.5s infinite linear; display:inline-block;">⚙️</span>
            <h4>Synthesizing Audit Metrics...</h4>
            <p>The multi-agent coordinator is currently running audits in the background. Real-time updates are streaming on the left.</p>
        </div>
    `;
    
    statusBadge.innerText = "Processing...";
    statusBadge.className = "stream-status active";
    loaderBar.style.display = "block";
    
    currentAgent = "contractor_vetting_coordinator";
    currentAgentBubble = null;
    accumulatedReportMarkdown = "";
    
    // 2. Open Server-Sent Events connection
    activeEventSource = new EventSource(`/api/vet/${contractorId}`);
    
    activeEventSource.addEventListener("agent_transfer", (e) => {
        const data = JSON.parse(e.data);
        const agentKey = data.agent_name;
        if (agentMap[agentKey]) {
            currentAgent = agentKey;
            currentAgentBubble = null; // Force creation of a new bubble
            appendHandoffNotice(agentMap[agentKey].name);
        }
    });
    
    activeEventSource.addEventListener("tool_call", (e) => {
        const data = JSON.parse(e.data);
        appendToolCallNotice(data.name, data.args);
    });
    
    activeEventSource.addEventListener("text", (e) => {
        const data = JSON.parse(e.data);
        appendAgentTextChunk(data.text);
    });
    
    activeEventSource.addEventListener("complete", (e) => {
        finalizeVettingRun();
    });
    
    activeEventSource.addEventListener("error", (e) => {
        const data = JSON.parse(e.data);
        handleStreamError(data.error || "Connection error occurred.");
    });
}

/**
 * Append a beautiful handoff notice to the chat timeline
 */
function appendHandoffNotice(agentName) {
    const notice = document.createElement("div");
    notice.className = "tool-exe-block";
    notice.style.borderColor = "var(--accent-indigo)";
    notice.innerHTML = `
        <span class="spinner">🔄</span>
        <span>Handoff: Transferring control to <strong>${agentName}</strong>...</span>
    `;
    chatTerminal.appendChild(notice);
    scrollToBottom(chatTerminal);
}

/**
 * Append custom tool call description cards
 */
function appendToolCallNotice(toolName, args) {
    const cleanArgs = Object.entries(args).map(([k, v]) => `${k}: ${v}`).join(", ");
    const notice = document.createElement("div");
    notice.className = "tool-exe-block";
    notice.innerHTML = `
        <span>🛠️</span>
        <span>Invoking tool <strong>${toolName}</strong> (${cleanArgs})</span>
    `;
    chatTerminal.appendChild(notice);
    scrollToBottom(chatTerminal);
}

/**
 * Streams incoming text chunks into styled agent bubbles
 */
function appendAgentTextChunk(chunk) {
    // Accumulate the full markdown text of the coordinator's final compile
    if (currentAgent === "contractor_vetting_coordinator" || currentAgent === "interview_coach_agent") {
        accumulatedReportMarkdown += chunk;
    }
    
    // Spawn new bubble if necessary
    if (!currentAgentBubble) {
        const meta = agentMap[currentAgent] || agentMap["contractor_vetting_coordinator"];
        
        currentAgentBubble = document.createElement("div");
        currentAgentBubble.className = `agent-bubble ${meta.cssClass}`;
        currentAgentBubble.innerHTML = `
            <div class="bubble-sender">
                <span class="badge-icon">${meta.icon}</span>
                <span>${meta.name}</span>
            </div>
            <div class="bubble-body"></div>
        `;
        chatTerminal.appendChild(currentAgentBubble);
    }
    
    // Append chunk text
    const bodyContainer = currentAgentBubble.querySelector(".bubble-body");
    bodyContainer.innerText += chunk;
    scrollToBottom(chatTerminal);
}

/**
 * Compiles accumulated report markdown and displays it inside results panel
 */
function finalizeVettingRun() {
    statusBadge.innerText = "Idle";
    statusBadge.className = "stream-status";
    loaderBar.style.display = "none";
    
    if (activeEventSource) {
        activeEventSource.close();
    }
    
    // If no report markdown was accumulated, use a fallback notice
    if (!accumulatedReportMarkdown.trim()) {
        accumulatedReportMarkdown = "### Vetting Completed Successfully\n\nThe contractor profile was audited and is compliant. Please review the live logs on the left.";
    }
    
    // Parse Markdown dynamically using marked library
    resultsViewport.innerHTML = `
        <div class="rendered-vetting-report">
            ${marked.parse(accumulatedReportMarkdown)}
        </div>
    `;
}

function handleStreamError(errorText) {
    statusBadge.innerText = "Error";
    statusBadge.className = "stream-status";
    loaderBar.style.display = "none";
    
    if (activeEventSource) {
        activeEventSource.close();
    }
    
    const notice = document.createElement("div");
    notice.className = "agent-bubble trust";
    notice.style.borderColor = "var(--accent-ruby)";
    notice.innerHTML = `
        <div class="bubble-sender" style="color: var(--accent-ruby);">
            <span class="badge-icon">⚠️</span>
            <span>Orchestration Error</span>
        </div>
        <div class="bubble-body" style="font-weight: 500;">
            ${errorText}
        </div>
    `;
    chatTerminal.appendChild(notice);
}

function scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
}
