"""Reproducible USD view; original GBP values are never overwritten."""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import json

FX = json.loads((Path(__file__).resolve().parents[1] / 'data/fx_rate.json').read_text())


def usd_view(df):
    result = df.copy()
    rate = Decimal(FX['rate'])
    for source, target in [('sales_pence','sales_cents_usd'), ('return_pence','return_cents_usd')]:
        # Decimal arithmetic avoids float rounding and multiplication overflow.
        values = {int(v): int((Decimal(int(v)) * rate).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
                  for v in result[source].unique()}
        result[target] = result[source].map(values).astype('int64')
    result['net_cents_usd'] = result['sales_cents_usd'] - result['return_cents_usd']
    return result


def usd_export(df):
    out = df.drop(columns=['UnitPrice','sales_pence','return_pence','net_pence',
                           'sales_cents_usd','return_cents_usd','net_cents_usd']).copy()
    rate = Decimal(FX['rate'])
    prices = {v: float((Decimal(str(v)) * rate).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
              for v in df['UnitPrice'].unique()}
    out['UnitPrice_USD'] = df['UnitPrice'].map(prices)
    out['GrossSales_USD'] = df['sales_cents_usd'] / 100
    out['Returns_USD'] = df['return_cents_usd'] / 100
    out['NetSales_USD'] = df['net_cents_usd'] / 100
    out['Currency'] = 'USD'
    out['GBP_to_USD_rate'] = FX['rate']
    out['FX_reference_date'] = FX['date']
    return out
