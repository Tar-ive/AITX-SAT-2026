# Sage: a Self-Improving Review Judge ("soft RL")

Design + research notes for an agent that gets measurably better at judging
eBay/Amazon reviews (good vs. bad vs. fake) every time users interact with it,
**without retraining model weights**.

## 1. What "soft RL" means here — and its academic name

The mechanism the team described — grade each interaction, remember what was
good/bad, use that memory to act better next time — is **verbal
reinforcement learning**, introduced by
[Reflexion (Shinn et al., 2023)](https://arxiv.org/pdf/2303.11366):

- **Actor**: the agent answers a review-judgment or GPU-price question.
- **Evaluator**: produces a reward signal for that episode (below).
- **Self-reflection**: the agent writes a short lesson ("I trusted a
  5-star burst from 1-day-old accounts; the listing was a scam → weight
  account age") which is appended to a persistent memory buffer.
- Next episode, relevant lessons are retrieved into context. Reflexion
  reached 91% pass@1 on HumanEval this way vs. GPT-4's 80% — no fine-tuning.

So the "policy update" is: **memory grows and is periodically distilled into
the agent's standing instructions.** Weights never change; behavior does.

## 2. Reward signal (what counts as good vs. bad)

| Signal | Source | Weight |
|---|---|---|
| Explicit human feedback | 👍/👎 reaction on Sage's Discord verdicts | high |
| Outcome | user proceeded with a listing Sage cleared and didn't report a problem / user rejected a listing Sage cleared | high, delayed |
| Benchmark score | frozen labeled datasets (§4) re-run after every batch | authoritative for *learning*, see §5 |
| Consistency | Sage contradicting its own earlier verdict on the same evidence | negative |

Policy for memory admission (prevents junk learning):
1. A lesson enters memory only with an attached reward event, never from
   Sage's own unaudited opinion.
2. Lessons are *generalizations* ("review bursts within 48h are suspect"),
   never memorized answers to benchmark items — that's leakage (§5).
3. Contradictory lessons trigger a reconciliation pass (LLM merges or drops).
4. Memory is versioned (git). Every benchmark run records the memory version,
   so the learning curve is reproducible and reversible.

## 3. What the research says about fake-review cues (seed knowledge)

Rather than starting from zero, Sage's initial instruction set is distilled
from the literature the user guessed exists — it does:

- Classic linguistic-cue work: deceptive reviews over-use superlatives and
  first-person, under-use spatial detail
  ([Ott et al.'s deceptive opinion spam line of work](https://www.researchgate.net/publication/290078110_Negative_Deceptive_Opinion_Spam);
  [survey](https://www.cambridge.org/core/journals/knowledge-engineering-review/article/recent-stateoftheart-of-fake-review-detection-a-comprehensive-review/F02E8339C43A62BA63EBD54A1608F785)).
- **Critical 2025 finding:** LLM-written fake reviews are now essentially
  indistinguishable from genuine ones by text alone, for both humans and
  machine detectors
  ([Large Language Models as "Hidden Persuaders"](https://arxiv.org/pdf/2506.13313)).
- Consequently, modern systems lean on **behavioral/metadata signals** —
  reviewer account age, review-burst timing, rating distribution vs. text
  sentiment mismatch, cross-product duplication, seller history — often via
  graph methods, and on **evidence-grounded adjudication** (retrieve
  corroborating facts before judging), e.g.
  [JARVIS](https://arxiv.org/pdf/2602.12941) and
  [leakage-free multi-model detection frameworks](https://www.researchgate.net/publication/397106930_Detecting_LLM-Generated_Fake_Reviews_A_Leakage-Free_Multi-Model_Framework).

Design consequence: **Sage judges (text + metadata + seller context)
tuples, not prose alone.** On eBay that means: seller feedback %, feedback
count, account age, price vs. market median, review timing pattern —
exactly the fields Inspector already extracts.

## 4. Benchmarks (the "actual validation" the user asked for)

Frozen, labeled, public — Sage is *never* allowed to store these items in memory:

| Dataset | Contents | Labels | Use |
|---|---|---|---|
| **Ott / OpSpam deceptive opinion corpus** | 1,600 hotel reviews (800 truthful TripAdvisor / 800 elicited deceptive) | gold (constructed) | text-cue sanity check; the field's classic benchmark |
| **YelpChi** (+ YelpNYC/YelpZip, Rayana & Akoglu) | Chicago restaurant/hotel reviews | Yelp filter = pseudo-labels, includes reviewer metadata | metadata+text judging at scale |
| **Amazon labeled review set** | ~21k items, 30 categories | platform-identified true/false | product-domain transfer (closest to GPU listings) |
| **AI-generated era sets: GPTARD / ARED** ([AI-generated fake review detection, 2026](https://www.sciencedirect.com/science/article/abs/pii/S0167923626000175)) | human vs. LLM-generated product reviews | generated-by-construction | the hard modern case |
| **Custom eBay-GPU eval set (build ourselves)** | ~100 real GPU listings + reviews, hand-labeled by us | our labels | the distribution we actually care about |

Split each into a small **dev slice** (lessons may be *derived* from mistakes
here) and a locked **test slice** (never shown to Sage outside evaluation).

## 5. Validation protocol — proving improvement, honestly

1. **Baseline (version 0):** run Sage with empty memory on every test slice.
   Record accuracy, macro-F1, AUC, and calibration (does "80% sure fake"
   mean 80%?).
2. **Cadence:** after every N=25 real user interactions (or weekly), snapshot
   memory → version k, re-run all benchmarks with temperature 0, 3 repeats.
3. **Learning curve:** plot metric vs. memory version. Improvement claim
   requires statistical significance (McNemar's test on paired predictions,
   p < 0.05) — not just a higher number.
4. **Leakage guard:** memory is grep-audited against benchmark texts before
   every run; any overlap → lesson quarantined. (This is the failure mode
   that produces fake "improvement.")
5. **Ablation (the soft-RL proof):** same model, same date, memory ON vs.
   memory OFF. The delta *is* the learning. Publish both numbers.
6. **Regression rule:** if version k drops > 2 F1 points on any benchmark,
   auto-rollback to version k-1 (memory is git-versioned, so this is one revert).
7. **Report:** a one-page scorecard per version committed to this repo
   (`benchmarks/results/vK.md`) — date, memory version, per-dataset metrics,
   significance, notable new lessons.

## 6. Where Sage fits the team

Sage subscribes to #gpu-desk. When Inspector posts listing + review data,
Sage attaches a verdict block: `{fake_risk: low|med|high, top_reasons: [...],
confidence: 0.xx}`. Concierge includes the verdict when asking the user.
User reactions and outcomes flow back as rewards (§2). Sage never
recommends buying — it only judges evidence (role enforcement per the
companion architecture doc).

## 7. Honest limitations

- Yelp/Amazon labels are platform-filter *pseudo*-labels, not ground truth —
  report them as such.
- Text-only detection of 2025-era LLM fakes is near chance; expected gains
  come from metadata + evidence grounding, so benchmarks that are text-only
  (Ott) measure only part of Sage's job.
- Verbal-RL gains plateau; if the learning curve flattens for 3+ versions,
  next step is preference fine-tuning (DPO) on the accumulated reward data —
  requires a locally hosted model, out of scope for the current NVIDIA
  Endpoints setup.

## References

- Reflexion: Shinn et al., 2023 — https://arxiv.org/pdf/2303.11366
- Hidden Persuaders (LLM fake reviews indistinguishable) — https://arxiv.org/pdf/2506.13313
- JARVIS evidence-grounded review adjudication — https://arxiv.org/pdf/2602.12941
- Fake review detection survey (Cambridge KER) — https://www.cambridge.org/core/journals/knowledge-engineering-review/article/recent-stateoftheart-of-fake-review-detection-a-comprehensive-review/F02E8339C43A62BA63EBD54A1608F785
- Fake Review Detection: Taxonomies, Benchmarks, Intent Modeling — https://www.researchgate.net/publication/392230678_Fake_Review_Detection_Taxonomies_Benchmarks_and_Intent_Modeling_Frameworks
- Negative Deceptive Opinion Spam (Ott et al. line) — https://www.researchgate.net/publication/290078110_Negative_Deceptive_Opinion_Spam
- AI-generated fake review detection (GPTARD/ARED) — https://www.sciencedirect.com/science/article/abs/pii/S0167923626000175
- Leakage-free LLM fake-review detection framework — https://www.researchgate.net/publication/397106930_Detecting_LLM-Generated_Fake_Reviews_A_Leakage-Free_Multi-Model_Framework
- MultiAgentBench — https://www.researchgate.net/publication/394298482_MultiAgentBench_Evaluating_the_Collaboration_and_Competition_of_LLM_agents
- LLM-Coordination benchmark (NAACL 2025) — https://github.com/eric-ai-lab/llm_coordination
- Reflexion explainer — https://www.promptingguide.ai/techniques/reflexion
