"""Deterministic retail analytics; the model never executes Python or SQL."""
from __future__ import annotations

import pandas as pd
import numpy as np

REQUIRED = ['InvoiceNo', 'StockCode', 'Description', 'Quantity', 'InvoiceDate', 'UnitPrice', 'CustomerID', 'Country']


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    raw = raw.copy()
    raw.columns = raw.columns.str.strip()
    missing = sorted(set(REQUIRED) - set(raw.columns))
    if missing:
        raise ValueError('Missing columns: ' + ', '.join(missing))
    df = raw[REQUIRED].copy()
    report = {'source_rows': len(df)}
    for c in ['InvoiceNo', 'StockCode', 'Description', 'Country', 'CustomerID']:
        df[c] = df[c].astype('string').str.strip().replace('', pd.NA)
    df['CustomerID'] = df['CustomerID'].str.replace(r'\.0$', '', regex=True)
    df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'], errors='coerce', format='mixed')
    if getattr(df['InvoiceDate'].dtype, 'tz', None) is not None:
        df['InvoiceDate'] = df['InvoiceDate'].dt.tz_localize(None)
    if not pd.api.types.is_datetime64_any_dtype(df['InvoiceDate']):
        raise ValueError('Use consistent timestamps without mixed time zones.')
    for c in ['Quantity', 'UnitPrice']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    report['duplicates_removed'] = int(df.duplicated().sum())
    df = df.drop_duplicates()
    valid = (df[['InvoiceNo', 'StockCode', 'InvoiceDate']].notna().all(axis=1)
             & np.isfinite(df['Quantity']) & np.isfinite(df['UnitPrice'])
             & df['Quantity'].ne(0) & df['UnitPrice'].gt(0)
             & df['Quantity'].eq(df['Quantity'].round())
             & df['Quantity'].abs().le(1e7) & df['UnitPrice'].le(1e7))
    report['invalid_rows_removed'] = int((~valid).sum())
    df = df.loc[valid].copy()
    if df.empty:
        raise ValueError('No valid priced transactions remain after cleaning.')
    report['missing_customer_rows_retained'] = int(df['CustomerID'].isna().sum())
    report['missing_descriptions_filled'] = int(df['Description'].isna().sum())
    df['Description'] = df['Description'].fillna('Unknown product')
    df['Country'] = df['Country'].fillna('Unknown country')
    df['is_return'] = df['InvoiceNo'].str.upper().str.startswith('C') | df['Quantity'].lt(0)
    # Integer pence makes financial totals reproducible; prices round per unit.
    price = (df['UnitPrice'] * 100).round().astype('int64')
    value = price * df['Quantity'].abs().astype('int64')
    df['sales_pence'] = value.where(~df['is_return'], 0)
    df['return_pence'] = value.where(df['is_return'], 0)
    df['net_pence'] = df['sales_pence'] - df['return_pence']
    df['month'] = df['InvoiceDate'].dt.strftime('%Y-%m')
    report['clean_rows'] = len(df)
    return df.sort_values('InvoiceDate').reset_index(drop=True), report


def filter_data(df, start, end, countries=()):
    mask = df['InvoiceDate'].ge(pd.Timestamp(start)) & df['InvoiceDate'].lt(pd.Timestamp(end) + pd.Timedelta(days=1))
    if countries:
        mask &= df['Country'].isin(countries)
    return df.loc[mask]


def amount_columns(currency='GBP'):
    if currency == 'GBP':
        return ['sales_pence', 'return_pence', 'net_pence']
    if currency == 'USD':
        return ['sales_cents_usd', 'return_cents_usd', 'net_cents_usd']
    raise ValueError('Unsupported currency')


def kpis(df, currency='GBP'):
    sales_col, returns_col, _ = amount_columns(currency)
    sales = int(df[sales_col].sum()) / 100
    returns = int(df[returns_col].sum()) / 100
    purchases = df.loc[~df['is_return']]
    orders = int(purchases['InvoiceNo'].nunique())
    return {'gross_sales': sales, 'returns': returns, 'net_sales': round(sales - returns, 2),
            'orders': orders, 'customers': int(purchases['CustomerID'].nunique()),
            'average_order_value': sales / orders if orders else 0,
            'return_value_rate': returns / sales * 100 if sales else None}


def aggregate(df, dimension='Country', metric='net_sales', limit=10, currency='GBP'):
    if dimension not in ['Country', 'Description', 'month', 'StockCode']:
        raise ValueError('Unsupported dimension')
    if metric not in ['net_sales', 'gross_sales', 'returns', 'orders']:
        raise ValueError('Unsupported metric')
    # Administrative codes (POST, DOT, M, etc.) are not merchandise.
    # Keep them in total sales, but exclude them from product rankings.
    if dimension in ['Description', 'StockCode']:
        df = df.loc[df['StockCode'].str.fullmatch(r'\d{5}[A-Za-z]*', na=False)]
    if metric == 'orders':
        out = df.loc[~df['is_return']].groupby(dimension)['InvoiceNo'].nunique()
    else:
        sales, returns, net = amount_columns(currency)
        col = {'net_sales': net, 'gross_sales': sales, 'returns': returns}[metric]
        out = df.groupby(dimension)[col].sum() / 100
    out = out.rename(metric).reset_index()
    if dimension == 'month':
        return out.sort_values(dimension).reset_index(drop=True)
    return out.sort_values(metric, ascending=False).head(limit).reset_index(drop=True)


def make_plan(question):
    """Small, explicit offline router, never presented as AI."""
    q = question.lower()
    if any(x in q for x in ['profit', 'margin', 'forecast', 'predict', 'cause', 'why']):
        return {'operation': 'unsupported', 'dimension': 'Country', 'metric': 'net_sales', 'limit': 10}
    if any(x in q for x in ['quality', 'missing', 'duplicate', 'clean']):
        op, dimension = 'quality', 'Country'
    elif any(x in q for x in ['month', 'trend', 'over time']):
        op, dimension = 'group', 'month'
    elif any(x in q for x in ['product', 'item']):
        op, dimension = 'group', 'Description'
    elif any(x in q for x in ['countr', 'market']):
        op, dimension = 'group', 'Country'
    elif any(x in q for x in ['summar', 'overview', 'sales', 'revenue', 'order', 'return', 'customer']):
        op, dimension = 'summary', 'Country'
    else:
        op, dimension = 'unsupported', 'Country'
    metric = 'returns' if ('return' in q or 'cancel' in q) else 'orders' if 'order' in q else 'gross_sales' if 'gross' in q else 'net_sales'
    return {'operation': op, 'dimension': dimension, 'metric': metric, 'limit': 10}


def execute_plan(df, plan, report, currency='GBP'):
    if set(plan) != {'operation', 'dimension', 'metric', 'limit'}:
        raise ValueError('Invalid analysis plan fields')
    if plan['operation'] not in ['summary', 'group', 'quality', 'unsupported']:
        raise ValueError('Unsupported operation')
    if plan['dimension'] not in ['Country', 'Description', 'month', 'StockCode'] or plan['metric'] not in ['net_sales', 'gross_sales', 'returns', 'orders']:
        raise ValueError('Invalid dimension or metric')
    if type(plan['limit']) is not int or not 1 <= plan['limit'] <= 20:
        raise ValueError('Result limit must be between 1 and 20')
    base = {'metrics': kpis(df, currency), 'filtered_rows': len(df), 'currency': currency}
    if plan['operation'] == 'group':
        base['table'] = aggregate(df, plan['dimension'], plan['metric'], plan['limit'], currency).to_dict('records')
    if plan['operation'] == 'quality':
        base['dataset_quality_before_filters'] = report
    return base


def formulas(currency='GBP'):
    sales, returns, _ = amount_columns(currency)
    return {'gross_sales': f'SUM({sales}) / 100; positive, non-cancelled lines; {currency}',
            'returns': f'SUM({returns}) / 100; magnitude of cancellation/negative-quantity lines; {currency}',
            'net_sales': 'gross_sales - returns', 'orders': 'COUNT(DISTINCT InvoiceNo) for non-return lines',
            'average_order_value': 'gross_sales / orders',
            'customers': 'Distinct nonmissing CustomerID on non-return lines',
            'return_value_rate': 'returns / gross_sales * 100; value ratio, not customer return rate'}
