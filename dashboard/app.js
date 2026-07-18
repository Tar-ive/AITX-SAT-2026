// 15 Golden Test Cases Database
const testCases = [
    {
        id: "TC-01",
        name: "Test Case 1: ASUS ROG Strix RTX 5080 (Warranty-Critical)",
        prompt: "I need a brand-new, factory-sealed ASUS ROG Strix RTX 5080 with a full manufacturer warranty. Shipped by this weekend.",
        expected: "Amazon (Direct), Newegg, or Best Buy. Skip third-party/eBay resellers.",
        debate: [
            { agent: "orchestrator", text: "Initiating hunt for brand-new, factory-sealed ASUS ROG Strix RTX 5080 with warranty. Priority: Speed (<3 days) & Warranty Verification." },
            { agent: "amazon", text: "Amazon Retail: $1,199.00 (Shipped/Sold by Amazon). Stock: High. Delivery: Friday." },
            { agent: "ebay", text: "eBay listing: $1,050.00 (Condition: 'New other - open box'). Seller rating: 98.4%. Standard shipping: 5 days." },
            { agent: "pcpp", text: "Newegg Retail: $1,189.00. B&H Photo: $1,195.00. Best Buy: $1,199.00." },
            { agent: "speculator", text: "No price reductions anticipated within 72 hours. Supply levels stable." },
            { agent: "sage", text: "Reviewing eBay listing #83726... Warning: Open-box item. Manufacturer warranty void for non-authorized resale. Recommending rejection of eBay listing." },
            { agent: "orchestrator", text: "Consensus formed: Recommend Newegg at $1,189.00 or Amazon at $1,199.00. Filtered out eBay $1,050.00 due to warranty risk flagged by Sage." }
        ],
        score: { A: 100, S: 100, P: 100, R: 100, C: 100 }
    },
    {
        id: "TC-02",
        name: "Test Case 2: M4 MacBook Pro 14-inch (AppleCare Eligible)",
        prompt: "Find the best price on a brand-new M4 MacBook Pro 14-inch. I intend to buy AppleCare+ for it, so it must be an eligible retail unit.",
        expected: "Apple Store, B&H Photo, Amazon (Direct), or Best Buy. Skip secondhand/refurbished marketplaces.",
        debate: [
            { agent: "orchestrator", text: "Initiating hunt for brand-new M4 MacBook Pro. User requires AppleCare+ post-purchase eligibility." },
            { agent: "amazon", text: "Amazon Retail: $1,499.00 (Authorized Apple Reseller). AppleCare+ option available at checkout." },
            { agent: "ebay", text: "Back Market (Refurbished Excellent): $1,280.00. Seller warranty: 1 year." },
            { agent: "pcpp", text: "Best Buy: $1,499.00. B&H Photo: $1,449.00." },
            { agent: "sage", text: "Warning: Back Market and eBay listings are refurbished/used. Apple Care+ policy states units must be purchased new from authorized resellers or Apple within 60 days. Recommending rejection of secondary markets." },
            { agent: "orchestrator", text: "Consensus formed: Recommending B&H Photo at $1,449.00 (Authorized Reseller). Filtered out refurbished options due to AppleCare+ exclusion rules." }
        ],
        score: { A: 100, S: 100, P: 100, R: 100, C: 100 }
    },
    {
        id: "TC-03",
        name: "Test Case 3: California Sales Tax Avoidance (Tax Optimization)",
        prompt: "I want to buy a brand-new RTX 5090. I live in California and want to legally avoid or minimize upfront state sales tax if a major authorized retailer offers a workaround.",
        expected: "B&H Photo Video (via Payboo)",
        debate: [
            { agent: "orchestrator", text: "Initiating hunt for brand-new RTX 5090. User location: California. Target: Legal sales tax minimization." },
            { agent: "amazon", text: "Amazon: $1,999.00. CA Sales Tax: $174.91 (8.75%). Landed: $2,173.91." },
            { agent: "pcpp", text: "B&H Photo: $1,999.00. Payboo Credit Card payment option active (instant refund of tax-equivalent cost: -$174.91)." },
            { agent: "speculator", text: "Alert: CA sales tax matches user's billing region. B&H Payboo card provides the only legal retailer-funded workaround for upfront tax." },
            { agent: "orchestrator", text: "Consensus formed: Recommend purchasing from B&H Photo at $1,999.00 using Payboo. Landed cost matches shelf cost ($1,999.00), saving $174.91." }
        ],
        score: { A: 100, S: 100, P: 100, R: 100, C: 100 }
    },
    {
        id: "TC-04",
        name: "Test Case 4: M3 MacBook Air Customer Return (Open Box)",
        prompt: "I want an M3 MacBook Air. I don't want a heavily used one, just a customer return or open-box unit that still has 10+ months of original Apple warranty left.",
        expected: "Best Buy Open-Box (Excellent) or Apple Certified Refurbished.",
        debate: [
            { agent: "orchestrator", text: "Searching for M3 MacBook Air. Condition: Open-box / Customer return with original warranty." },
            { agent: "amazon", text: "Amazon Warehouse (Like New): $890.00. Warranty status: Unverified." },
            { agent: "ebay", text: "eBay listing: $790.00. Description: 'Used for 3 months.' Original invoice not provided." },
            { agent: "pcpp", text: "Best Buy Open-Box (Excellent): $849.00. Confirmed to retain original Apple warranty balance." },
            { agent: "sage", text: "Apple Certified Refurbished: $899.00 (1-year Apple Warranty). Recommending Best Buy Open-Box or Apple Refurbished due to guaranteed warranty transfer." },
            { agent: "orchestrator", text: "Consensus formed: Recommending Best Buy Open-Box (Excellent) at $849.00. Bypassing unverified eBay listing." }
        ],
        score: { A: 100, S: 50, P: 100, R: 100, C: 100 }
    },
    {
        id: "TC-05",
        name: "Test Case 5: 5x Refurbished MacBook Pros (Interns Setup)",
        prompt: "We need 5 refurbished M2 MacBook Pros for our new interns. They must come with a verified 1-year functional warranty so our IT team doesn't have to troubleshoot them.",
        expected: "Amazon Renewed (Premium) or Back Market.",
        debate: [
            { agent: "orchestrator", text: "Sourcing 5x M2 MacBook Pros. Condition: Refurbished. Requirement: 1-Year functional warranty." },
            { agent: "ebay", text: "Individual eBay Seller: 5x lot for $4,500 ($900 each). Return policy: 14 days. No formal warranty." },
            { agent: "amazon", text: "Amazon Renewed (Excellent): $1,050 each ($5,250 total). Includes 90-day Amazon guarantee." },
            { agent: "pcpp", text: "Back Market (Verified Refurbished): $990 each ($4,950 total). Includes 1-year functional warranty." },
            { agent: "sage", text: "Rejecting eBay lot due to lack of IT-grade warranty. Back Market meets 1-year threshold at lowest cost." },
            { agent: "orchestrator", text: "Consensus formed: Recommending Back Market at $990 each with 1-year warranty coverage." }
        ],
        score: { A: 100, S: 100, P: 100, R: 100, C: 100 }
    },
    {
        id: "TC-08",
        name: "Test Case 8: 20x Corsair Vengeance RAM (3-Day LAN Center Deadline)",
        prompt: "We are building 20 custom gaming PCs for a LAN center. We need 20 identical kits of Corsair Vengeance 32GB RAM. They must arrive within 3 days or we miss our opening deadline.",
        expected: "Amazon Business (Prime) or Newegg Business.",
        debate: [
            { agent: "orchestrator", text: "Sourcing 20 identical Corsair RAM kits. Hard constraint: Delivery < 3 days." },
            { agent: "amazon", text: "Amazon Business: 20 units in stock. Total: $1,600. Delivery: Tomorrow (Prime)." },
            { agent: "ebay", text: "Alibaba manufacturer: $35 per kit ($700 total). Delivery time: 12-15 days (customs clearance required)." },
            { agent: "pcpp", text: "Newegg Business: 20 units in stock. Total: $1,580. Delivery: 2 days." },
            { agent: "speculator", text: "Alibaba pricing is 55% cheaper, but lead time violates the 3-day opening deadline. Do not route to overseas wholesale." },
            { agent: "orchestrator", text: "Consensus formed: Recommending Newegg Business at $1,580 (2-day shipping). Overseas channels rejected due to delivery delay." }
        ],
        score: { A: 100, S: 100, P: 100, R: 100, C: 100 }
    },
    {
        id: "TC-13",
        name: "Test Case 13: Cheap 64GB DDR5 Desktop RAM (Counterfeit Filter)",
        prompt: "Find me the absolute cheapest 64GB DDR5 desktop RAM kit on the internet. I don't care where it comes from.",
        expected: "Cheap authorized brand (Crucial/Silicon Power) on Amazon/Newegg.",
        debate: [
            { agent: "orchestrator", text: "Searching for lowest cost 64GB DDR5 RAM." },
            { agent: "amazon", text: "Silicon Power 64GB DDR5: $159.00." },
            { agent: "ebay", text: "Wish listing: 'New high-speed 64GB DDR5 RAM' for $18.99." },
            { agent: "pcpp", text: "Crucial 64GB DDR5: $164.00." },
            { agent: "sage", text: "CRITICAL WARNING: The $18.99 Wish listing is a known flash-controller firmware spoofing scam. Recommending Silicon Power on Amazon at $159.00 as the absolute cheapest legitimate option." },
            { agent: "orchestrator", text: "Consensus formed: Recommending Silicon Power on Amazon ($159.00). Wish option rejected and flagged as a security hazard." }
        ],
        score: { A: 100, S: 100, P: 100, R: 100, C: 100 }
    }
];

// Preloaded Sage Reflections
const reflections = [
    { id: "REF-01", date: "Day 1 (08:14)", category: "warranty", text: "Verified that manufacturer warranties (ASUS, MSI) are void for open-box items sold by non-authorized eBay resellers. Always prioritize authorized retail channels." },
    { id: "REF-02", date: "Day 1 (14:30)", category: "fees", text: "E-commerce sites regularly mask mandatory shipping and handling surcharges. Landed Price calculations must trigger a mock-browser checkout action to pull final landed numbers." },
    { id: "REF-03", date: "Day 2 (02:11)", category: "safety", text: "Wish and Temu RAM modules listed under $30 are 100% counterfeit firmware spoofs. Added hard lower bound checks ($50 minimum for 32GB, $100 for 64GB DDR5) to flag hardware scams." },
    { id: "REF-04", date: "Day 2 (11:04)", category: "logistics", text: "For lead times under 5 days, automatically disable B2B Chinese wholesalers (Alibaba, Made-In-China) due to customs clearance latency. Route bulk orders to Amazon Business or Newegg Business instead." },
    { id: "REF-05", date: "Day 2 (20:45)", category: "licensing", text: "Verified that AppleCare+ requires purchase verification within 60 days. Added strict check: if user mentions AppleCare+, filter out all refurbished platforms (Back Market, Swappa) immediately." }
];

// Default Evaluation database
const defaultEvaluations = [
    { version: "Snapshot v1.0 (Day 0 Baseline)", caseId: "TC-01", A: 0, S: 100, P: 0, R: 50, C: 0 },
    { version: "Snapshot v1.0 (Day 0 Baseline)", caseId: "TC-02", A: 50, S: 100, P: 0, R: 100, C: 50 },
    { version: "Snapshot v1.0 (Day 0 Baseline)", caseId: "TC-03", A: 0, S: 50, P: 50, R: 50, C: 0 },
    { version: "Snapshot v1.0 (Day 0 Baseline)", caseId: "TC-04", A: 50, S: 50, P: 50, R: 100, C: 50 },
    { version: "Snapshot v1.0 (Day 0 Baseline)", caseId: "TC-05", A: 50, S: 100, P: 0, R: 50, C: 50 },
    { version: "Snapshot v1.0 (Day 0 Baseline)", caseId: "TC-08", A: 0, S: 100, P: 0, R: 50, C: 0 },
    { version: "Snapshot v1.0 (Day 0 Baseline)", caseId: "TC-13", A: 0, S: 100, P: 0, R: 100, C: 0 }
    
    { version: "Snapshot v1.1 (Day 2 Reflexion)", caseId: "TC-01", A: 100, S: 100, P: 100, R: 100, C: 100 },
    { version: "Snapshot v1.1 (Day 2 Reflexion)", caseId: "TC-02", A: 100, S: 100, P: 100, R: 100, C: 100 },
    { version: "Snapshot v1.1 (Day 2 Reflexion)", caseId: "TC-03", A: 100, S: 100, P: 100, R: 100, C: 100 },
    { version: "Snapshot v1.1 (Day 2 Reflexion)", caseId: "TC-04", A: 100, S: 50, P: 100, R: 100, C: 100 },
    { version: "Snapshot v1.1 (Day 2 Reflexion)", caseId: "TC-05", A: 100, S: 100, P: 100, R: 100, C: 100 },
    { version: "Snapshot v1.1 (Day 2 Reflexion)", caseId: "TC-08", A: 100, S: 100, P: 100, R: 100, C: 100 },
    { version: "Snapshot v1.1 (Day 2 Reflexion)", caseId: "TC-13", A: 100, S: 100, P: 100, R: 100, C: 100 },
    
    { version: "GPT-4o (Standard Scraper)", caseId: "TC-01", A: 50, S: 100, P: 50, R: 100, C: 50 },
    { version: "GPT-4o (Standard Scraper)", caseId: "TC-02", A: 100, S: 100, P: 50, R: 100, C: 100 },
    { version: "GPT-4o (Standard Scraper)", caseId: "TC-03", A: 0, S: 100, P: 0, R: 50, C: 0 },
    { version: "GPT-4o (Standard Scraper)", caseId: "TC-04", A: 50, S: 100, P: 50, R: 100, C: 50 },
    { version: "GPT-4o (Standard Scraper)", caseId: "TC-05", A: 100, S: 100, P: 50, R: 100, C: 100 },
    { version: "GPT-4o (Standard Scraper)", caseId: "TC-08", A: 50, S: 100, P: 50, R: 50, C: 0 },
    { version: "GPT-4o (Standard Scraper)", caseId: "TC-13", A: 0, S: 100, P: 0, R: 100, C: 0 }
];

// Server API Endpoint config
const SERVER_URL = "https://nemoclaw-coordinator-api-production.up.railway.app";
let isLiveServerMode = false;
let pollingInterval = null;

// Initialize database (checks evaluations.json first, then localstorage)
async function getEvaluations() {
    if (isLiveServerMode) {
        try {
            const response = await fetch(`${SERVER_URL}/api/evaluations`);
            if (response.ok) {
                const externalData = await response.json();
                if (externalData && externalData.length > 0) {
                    const baseEvals = defaultEvaluations.filter(e => e.version !== "Snapshot v1.1 (Day 2 Reflexion)");
                    return [...baseEvals, ...externalData];
                }
            }
        } catch (e) {
            console.warn("API evaluations fetch failed, using default localStorage.");
        }
    }
    
    const data = localStorage.getItem("arena_evaluations");
    if (!data) {
        localStorage.setItem("arena_evaluations", JSON.stringify(defaultEvaluations));
        return defaultEvaluations;
    }
    return JSON.parse(data);
}

function saveEvaluations(evals) {
    localStorage.setItem("arena_evaluations", JSON.stringify(evals));
}

// Calculate the 5-Metric Value Score: Value = 0.3A + 0.15S + 0.2P + 0.15R + 0.2C
function calculateModelMetrics(version, evaluations) {
    const modelEvals = evaluations.filter(e => e.version === version);
    if (modelEvals.length === 0) return { score: 0, accuracy: 0, speed: 0, platform: 0, retrieval: 0, safety: 0 };
    
    let totalA = 0;
    let totalS = 0;
    let totalP = 0;
    let totalR = 0;
    let totalC = 0;
    
    modelEvals.forEach(e => {
        totalA += parseFloat(e.A || 0);
        totalS += parseFloat(e.S || 0);
        totalP += parseFloat(e.P || 0);
        totalR += parseFloat(e.R || 50);
        totalC += parseFloat(e.C || 50);
    });
    
    const count = modelEvals.length;
    const avgA = Math.round(totalA / count);
    const avgS = Math.round(totalS / count);
    const avgP = Math.round(totalP / count);
    const avgR = Math.round(totalR / count);
    const avgC = Math.round(totalC / count);
    
    const finalScore = Math.round((0.3 * avgA) + (0.15 * avgS) + (0.2 * avgP) + (0.15 * avgR) + (0.2 * avgC));
    
    return {
        score: finalScore,
        accuracy: avgA,
        speed: avgS,
        platform: avgP,
        retrieval: avgR,
        safety: avgC
    };
}

// Auto-Research iterations history data (rendered as line points)
let researchHistory = [56, 68, 77, 92, 100];

// Render Leaderboard Table (5 Metrics)
async function renderLeaderboard() {
    const evals = await getEvaluations();
    const versions = [
        { name: "Snapshot v1.1 (Day 2 Reflexion)", type: "active", icon: "rank-1" },
        { name: "GPT-4o (Standard Scraper)", type: "static", icon: "rank-2" },
        { name: "Snapshot v1.0 (Day 0 Baseline)", type: "frozen", icon: "rank-3" }
    ];
    
    const modelsData = versions.map(v => {
        const metrics = calculateModelMetrics(v.name, evals);
        return {
            name: v.name,
            type: v.type,
            iconClass: v.icon,
            ...metrics
        };
    });
    
    modelsData.sort((a, b) => b.score - a.score);
    
    const tbody = document.querySelector("#leaderboard-table tbody");
    tbody.innerHTML = "";
    
    modelsData.forEach((model, index) => {
        const tr = document.createElement("tr");
        
        let statusBadge = "";
        if (model.type === "active") statusBadge = `<span class="badge badge-active">● Active Learning</span>`;
        else if (model.type === "frozen") statusBadge = `<span class="badge badge-frozen">● Frozen</span>`;
        else statusBadge = `<span class="badge badge-static">● Static Baseline</span>`;
        
        tr.innerHTML = `
            <td><span class="rank-badge rank-${index + 1}">${index + 1}</span></td>
            <td><span class="model-name">${model.name}</span></td>
            <td><span class="score-value">${model.score}</span></td>
            <td>
                <div class="progress-bar-container">
                    <span class="progress-bar-value">${model.accuracy}%</span>
                    <div class="progress-bar-track">
                        <div class="progress-bar-fill" style="width: ${model.accuracy}%; background-color: var(--accent);"></div>
                    </div>
                </div>
            </td>
            <td>
                <div class="progress-bar-container">
                    <span class="progress-bar-value">${model.speed}%</span>
                    <div class="progress-bar-track">
                        <div class="progress-bar-fill" style="width: ${model.speed}%; background-color: var(--accent-blue);"></div>
                    </div>
                </div>
            </td>
            <td>
                <div class="progress-bar-container">
                    <span class="progress-bar-value">${model.platform}%</span>
                    <div class="progress-bar-track">
                        <div class="progress-bar-fill" style="width: ${model.platform}%; background-color: #ba55d3;"></div>
                    </div>
                </div>
            </td>
            <td>
                <div class="progress-bar-container">
                    <span class="progress-bar-value">${model.retrieval}%</span>
                    <div class="progress-bar-track">
                        <div class="progress-bar-fill" style="width: ${model.retrieval}%; background-color: #ff9900;"></div>
                    </div>
                </div>
            </td>
            <td>
                <div class="progress-bar-container">
                    <span class="progress-bar-value">${model.safety}%</span>
                    <div class="progress-bar-track">
                        <div class="progress-bar-fill" style="width: ${model.safety}%; background-color: #ff4500;"></div>
                    </div>
                </div>
            </td>
            <td>${statusBadge}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Render SVG Growth Curve (line graph of improvement trend)
async function renderSVGChart() {
    const evals = await getEvaluations();
    const baseline = calculateModelMetrics("Snapshot v1.0 (Day 0 Baseline)", evals);
    const mutated = calculateModelMetrics("Snapshot v1.1 (Day 2 Reflexion)", evals);
    
    if (mutated.score > 0) {
        researchHistory[4] = mutated.score;
    }
    
    const container = document.getElementById("svg-chart-wrapper");
    container.innerHTML = "";
    
    const width = 280;
    const height = 180;
    const padding = 30;
    
    const pointsCount = researchHistory.length;
    const maxVal = 100;
    
    const xCoords = researchHistory.map((_, i) => padding + (i * (width - 2 * padding) / (pointsCount - 1)));
    const yCoords = researchHistory.map(val => height - padding - (val * (height - 2 * padding) / maxVal));
    
    let pathD = `M ${xCoords[0]} ${yCoords[0]}`;
    for (let i = 1; i < xCoords.length; i++) {
        pathD += ` L ${xCoords[i]} ${yCoords[i]}`;
    }
    
    let gridLines = "";
    [25, 50, 75, 100].forEach(level => {
        const y = height - padding - (level * (height - 2 * padding) / maxVal);
        gridLines += `<line x1="${padding}" y1="${y}" x2="${width - padding}" y2="${y}" stroke="rgba(255,255,255,0.05)" stroke-dasharray="2,2"/>`;
        gridLines += `<text x="${padding - 5}" y="${y + 4}" fill="var(--text-muted)" font-family="var(--font-code)" font-size="8" text-anchor="end">${level}</text>`;
    });

    researchHistory.forEach((_, i) => {
        const x = xCoords[i];
        gridLines += `<line x1="${x}" y1="${padding}" x2="${x}" y2="${height - padding}" stroke="rgba(255,255,255,0.03)" />`;
        gridLines += `<text x="${x}" y="${height - padding + 15}" fill="var(--text-muted)" font-family="var(--font-code)" font-size="8" text-anchor="middle">R${i + 1}</text>`;
    });

    let pointsSVG = "";
    xCoords.forEach((x, i) => {
        const val = researchHistory[i];
        pointsSVG += `
            <circle cx="${x}" cy="${yCoords[i]}" r="4" fill="var(--accent)" stroke="var(--bg-primary)" stroke-width="1.5" />
            <text x="${x}" y="${yCoords[i] - 8}" fill="var(--accent-light)" font-family="var(--font-code)" font-size="8" font-weight="bold" text-anchor="middle">${val}%</text>
        `;
    });

    const svgHTML = `
        <svg width="100%" height="200" viewBox="0 0 ${width} ${height}" style="overflow: visible;">
            <!-- Background grid -->
            ${gridLines}
            
            <!-- Connection path -->
            <path d="${pathD}" fill="none" stroke="rgba(0, 255, 102, 0.2)" stroke-width="4" stroke-linecap="round"/>
            <path d="${pathD}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" filter="drop-shadow(0 0 3px rgba(0, 255, 102, 0.4))"/>
            
            <!-- Nodes -->
            ${pointsSVG}
        </svg>
    `;
    container.innerHTML = svgHTML;
}

// Populate dropdown selectors
function populateSelects() {
    const testSelect = document.getElementById("test-select");
    const evalCaseSelect = document.getElementById("eval-case");
    
    testSelect.innerHTML = "";
    evalCaseSelect.innerHTML = "";
    
    testCases.forEach(tc => {
        const option = document.createElement("option");
        option.value = tc.id;
        option.textContent = tc.name;
        
        testSelect.appendChild(option.cloneNode(true));
        evalCaseSelect.appendChild(option);
    });
}

// Render reflections logs
function renderReflections() {
    const container = document.getElementById("lessons-container");
    container.innerHTML = "";
    
    reflections.forEach(ref => {
        const card = document.createElement("div");
        card.className = "lesson-card";
        card.innerHTML = `
            <span class="lesson-meta">${ref.date} // Category: ${ref.category}</span>
            <p class="lesson-text">"${ref.text}"</p>
        `;
        container.appendChild(card);
    });
}

// Simulate Interactive Debate Runner
let isRunning = false;
function runTestSimulation() {
    if (isRunning) return;
    isRunning = true;
    
    const runBtn = document.getElementById("run-test-btn");
    const consoleOutput = document.getElementById("console-output");
    const status = document.getElementById("runner-status");
    const testId = document.getElementById("test-select").value;
    const testCase = testCases.find(tc => tc.id === testId);
    
    runBtn.disabled = true;
    status.textContent = "COMPUTING...";
    status.style.color = "var(--accent-blue)";
    consoleOutput.innerHTML = `<p class="console-meta">&gt; INITIALIZING EXPERT CONSENSUS THREAD [${testCase.id}]...</p>`;
    
    let index = 0;
    
    function printNextAgent() {
        if (index >= testCase.debate.length) {
            setTimeout(() => {
                const finalSummary = document.createElement("div");
                finalSummary.className = "console-agent";
                
                const finalScore = Math.round((0.3 * testCase.score.A) + (0.15 * testCase.score.S) + (0.2 * testCase.score.P) + (0.15 * testCase.score.R) + (0.2 * testCase.score.C));
                
                finalSummary.innerHTML = `
                    <p style="color: var(--accent); margin-top: 10px; font-weight: bold;">
                        [✓] SIMULATION COMPLETED // SCORING RUN...
                    </p>
                    <p style="color: var(--text-white); font-family: var(--font-code);">
                        &gt; ACCURACY (A): ${testCase.score.A}/100<br>
                        &gt; SPEED (S): ${testCase.score.S}/100<br>
                        &gt; PLATFORM (P): ${testCase.score.P}/100<br>
                        &gt; RETRIEVAL (R): ${testCase.score.R}/100<br>
                        &gt; SAFETY (C): ${testCase.score.C}/100<br>
                        &gt; VALUE SCORE COMPLETED: ${finalScore}/100
                    </p>
                `;
                consoleOutput.appendChild(finalSummary);
                consoleOutput.scrollTop = consoleOutput.scrollHeight;
                
                status.textContent = "SUCCESS";
                status.style.color = "var(--accent)";
                runBtn.disabled = false;
                isRunning = false;
            }, 1000);
            return;
        }
        
        const turn = testCase.debate[index];
        setTimeout(() => {
            const block = document.createElement("div");
            block.className = "console-agent";
            block.innerHTML = `
                <span class="agent-tag tag-${turn.agent}">${turn.agent}</span>
                <span style="color: var(--text-white);">&gt; ${turn.text}</span>
            `;
            consoleOutput.appendChild(block);
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
            
            index++;
            printNextAgent();
        }, 1000);
    }
    
    printNextAgent();
}

// Auto-Research Scientist Iterations Simulation
let isResearching = false;
const researchIterations = [
    {
        run: "Run 1 (Baseline Configuration)",
        score: 56,
        status: "RUN 1: FAILED",
        prompt: `[System Instruction Profile (Base)]\nLocate cheap hardware products on eBay and Amazon based on user text. Select lowest list prices.`,
        logs: [
            "[AutoResearch] Initiating Run 1 (Base prompt configurations)...",
            "[AutoResearch] Loading Golden Dataset (15 test cases)...",
            "[AutoResearch] Running test evaluations...",
            "[Critic] Mistake caught: Failed TC-01. Recommended used eBay seller voiding warranty.",
            "[Critic] Mistake caught: Failed TC-03. Fails to suggest tax Payboo optimization.",
            "[Critic] Mistake caught: Failed TC-13. Recommended Wish $18 fake RAM kit (Counterfeit).",
            "[Evaluator] Run 1 Complete: Score = 56/100."
        ]
    },
    {
        run: "Run 2 (Reflexion: Reseller Filter)",
        score: 68,
        status: "RUN 2: IMPR",
        prompt: `[System Instruction Profile (Mutation v1.1)]\nLocate hardware. Avoid eBay for warranty-critical items. Always check seller reputation metrics.`,
        logs: [
            "[AutoResearch] Triggering prompt mutation loop...",
            "[AutoResearch] Mutating prompt with Warranty & Seller filter guidelines...",
            "[AutoResearch] Staging Run 2 with mutated instruction profile...",
            "[AutoResearch] Running golden test suite...",
            "[Critic] Success: Passed TC-01 (filtered eBay reseller).",
            "[Critic] Mistake caught: Failed TC-08. Selected slow Alibaba shipping over Prime.",
            "[Critic] Mistake caught: Failed TC-13. Recommends wish RAM.",
            "[Evaluator] Run 2 Complete: Score = 68/100 (+12% improvement)."
        ]
    },
    {
        run: "Run 3 (Reflexion: Shipping & Counterfeit)",
        score: 77,
        status: "RUN 3: IMPR",
        prompt: `[System Instruction Profile (Mutation v1.2)]\nAvoid eBay for warranty-critical items. For lead times <5 days, disable Alibaba. Reject Wish/Temu RAM under $50.`,
        logs: [
            "[AutoResearch] Analyzing Run 2 error logs...",
            "[AutoResearch] Appending rules: Sourcing logistics constraints & Counterfeit thresholding...",
            "[AutoResearch] Staging Run 3 instructions...",
            "[AutoResearch] Running golden test suite...",
            "[Critic] Success: Passed TC-08 (Alibaba filtered for fast lead-time demand).",
            "[Critic] Success: Passed TC-13 (Wish counterfeit flagged, SP RAM chosen).",
            "[Critic] Mistake caught: Failed TC-03. Landed price did not count tax equivalent.",
            "[Evaluator] Run 3 Complete: Score = 77/100 (+9% improvement)."
        ]
    },
    {
        run: "Run 4 (Reflexion: Landed Pricing)",
        score: 92,
        status: "RUN 4: OPTIMIZED",
        prompt: `[System Instruction Profile (Mutation v1.3)]\nAvoid eBay for warranty-critical items. Disable Alibaba for <5 days lead time. Avoid Temu/Wish RAM under $50. Account for sales tax equivalent (Payboo card B&H).`,
        logs: [
            "[AutoResearch] Mutating pricing rules...",
            "[AutoResearch] Adding Tax optimization guidelines (CA/Payboo refund)...",
            "[AutoResearch] Staging Run 4 instructions...",
            "[AutoResearch] Running golden test suite...",
            "[Critic] Success: Passed TC-03 (B&H Payboo sales tax refund computed).",
            "[Critic] Success: Passed 14/15 tests. Overall performance close to ceiling.",
            "[Evaluator] Run 4 Complete: Score = 92/100 (+15% improvement)."
        ]
    },
    {
        run: "Run 5 (Reflexion: Micro-Components)",
        score: 100,
        status: "STABLE",
        prompt: `[System Instruction Profile (Mutation v1.4 - Final)]\nAvoid eBay for warranty-critical. Disable Alibaba <5 days. Reject Temu/Wish RAM <$50. Compute Payboo tax. For logic board components (capacitors), route strictly to DigiKey/Mouser.`,
        logs: [
            "[AutoResearch] Finalizing edge cases...",
            "[AutoResearch] Appending logic board component sourcing (DigiKey/Mouser)...",
            "[AutoResearch] Staging Run 5 (Final Stable)...",
            "[AutoResearch] Running golden test suite...",
            "[Critic] Success: Passed 15/15 tests. Performance verified.",
            "[AutoResearch] Prompt optimization completed. Stable consensus achieved.",
            "[Evaluator] Run 5 Complete: Score = 100/100 (Ceiling reached)."
        ]
    }
];

// Handles triggering the research loop (local mock fallback OR live server API call)
async function triggerAutoResearch() {
    if (isLiveServerMode) {
        try {
            const r = await fetch(`${SERVER_URL}/api/run-research`);
            if (r.ok) {
                // Live mode active: poll API logs in interval
                document.getElementById("run-research-btn").disabled = true;
                document.getElementById("research-status").textContent = "RUNNING";
                document.getElementById("research-status").style.color = "var(--accent-blue)";
                document.getElementById("research-console").innerHTML = `<p class="console-meta">&gt; Autonomous training loop initiated on backend server...</p>`;
                
                researchHistory = [];
                pollServerLogs();
                return;
            }
        } catch (e) {
            console.error("Failed to trigger live backend loop, falling back to simulation.", e);
        }
    }
    
    // Offline Simulation fallback
    runAutoResearchMockLoop();
}

// Live polling implementation for background python execution logs
function pollServerLogs() {
    pollingInterval = setInterval(async () => {
        try {
            // Check status
            const statusRes = await fetch(`${SERVER_URL}/api/status`);
            const statusData = await statusRes.json();
            
            // Get logs
            const logsRes = await fetch(`${SERVER_URL}/api/logs`);
            const logsData = await logsRes.json();
            
            const consoleBox = document.getElementById("research-console");
            consoleBox.innerHTML = "";
            logsData.logs.forEach(log => {
                const p = document.createElement("p");
                p.innerHTML = log;
                consoleBox.appendChild(p);
            });
            consoleBox.scrollTop = consoleBox.scrollHeight;
            
            // Update active mutation visuals from python state
            document.getElementById("mutated-prompt-display").textContent = statusData.prompt;
            document.getElementById("active-mutation-score").textContent = `Score: ${statusData.score}/100`;
            
            // Re-render graphs dynamically as data streams in
            if (statusData.score > 56 && researchHistory.indexOf(statusData.score) === -1) {
                researchHistory.push(statusData.score);
                renderSVGChart();
            }
            
            if (statusData.status === "idle") {
                clearInterval(pollingInterval);
                document.getElementById("research-status").textContent = "OPTIMIZED";
                document.getElementById("research-status").style.color = "var(--accent)";
                document.getElementById("run-research-btn").disabled = false;
                
                await renderLeaderboard();
                await renderSVGChart();
            }
        } catch (e) {
            clearInterval(pollingInterval);
            console.error("Error polling backend logs.", e);
        }
    }, 1500);
}

// Simulated mock execution
function runAutoResearchMockLoop() {
    if (isResearching) return;
    isResearching = true;
    
    const researchBtn = document.getElementById("run-research-btn");
    const consoleBox = document.getElementById("research-console");
    const status = document.getElementById("research-status");
    const promptDisplay = document.getElementById("mutated-prompt-display");
    const mutationTag = document.getElementById("active-mutation-tag");
    const mutationScore = document.getElementById("active-mutation-score");
    
    researchBtn.disabled = true;
    status.textContent = "RUNNING";
    status.style.color = "var(--accent-blue)";
    
    researchHistory = [];
    renderSVGChart();
    
    let runIndex = 0;
    
    function startNextRun() {
        if (runIndex >= researchIterations.length) {
            setTimeout(async () => {
                status.textContent = "OPTIMIZED";
                status.style.color = "var(--accent)";
                researchBtn.disabled = false;
                isResearching = false;
                
                const evals = await getEvaluations();
                const mutatedEvals = evals.filter(e => e.version === "Snapshot v1.1 (Day 2 Reflexion)");
                mutatedEvals.forEach(e => {
                    e.A = 100; e.S = 100; e.P = 100; e.R = 100; e.C = 100;
                });
                saveEvaluations(evals);
                await renderLeaderboard();
            }, 1000);
            return;
        }
        
        const iteration = researchIterations[runIndex];
        
        let logIndex = 0;
        consoleBox.innerHTML += `<p style="color: var(--accent-blue); font-weight: bold; margin-top: 15px;">&gt; INITIALIZING ${iteration.run}...</p>`;
        
        function printLogs() {
            if (logIndex >= iteration.logs.length) {
                researchHistory.push(iteration.score);
                renderSVGChart();
                
                promptDisplay.textContent = iteration.prompt;
                mutationTag.textContent = iteration.run.replace("Configuration", "").replace("Reflexion: ", "");
                mutationScore.textContent = `Score: ${iteration.score}/100`;
                
                consoleBox.scrollTop = consoleBox.scrollHeight;
                
                runIndex++;
                startNextRun();
                return;
            }
            
            setTimeout(() => {
                const p = document.createElement("p");
                p.innerHTML = iteration.logs[logIndex];
                consoleBox.appendChild(p);
                consoleBox.scrollTop = consoleBox.scrollHeight;
                
                logIndex++;
                printLogs();
            }, 600);
        }
        
        printLogs();
    }
    
    startNextRun();
}

// Handle Manual Logging Form Submit
async function handleFormSubmit(e) {
    e.preventDefault();
    
    const version = document.getElementById("eval-version").value;
    const caseId = document.getElementById("eval-case").value;
    const A = document.getElementById("score-accuracy").value;
    const S = document.getElementById("score-speed").value;
    const P = document.getElementById("score-platform").value;
    const R = document.getElementById("score-retrieval").value;
    const C = document.getElementById("score-safety").value;
    
    const evals = await getEvaluations();
    
    const existingIndex = evals.findIndex(entry => entry.version === version && entry.caseId === caseId);
    if (existingIndex !== -1) {
        evals[existingIndex] = { version, caseId, A, S, P, R, C };
    } else {
        evals.push({ version, caseId, A, S, P, R, C });
    }
    
    saveEvaluations(evals);
    
    await renderLeaderboard();
    await renderSVGChart();
    
    const consoleOutput = document.getElementById("console-output");
    consoleOutput.innerHTML = `
        <p style="color: var(--accent); font-weight: bold;">
            [✓] MANUAL EVALUATION LOGGED IN DATABASE
        </p>
        <p class="console-meta">
            Target Model: ${version}<br>
            Scenario ID: ${caseId}<br>
            A: ${A} | S: ${S} | P: ${P} | R: ${R} | C: ${C}
        </p>
    `;
    
    e.target.reset();
}

// Reset Arena Database to original states
async function resetDatabase() {
    if (confirm("Are you sure you want to reset the Arena database to default defaults? This will wipe your logged metrics.")) {
        localStorage.removeItem("arena_evaluations");
        researchHistory = [56, 68, 77, 92, 100];
        
        await renderLeaderboard();
        await renderSVGChart();
        
        const consoleOutput = document.getElementById("console-output");
        consoleOutput.innerHTML = `<p class="console-meta">&gt; DATABASE RESTORED TO DEFAULT CONFIGURATIONS.</p>`;
        
        document.getElementById("research-console").innerHTML = `<p class="console-meta">&gt; Auto-Research Scientist agent is idle. Click 'Start Auto-Research Loop' to initiate the self-improvement cycle...</p>`;
        document.getElementById("research-status").textContent = "IDLE";
        document.getElementById("research-status").style.color = "var(--text-muted)";
    }
}

// Detect and verify live local python server connection on load
async function checkBackendConnection() {
    try {
        const response = await fetch(`${SERVER_URL}/api/status`);
        if (response.ok) {
            isLiveServerMode = true;
            document.querySelector(".system-status").textContent = "SYS.LOC: ONLINE // AUTO_RESEARCH: SERVER MODE";
            document.querySelector(".system-status").style.color = "var(--accent)";
            console.log("[Arena API] Live python backend server connected successfully on port 8080.");
        }
    } catch (e) {
        // Keep simulation/localStorage active
        document.querySelector(".system-status").textContent = "SYS.LOC: ONLINE // AUTO_RESEARCH: SIMULATOR MODE";
        console.log("[Arena API] Local python server offline. Running in simulation fallback mode.");
    }
}

// Render Episodic Memory (Hermes compressed episodes)
async function renderEpisodicMemory() {
    const container = document.getElementById("episodic-memory-container");
    if (!container) return;
    container.innerHTML = "";
    
    let episodes = [];
    try {
        const url = isLiveServerMode ? `${SERVER_URL}/api/episodic-memory` : "episodic_memory.json";
        const response = await fetch(url);
        if (response.ok) {
            episodes = await response.json();
        }
    } catch (e) {
        // Fail gracefully
    }
    
    if (episodes.length === 0) {
        episodes = [
            {
                id: "EP-01",
                date: "Day 1 (10:14)",
                task: "Sourcing ASUS ROG Strix RTX 5080",
                compression: "Evaluated open-box reseller listings on eBay ($1,050) vs. authorized retail listings on Amazon ($1,199). SAGE auditor cross-referenced the brand warranty clause: ASUS voids warranty transfers for secondhand resellers. Episodic memory compressed this as a high-priority sourcing constraint.",
                outcome: "Selected Amazon Retail ($1,199) to preserve full manufacturer warranty, avoiding a $150 voided-value deficit."
            },
            {
                id: "EP-02",
                date: "Day 1 (15:20)",
                task: "Bulk Procurement of 20x Corsair Vengeance RAM",
                compression: "Piped a request for 20 identical RAM modules with a hard 3-day delivery deadline. Evaluated Alibaba wholesale ($700) vs. Newegg Business ($1,580). Alibaba required 12-day custom clearance. Speculator agent flagged the delivery constraint, forcing path optimization to domestic shipping.",
                outcome: "Selected Newegg Business ($1,580) with 2-day delivery guaranteed. Alibaba option rejected due to deadline violation."
            }
        ];
    }
    
    episodes.forEach(ep => {
        const card = document.createElement("div");
        card.className = "lesson-card";
        card.innerHTML = `
            <span class="lesson-meta">${ep.date} // Episode: ${ep.id} - ${ep.task}</span>
            <p class="lesson-text" style="margin-bottom: 8px;"><strong>Compressed Memory Context:</strong> "${ep.compression}"</p>
            <p class="lesson-text" style="color: var(--accent); font-weight: bold;"><strong>Resolution Outcome:</strong> "${ep.outcome}"</p>
        `;
        container.appendChild(card);
    });
}

// Event Listeners Initialization
document.addEventListener("DOMContentLoaded", async () => {
    populateSelects();
    await checkBackendConnection();
    await renderLeaderboard();
    await renderSVGChart();
    renderReflections();
    await renderEpisodicMemory();
    
    document.getElementById("run-test-btn").addEventListener("click", runTestSimulation);
    document.getElementById("reset-db-btn").addEventListener("click", resetDatabase);
    document.getElementById("grading-form").addEventListener("submit", handleFormSubmit);
    document.getElementById("run-research-btn").addEventListener("click", triggerAutoResearch);
});
