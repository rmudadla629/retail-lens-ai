import json
from pathlib import Path
import sqlite3
import pandas as pd
import pytest
from src.analytics import clean_data, kpis, filter_data, aggregate, execute_plan, make_plan


def sample():
    return pd.DataFrame([
        ['1','A','Red lamp',2,'2011-01-01 10:00',10,'100','UK'],
        ['1','B','Blue lamp',1,'2011-01-01 10:00',20,'100','UK'],
        ['2','A','Red lamp',1,'2011-01-02 23:59',10,None,'France'],
        ['C3','A','Red lamp',-1,'2011-01-03',10,'100','UK'],
        ['4','B','Blue lamp',0,'2011-01-03',20,'200','UK'],
        ['5','B','Blue lamp',1,'2011-01-03',0,'200','UK'],
        ['6','B','Blue lamp',1,'bad-date',20,'200','UK'],
        ['1','A','Red lamp',2,'2011-01-01 10:00',10,'100','UK'],
    ],columns=['InvoiceNo','StockCode','Description','Quantity','InvoiceDate','UnitPrice','CustomerID','Country'])


def test_cleaning_retains_anonymous_sales_and_audits_exclusions():
    df, report = clean_data(sample())
    assert report['duplicates_removed'] == 1
    assert report['invalid_rows_removed'] == 3
    assert report['missing_customer_rows_retained'] == 1
    assert report['clean_rows'] == 4
    assert report['source_rows'] == report['clean_rows'] + report['duplicates_removed'] + report['invalid_rows_removed']
    m = kpis(df)
    assert m == {'gross_sales':50, 'returns':10, 'net_sales':40, 'orders':2,
                 'customers':1, 'average_order_value':25, 'return_value_rate':20}


def test_negative_quantity_and_c_invoice_are_both_returns():
    raw = sample().iloc[:2].copy()
    raw.loc[0, 'Quantity'] = -2
    raw.loc[1, 'InvoiceNo'] = 'c2'
    df, _ = clean_data(raw)
    assert kpis(df)['returns'] == 40
    assert kpis(df)['orders'] == 0
    assert kpis(df)['return_value_rate'] is None


def test_inclusive_end_date_and_country_filter():
    df, _ = clean_data(sample())
    assert kpis(filter_data(df,'2011-01-01','2011-01-02'))['net_sales'] == 50
    assert len(filter_data(df,'2011-01-02','2011-01-02',['France'])) == 1
    assert filter_data(df,'2011-02-01','2011-02-02').empty


def test_group_reconciliation_and_missing_schema():
    df, _ = clean_data(sample())
    assert aggregate(df,'Country')['net_sales'].sum() == 40
    with pytest.raises(ValueError, match='Missing columns'):
        clean_data(sample().drop(columns='UnitPrice'))


def test_plan_does_not_execute_arbitrary_code():
    df, report = clean_data(sample())
    bad = {'operation':'group', 'dimension':'__import__("os")', 'metric':'net_sales', 'limit':10}
    with pytest.raises(ValueError):
        execute_plan(df,bad,report)
    assert make_plan('What is our profit margin?')['operation'] == 'unsupported'
    assert make_plan('Show monthly sales trends')['dimension'] == 'month'


def test_administrative_codes_stay_in_totals_but_not_product_rankings():
    raw = sample().iloc[:2].copy()
    raw.loc[0, 'StockCode'] = 'DOT'
    raw.loc[1, 'StockCode'] = '12345A'
    df, _ = clean_data(raw)
    assert kpis(df)['gross_sales'] == 40
    ranked = aggregate(df, 'Description', 'gross_sales')
    assert ranked['gross_sales'].sum() == 20
    assert ranked['Description'].tolist() == ['Blue lamp']


def test_real_dataset_totals_match_stored_findings_and_sql():
    root = Path(__file__).resolve().parents[1]
    df = pd.read_parquet(root/'data/processed/retail.parquet')
    saved = json.loads((root/'data/processed/findings.json').read_text())
    assert kpis(df) == saved['metrics']
    with sqlite3.connect(':memory:') as conn:
        df[['InvoiceNo','is_return','sales_pence','return_pence','net_pence']].to_sql('retail',conn,index=False)
        result = conn.execute('SELECT SUM(net_pence)/100.0, COUNT(DISTINCT CASE WHEN is_return=0 THEN InvoiceNo END) FROM retail').fetchone()
    assert result[0] == kpis(df)['net_sales']
    assert result[1] == kpis(df)['orders']
