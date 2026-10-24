import json
from unittest.mock import patch
from types import SimpleNamespace
import pytest
from src.currency import usd_view, usd_export, FX
from src.analytics import clean_data, kpis, aggregate
from src.ai import analyze
from tests.test_analytics import sample


def test_usd_conversion_preserves_source_and_reconciles_lines():
    gbp, _ = clean_data(sample())
    usd = usd_view(gbp)
    assert 'sales_cents_usd' not in gbp
    assert usd['sales_pence'].equals(gbp['sales_pence'])
    assert usd['UnitPrice'].equals(gbp['UnitPrice'])
    assert kpis(usd, 'USD')['gross_sales'] == 78.45
    assert kpis(usd, 'USD')['returns'] == 15.69
    assert kpis(usd, 'USD')['net_sales'] == 62.76
    assert aggregate(usd, 'Country', currency='USD')['net_sales'].sum() == 62.76
    assert kpis(usd, 'USD')['orders'] == kpis(gbp)['orders']
    assert kpis(usd, 'USD')['customers'] == kpis(gbp)['customers']
    exported = usd_export(usd)
    assert round(exported['NetSales_USD'].sum(), 2) == 62.76
    assert exported['Currency'].eq('USD').all()
    assert exported['FX_reference_date'].eq('2011-12-09').all()
    assert not {'UnitPrice','sales_pence','return_pence','net_pence'} & set(exported.columns)


def test_usd_ai_uses_usd_evidence_and_instructions():
    gbp, report = clean_data(sample())
    usd = usd_view(gbp)
    plan = {'operation':'summary','dimension':'Country','metric':'net_sales','limit':10}
    with patch('src.ai.OpenAI') as client:
        create = client.return_value.responses.create
        create.side_effect = [SimpleNamespace(output_text=json.dumps(plan)), SimpleNamespace(output_text='USD result')]
        _, evidence, _ = analyze('Summarize sales',usd,report,{'fx':FX},'fake','model',currency='USD')
        assert evidence['currency'] == 'USD'
        assert evidence['metrics']['net_sales'] == 62.76
        assert 'Mention USD' in create.call_args_list[1].kwargs['instructions']
        payload = json.loads(create.call_args_list[1].kwargs['input'])
        assert payload['filters']['fx']['rate'] == '1.5688'


def test_invalid_currency_cannot_silently_relabel_values():
    gbp, _ = clean_data(sample())
    with pytest.raises(ValueError,match='Unsupported currency'):
        kpis(gbp,'EUR')
