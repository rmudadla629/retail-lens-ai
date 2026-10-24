from types import SimpleNamespace
from unittest.mock import patch
import json
from src.ai import analyze
from src.analytics import clean_data
from tests.test_analytics import sample


def test_real_ai_path_uses_validated_plan_and_aggregates_only():
    df, report = clean_data(sample())
    plan = {'operation':'group','dimension':'Country','metric':'net_sales','limit':10}
    with patch('src.ai.OpenAI') as client:
        create = client.return_value.responses.create
        create.side_effect = [SimpleNamespace(output_text=json.dumps(plan)), SimpleNamespace(output_text='UK leads net sales in this view.')]
        actual, evidence, answer = analyze('Top countries?',df,report,{'countries':['All']},'fake-test-key','model-under-test')
        assert actual == plan
        assert evidence['metrics']['net_sales'] == 40
        assert len(create.call_args_list) == 2
        assert all(call.kwargs['store'] is False for call in create.call_args_list)
        payload = create.call_args_list[1].kwargs['input']
        assert 'CustomerID' not in json.loads(payload)['evidence']
        assert 'InvoiceNo' not in json.loads(payload)['evidence']
        assert 'fake-test-key' not in payload


def test_unsupported_ai_plan_does_not_make_interpretation_call():
    df, report = clean_data(sample())
    plan = {'operation':'unsupported','dimension':'Country','metric':'net_sales','limit':10}
    with patch('src.ai.OpenAI') as client:
        client.return_value.responses.create.return_value.output_text = json.dumps(plan)
        _, _, answer = analyze('Predict profit',df,report,{},'fake','model')
        assert client.return_value.responses.create.call_count == 1
        assert 'Profit requires cost data' in answer
