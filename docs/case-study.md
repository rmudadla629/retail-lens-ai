# Retail Lens AI: portfolio case study

## Business question

How can an analyst turn retail transactions into a useful sales overview, identify merchandise and market concentration, and let a stakeholder ask natural-language questions while keeping calculations inspectable?

## Approach

The project uses the full UCI Online Retail dataset. Python cleans the transactions and documents exclusions. Pandas and SQLite independently reconcile totals. Plotly supports interactive exploration; Streamlit connects filters, uploads, data tables, and AI questions. The default provider is Groq, with Gemini and OpenAI as optional alternatives.

The AI does two jobs: translate a question into a constrained analysis plan, then explain the computed evidence. Python owns every calculation. The model cannot execute code or SQL. A separate guided mode works without any API key and is explicitly labeled as non-AI.

## Findings on the bundled dataset

| Measure | Result |
|---|---:|
| Cleaned transaction lines | 534,129 |
| Gross sales | $16,695,281.58 |
| Returns/cancellation value | $1,402,473.81 |
| Net sales | $15,292,807.77 |
| Distinct purchase invoices | 19,960 |
| Known purchasing customers | 4,338 |
| Gross average order value | $836.44 |
| Cancellation value / gross sales | 8.40% |

- The United Kingdom contributes 84.01% of net sales. International expansion may warrant investigation, but revenue alone cannot establish which market is profitable.
- November 2011 has the highest observed monthly net sales ($2,284,394.92). This is an observed historical peak, not evidence of a causal seasonal effect.
- REGENCY CAKESTAND 3 TIER leads merchandise descriptions by net sales ($258,001.10). Postage and administrative codes are excluded from merchandise rankings.
- Lines without customer identifiers contribute about 15.08% of net sales. Dropping them would materially change the revenue story.

The app can recalculate these results for a date/country selection. SQL outputs are in `docs/sql-results.txt`.

## Practical next steps for a business

Investigate cancellation-heavy products, inspect country concentration, and obtain product cost and marketing spend before making profitability or investment decisions. Compare complete periods rather than treating the truncated December 2011 as a full month.

## Limits and choices to explain in an interview

- Exact duplicate removal can eliminate legitimate repeated lines; the choice is explicit and reproducible.
- Cancellation value is a transaction-based proxy, not a matched refund ledger.
- Unit prices round to pence before quantity multiplication.
- The source ends on 9 December 2011. Boundary months and user-selected ranges can be incomplete.
- Product-level distinct invoice counts overlap and must not be summed as total orders.
- AI interpretations need review; the evidence panel exposes the plan, formulas, filters, and results.

## Suggested 60-second demonstration

1. Show the full-data KPIs and the colorful overview.
2. Filter to France and show that charts and KPIs change together.
3. Open Products & markets and rank products by cancellation value.
4. Open Ask AI and ask “Which products lead net sales?”
5. Expand the calculation and evidence panel.
6. Open Method & quality to explain the duplicate and missing-customer choices.

## Resume wording

Built a Python/Streamlit retail analytics app using 541K source transactions, interactive Plotly dashboards, SQL reconciliation, and an optional Groq-backed AI analysis workflow that executes validated analysis plans and exposes calculated evidence.

Avoid claiming business savings, ROI, or live AI evaluation results that have not been measured.

## USD presentation

All dashboard monetary amounts, AI evidence, filtered exports, and SQL results use USD equivalents. The original UK transactions remain GBP in the source Parquet. A fixed closing-date reference rate of **1 GBP = 1.5688 USD (2011-12-09)** is stored in `data/fx_rate.json`. Source: [Frankfurter historical rate](https://api.frankfurter.dev/v1/2011-12-09?base=GBP&symbols=USD). Each sales/cancellation line converts to cents with decimal half-up rounding before aggregation, so summing exported lines reconciles with the dashboard. This is a reproducible restatement, not transaction-date conversion or current-dollar purchasing power. Row rounding can differ from multiplying a final GBP total by the rate. Unit prices are rounded separately for display. Original GBP findings remain in `data/processed/findings.json`; USD findings are in `data/processed/findings_usd.json`.
