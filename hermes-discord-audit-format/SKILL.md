---
name: discord-commerce-audit
description: Present Hermes product research in a concise, source-verifiable Discord audit card.
---

# Discord commerce audit

Use this format for a product-search or deal-finding response in Discord.
It is deliberately compact, works in normal Discord Markdown, and is safe to
render as an embed by a Discord adapter.

```text
🔎 **HERMES E-Commerce Audit Report**
**Target:** <user's requested item and constraints>

**Recommended option — <Online | In-person / pickup>:** [<retailer — product title>](<direct verified URL when available>) — <price/condition>
<one-sentence reason it is the best option>

**Evidence**
• Price: <verified price or “not verified”>
• Availability: <in stock / backorder / unknown>
• Warranty / seller: <verified fact or “not verified”>
• Research basis: <database, web fallback, or both>

**Options**
1. **Online:** [<retailer — product title>](<direct verified URL>) — <price> — <short trade-off>
2. **In-person / pickup:** <retailer and location> — <price> — <availability or pickup limitation>

**Sources:** [<source 1>](<direct URL>) · [<source 2>](<direct URL>)

**Availability note:** <include any important online, pickup, or local
availability constraint.>
```

Rules:

- Every online option must have a direct, clickable URL. Omit an option rather
  than link to a homepage, search page, redirect, or unverified destination.
- Label every option as **Online** or **In-person / pickup**. Rank options by
  the user's criteria, regardless of purchase mode.
- Do not use synthetic numeric scores such as `100/100`. Describe the actual
  evidence, uncertainty, and trade-offs instead.
- Keep the response under 1,800 characters. If more detail is necessary, post
  the audit card first and follow it with a second message containing the
  remaining sourced options.
