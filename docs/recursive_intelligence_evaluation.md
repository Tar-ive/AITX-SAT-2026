# Recursive Intelligence Evaluation & Snapshot Benchmark Plan

This document outlines the testing methodology, evaluation criteria, and demo-driven execution plan for competing in the **Recursive Intelligence Track** at the hackathon.

---

## 1. The Mathematical Value Function

To prove that the agent is recursively improving over a 48-hour period, we evaluate its performance using a compressed score between 0 and 100:

$$\text{Value} = w_1 \cdot \text{Accuracy} + w_2 \cdot \text{Speed} + w_3 \cdot \text{Platform}$$

### Weight Allocations (Balanced Profile):
*   $w_1 = 0.5$ (Accuracy: prioritizing exact landed price calculations over sticker prices).
*   $w_2 = 0.2$ (Speed: time elapsed between live price drops and bot triggers).
*   $w_3 = 0.3$ (Platform Intelligence: selecting the ideal commerce category).

### Component Scoring Rubrics:

#### A. Accuracy Score ($A$) — Max 100 points
This measures the difference between the Agent's reported price and the true Landed Price (including shipping and hidden checkout fees).
*   If Price Error $\leq 1\%$: $100\text{ points}$
*   If Price Error $\leq 10\%$: $50\text{ points}$
*   If Price Error $> 10\%$: $0\text{ points}$

#### B. Speed Score ($S$) — Max 100 points
This measures how long the agent takes to detect a live price change on monitored listings.
*   Detection within 5 mins of change: $100\text{ points}$
*   Detection within 1 hour of change: $50\text{ points}$
*   Detection $> 1\text{ hour}$ or missed: $0\text{ points}$

#### C. Platform Intelligence Score ($P$) — Max 100 points
This tests if the agent targets the correct marketplace type based on the user's implicit intent (Warranty/New vs. Used/Liquidated vs. Bulk Sourcing).
*   Matches the ideal platform category exactly: $100\text{ points}$
*   Finds the item but on a sub-optimal platform type: $50\text{ points}$
*   Fails to find the item or selects a nonsensical platform: $0\text{ points}$

---

## 2. 15-Question Hardware Sourcing Benchmark (Golden Dataset)

These 15 test cases are run against the agent at **Day 0 (Base)** and **Day 2 (Post-Learning)** to calculate the delta improvement.

### Category A: The "New & Warranty-Critical" Vector
1.  **Test Case 1 (ASUS ROG Strix RTX 5080):** 
    *   *Prompt:* "I need a brand-new, factory-sealed ASUS ROG Strix RTX 5080 with a full manufacturer warranty. Shipped by this weekend."
    *   *Ideal Platform:* Amazon (shipped/sold by Amazon), Newegg, or Best Buy.
    *   *Failure Mode:* Recommending an unauthorized third-party reseller on eBay.
2.  **Test Case 2 (M4 MacBook Pro 14-inch):** 
    *   *Prompt:* "Find the best price on a brand-new M4 MacBook Pro 14-inch. I intend to buy AppleCare+ for it, so it must be an eligible retail unit."
    *   *Ideal Platform:* Apple Store, Amazon (Authorized), or Best Buy.
    *   *Failure Mode:* Recommending Swappa or generic refurbished outlets.
3.  **Test Case 3 (Tax-Optimization):** 
    *   *Prompt:* "I want to buy a brand-new RTX 5090. I live in California and want to legally avoid or minimize upfront state sales tax if an authorized retailer offers a workaround."
    *   *Ideal Platform:* B&H Photo Video (using their Payboo credit card tax-equivalent refund).
    *   *Failure Mode:* Pointing to standard retail channels that collect upfront tax.

### Category B: The "Secondhand & Grading" Vector
4.  **Test Case 4 (Near-Mint Open Box MacBook):** 
    *   *Prompt:* "I want an M3 MacBook Air. I don't want a heavily used one, just a customer return or open-box unit that still has 10+ months of original Apple warranty left."
    *   *Ideal Platform:* Best Buy Open-Box (Excellent) or Apple Certified Refurbished.
    *   *Failure Mode:* Pointing to peer-to-peer eBay auctions.
5.  **Test Case 5 (Certified Refurbished Workstation):** 
    *   *Prompt:* "We need 5 refurbished M2 MacBook Pros for our new interns. They must come with a verified 1-year functional warranty so our IT team doesn't have to troubleshoot them."
    *   *Ideal Platform:* Amazon Renewed (Excellent/Premium) or Back Market.
    *   *Failure Mode:* Individual unverified sellers on Craigslist/eBay.
6.  **Test Case 6 (As-Is Parts GPU):** 
    *   *Prompt:* "I'm looking for a broken or 'for parts' RTX 3080. I want to harvest the cooling shroud and fans to fix my own card. Price must be under $100."
    *   *Ideal Platform:* eBay (Filtered by condition: "For parts or not working").
    *   *Failure Mode:* Searching Amazon or Newegg.
7.  **Test Case 7 (Direct Peer-to-Peer Verified):** 
    *   *Prompt:* "I want a used RTX 4070 Ti, but I want to see actual timestamped photos of the card running a benchmark from a trusted individual seller, not a liquidator."
    *   *Ideal Platform:* Swappa or r/hardwareswap.
    *   *Failure Mode:* Linking to standard bulk refurbishers using stock images.

### Category C: The "Bulk Sourcing & Lead Time" Vector
8.  **Test Case 8 (Immediate System-Builder Rush):** 
    *   *Prompt:* "We are building 20 custom gaming PCs for a LAN center. We need 20 identical kits of Corsair Vengeance 32GB RAM. They must arrive within 3 days or we miss our opening deadline."
    *   *Ideal Platform:* Amazon Business (with Prime) or Newegg Business.
    *   *Failure Mode:* Sourcing from Alibaba/AliExpress (which take 10-20 days).
9.  **Test Case 9 (Deep-Discount Bulk Sourcing):** 
    *   *Prompt:* "We are opening an AI rental cluster. We need to buy 100 units of generic, unbranded DDR5 server ECC RAM modules. Lead time doesn't matter; lowest factory-direct price per unit."
    *   *Ideal Platform:* Alibaba or Global Sources (direct from manufacturer).
    *   *Failure Mode:* Recommending consumer retail outlets.
10. **Test Case 10 (High-Risk Escrow Bulk Order):** 
    *   *Prompt:* "I want to buy 10 budget RX 580 GPUs to build low-end emulation machines. Cheap, but with escrow buyer protection so the seller doesn't ghost me with my money."
    *   *Ideal Platform:* AliExpress (escrow protection for small-scale bulk imports).
    *   *Failure Mode:* Direct wire transfer via Alibaba.

### Category D: The "Niche, Legacy & Scams" Vector
11. **Test Case 11 (Legacy Motherboard Sourcing):** 
    *   *Prompt:* "Our legacy office file server needs a replacement motherboard that supports an ancient Intel Core 4th-gen processor. Where can I find one?"
    *   *Ideal Platform:* eBay or legacy PC liquidators (like ServerMonkey).
    *   *Failure Mode:* Searching Best Buy or standard retail.
12. **Test Case 12 (Regional Pricing Arbitrage):** 
    *   *Prompt:* "I want to buy a bulk lot of 50 pulled/used Samsung RAM chips from decommissioned data centers. These are usually liquidated heavily in Asian tech hubs. Where should I look?"
    *   *Ideal Platform:* Taobao or AliExpress.
    *   *Failure Mode:* Searching local retail stores.
13. **Test Case 13 (Wish/Temu Counterfeit Protection):** 
    *   *Prompt:* "Find me the absolute cheapest 64GB DDR5 desktop RAM kit on the internet. I don't care where it comes from."
    *   *Ideal Platform:* Recommends cheapest authorized source with a flag warning the user *against* $15 counterfeit listings on Temu/Wish.
    *   *Failure Mode:* Recommending a counterfeit $15 RAM stick because it has the lowest price.
14. **Test Case 14 (Best Buy Price Matching):** 
    *   *Prompt:* "I see a price drop on a MacBook Pro at an unauthorized store, but I want to buy it from Best Buy because I have a store credit card there. Does Best Buy price-match them?"
    *   *Ideal Platform:* Best Buy (Checks Best Buy's official competitor match list).
    *   *Failure Mode:* Answering "Yes" blindly without policy checking.
15. **Test Case 15 (Micro-Component Sourcing):** 
    *   *Prompt:* "I'm soldering a broken MacBook logic board and I need 50 pieces of a specific replacement SMD capacitor (0402 size, 10uF). Where do I buy these?"
    *   *Ideal Platform:* DigiKey, Mouser Electronics, or Newark.
    *   *Failure Mode:* Overpriced retail multi-packs on Amazon.

---

## 3. The 48-Hour Learning & Reflection Loop

1.  **Day 0 (Snapshot v1.0 - Base):** The agent runs the 15-question benchmark. Performance is scored by an LLM-as-a-Judge using the Value Function formula. Result is recorded as the **Baseline**.
2.  **Interactive Training Phase:** As the developer interacts with the agent in Discord over the 2-day period, mistakes are flagged. When the user corrects a path (e.g. explaining why B&H Payboo is better for tax optimization than Amazon), the agent's **Critic (Sage)** intercepts:
    *   It generates a self-reflection prompt detailing the mistake.
    *   It extracts the general rule and appends it to `docs/memory_buffer.txt`.
3.  **Day 2 (Snapshot v1.1 - Mutated):** The agent is re-evaluated on the exact same 15 questions. The system prompt incorporates `docs/memory_buffer.txt`.

---

## 4. Visualizing the Demo in Discord

### The `/benchmark` Command
When invoked, the bot runs the test suite and prints a formatted summary comparing the snapshots:

```
📊 HACKATHON BENCHMARK SCORECARD: RECURSIVE INTELLIGENCE
------------------------------------------------------------
[Snapshot v1.0 - Day 0]     [■■■■■■□□□□] 56/100 Points
[Snapshot v1.1 - Day 2]     [■■■■■■■■■□] 88/100 Points (+32%)

📈 Metric Deltas:
• Landed Price Accuracy:  v1.0: 60%  -->  v1.1: 96% (+36%)
• Platform Intelligence:  v1.0: 50%  -->  v1.1: 80% (+30%)
• False Positive Rate:   v1.0: 30%  -->  v1.1: 5%  (-25%)

🧠 Accumulated Rules (docs/memory_buffer.txt):
1. "Escrow guarantees are mandatory for bulk Emulation GPU kits."
2. "New MacBook Pro buyers seeking AppleCare must bypass Swappa."
3. " Digikey handles Logic Board capacitors; ignore retail overlays."
```
