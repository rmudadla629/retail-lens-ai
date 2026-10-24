# Data source and preparation

**Citation:** Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33

**Source:** https://archive.ics.uci.edu/dataset/352/online+retail

**License:** Creative Commons Attribution 4.0 International (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/

The dataset records transactions for a UK online retailer from 1 December 2010 through 9 December 2011. Prices are pounds sterling. This project is independent of UCI and the data creator.

## Adaptations

`scripts/prepare_data.py` downloads the official ZIP, reads the workbook and exports the full cleaned transaction table as Parquet. It also selects a deterministic 3,000-row raw CSV sample (seed 42) for demonstrating uploads. The raw workbook is not committed. The included data and sample remain under CC BY 4.0; the project code has an MIT license.

The full dataset is used; it is not synthetic and the dashboard is not restricted to the small upload sample.

1. Normalize strings and timestamps; parse prices and quantities.
2. Remove 5,268 exact duplicate rows. Removing duplicate-looking rows is a modeling choice; repeated lines could sometimes represent legitimate repeats.
3. Remove 2,512 rows with invalid fields, zero quantities, nonpositive prices, fractional quantities, or out-of-bounds numeric values. These exclusions follow deduplication.
4. Retain transactions without customer identifiers (132,565 cleaned lines). Missing IDs reduce the known-customer count, not sales totals.
5. Treat invoices beginning with C (case-insensitive) or negative quantities as return/cancellation lines. Store the absolute value of those lines as return_pence and subtract it from sales_pence to obtain net_pence. Refunds are not matched to original purchases.
6. Round unit prices to integer pence, then multiply by absolute integer quantity. This rounding rule means totals can differ from analyses that retain fractional-penny unit prices or use different exclusions.
7. Product rankings include StockCode matching five digits with optional letter suffixes. Administrative lines such as postage remain in total sales but not product rankings.

**Reconciliation:** 541,909 source rows − 5,268 duplicates − 2,512 invalid rows = 534,129 cleaned rows.

The archive SHA-256, exact date range, and audit counts are in `processed/quality.json`. Run `python scripts/prepare_data.py` to reproduce these outputs. The processed file is approximately 5 MB and is included so the deployed app starts without downloading or processing Excel.

## Required upload columns

| Column | Meaning |
|---|---|
| InvoiceNo | Invoice ID; prefix C denotes cancellation |
| StockCode | Product/administrative code |
| Description | Product description |
| Quantity | Signed integer units |
| InvoiceDate | Timestamp, preferably ISO 8601 |
| UnitPrice | Price in GBP; must be positive |
| CustomerID | Customer ID; may be blank |
| Country | Customer country; blanks become Unknown country |

No costs, profit, customer-acquisition spend, or verified churn labels are supplied. Do not interpret this dataset as evidence of profitability or causal customer behavior.

## USD display and exports

The source workbook, upload sample, and `processed/retail.parquet` retain GBP values. The app derives `sales_cents_usd`, `return_cents_usd`, and `net_cents_usd` using the fixed closing-date rate in `fx_rate.json`: 1 GBP = 1.5688 USD on 2011-12-09. Each GBP line amount converts to USD cents with Decimal ROUND_HALF_UP, then aggregates. This is a fixed-reference USD restatement, not historical daily FX conversion.

The explorer and filtered CSV show `UnitPrice_USD`, `GrossSales_USD`, `Returns_USD`, `NetSales_USD`, `Currency`, `GBP_to_USD_rate`, and `FX_reference_date`; source amounts are kept in the original dataset for audit rather than overwritten. Input CSV unit prices must still be GBP. Displayed unit prices are rounded separately and may not reproduce the converted line amount when multiplied by quantity.

Rate source: https://api.frankfurter.dev/v1/2011-12-09?base=GBP&symbols=USD . USD results reproduce offline from this saved rate; no live currency API is called when the app runs.
