# Recursive Intelligence Evaluation

This is the evaluation contract for the running EC2 AutoResearch loops, the
Supabase experiment registry, the Evals UI, and Discord `#eval`.

---

## 1. The Mathematical Value Function

The original hackathon score compresses a run to 0–100:

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

The live Evals UI preserves the five underlying measurements instead of hiding
them inside one composite:

1. Decision quality
2. Seconds per answer
3. Prompt injection risk
4. Hermes episodic-memory diff lines
5. Agent knowledge regression

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

## 3. Continuous AutoResearch

Two real loops feed the same Supabase registry:

- `cursor-karpathy` runs branch → mutate → evaluate → merge/revert experiments.
- `autoresearch-v2` re-evaluates champion and candidate on the same cases each
  cycle so provider noise largely cancels.

The v2 loop reads accepted hypotheses from Supabase, measures real answer time,
stores every candidate, and promotes only when the paired decision-quality
margin is at least `+0.01` with at least 80% valid case coverage. The general
boundaries in `autoresearch/improvement-boundaries.json` additionally require:

- decision quality gain of at least `0.005`;
- no prompt-injection-risk increase;
- zero knowledge regression;
- seconds per answer no worse than `1.3×` the champion.

A candidate that fails remains visible as negative research evidence. It does
not move the champion line.

## 4. Hash write and promotion provenance

`autoresearch/scripts/promote_to_soul.py` makes memory promotion idempotent:

1. Normalize every promoted lesson.
2. Hash each normalized line with SHA-256 and keep a 12-character content ID.
3. Union new hashes with the latest Hermes SOUL; rerunning cannot duplicate a
   lesson.
4. Write a new version to `public.agent_soul`.
5. Store the experiment ID and Git ref in the SOUL summary.

This gives each promoted memory change three identities: experiment ID, Git
commit, and content hash. The Evals API exposes the latest SOUL version,
diff-line count, and Git hash. Hovering the Memory Audit or Promote Harness card
shows that provenance in the methodology circle.

## 5. Prompt-injection evaluation

The promotion scan is defense in depth:

- HiddenLayer analyzes the model interaction for prompt injection.
- Policy checks detect malicious listing instructions.
- OpenShell enforces the outbound network allowlist even if the model complies.

The combined metric is stored as prompt-injection risk. A missing scan stays
unmeasured; it is never silently converted into a passing value.

## 6. Discord `#eval`

`#eval` is a Discord forum, so each report is a titled thread rather than a
plain channel message. After a promotion, and at configured checkpoints, the
loop posts:

- experiment and decision;
- all five metrics and deltas;
- promoted, held, or rolled-back state;
- hypothesis and evidence summary.

Human replies remain attached to that evaluation and become evidence for later
cycles. Credentials are not written to the post.

## 7. Real-data UI and caching

The Evals UI reads timestamped rows from `public.harness_experiments`,
`public.agent_soul`, and, when present, `public.evaluation_samples`.

- The initial endpoint returns graph summaries only.
- Detailed rollout samples load when the evidence drawer is opened.
- A 45-second process cache prevents repeated Supabase queries.
- Vercel receives `s-maxage=45, stale-while-revalidate=300`.
- The browser renders its last verified payload immediately, then refreshes in
  the background.

Charts show every evaluated candidate as a gray point and only accepted
experiments as the green champion staircase. This prevents rejected experiments
from looking like improvements.
