# Recursive self-improvement video brief

You are a senior motion designer and data-visualization engineer. Build a deterministic, code-rendered Remotion video from the attached CSV.

## Inputs

- Project: `{{PROJECT_NAME}}`
- Results CSV: `{{CSV_PATH}}`
- Teacher: `{{TEACHER_MODEL}}`
- Output: `{{OUTPUT_PATH}}`

The CSV is the only numerical source of truth. Never invent, smooth, reorder, or silently repair a value. Validate it first and stop with a precise error if a required field is missing or invalid.

## Deliverable

Create a 1080×1080, 30 fps, 40-second MP4 plus the Remotion source, a parsed `story.json`, and stills at 0, 8, 16, 24, 32, and 39 seconds. Use vector text and charts so every number remains exact and legible.

## Data rules

- One row is one evaluated policy candidate.
- `accepted=true` means the candidate became a champion.
- `accepted=false` means it was evaluated and rejected.
- `baseline=true` identifies the starting champion.
- `current=true` identifies the final champion.
- Draw every candidate as a point; only accepted rows advance the staircase.
- Use all accepted rows in the final leaderboard.
- Compare each metric with the baseline. Higher is better only for decision quality and valid URL rate.
- Display `±` confidence intervals exactly as provided.
- If `evidence_status=illustrative`, show an “Illustrative data” badge throughout. Otherwise show “Measured Verifiers run”.

## Storyboard

1. **0–6s — The problem:** “The best price is not any price. Buy at the right price without waiting forever.”
2. **6–13s — Overnight search:** animate candidates branching from the current champion; label the teacher and the 12:00–7:00 AM window.
3. **13–21s — Verification:** show retrieval, URL, claim, landed-price, latency, and forecast checks. Rejected candidates fade; accepted candidates glow.
4. **21–29s — Recursive improvement:** animate decision quality as a champion staircase. Overlay rejected candidates as muted points.
5. **29–37s — Evidence:** reveal the dynamic leaderboard with exact values and confidence intervals.
6. **37–40s — Result:** hold on the current champion, its change from baseline, and “Improve the policy. Re-run the same tests. Promote only verified gains.”

## Visual direction

Editorial research-lab aesthetic: warm off-white canvas, charcoal typography, fine grid lines, coral for the active champion, green for verified improvement, red for regression, gray for rejected candidates. Use restrained motion, clean number transitions, and no stock footage.

## Required checks before rendering

Print a data audit containing row count, accepted count, baseline/current IDs, metric ranges, and any missing values. After rendering, compare the six stills with `story.json` and confirm that all displayed numbers match the CSV.
