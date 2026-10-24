import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from src.ai import analyze, GROQ_MODEL, check_groq_access, analysis_error_message
from src.analytics import clean_data
from src.currency import usd_view
from tests.test_analytics import sample

def completion(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])

def test_groq_endpoint_key_schema_and_usd():
    df, report = clean_data(sample())
    plan = {'operation':'summary','dimension':'Country','metric':'net_sales','limit':10}
    with patch('src.ai.OpenAI') as client, patch('src.ai.requests.post') as google:
        create = client.return_value.chat.completions.create
        create.side_effect = [completion(json.dumps(plan)), completion('USD summary')]
        _, evidence, answer = analyze('Summary',usd_view(df),report,{},'fake-groq-key',GROQ_MODEL,currency='USD',provider='groq')
        assert client.call_args.kwargs['base_url'] == 'https://api.groq.com/openai/v1'
        assert client.call_args.kwargs['api_key'] == 'fake-groq-key'
        assert client.call_args.kwargs['max_retries'] == 0
        assert create.call_args_list[0].kwargs['response_format']['json_schema']['strict'] is True
        assert create.call_args_list[0].kwargs['model'] == GROQ_MODEL
        assert evidence['metrics']['net_sales'] == 62.76
        assert evidence['currency'] == 'USD'
        google.assert_not_called()
        client.return_value.responses.create.assert_not_called()

def test_groq_failure_never_falls_back():
    df, report = clean_data(sample())
    with patch('src.ai.OpenAI') as client, patch('src.ai.requests.post') as google:
        client.return_value.chat.completions.create.side_effect = RuntimeError('quota')
        with pytest.raises(RuntimeError):
            analyze('Summary',df,report,{},'fake',GROQ_MODEL,provider='groq')
        assert client.return_value.chat.completions.create.call_count == 1
        client.return_value.responses.create.assert_not_called()
        google.assert_not_called()

def test_key_check_only_lists_models_and_no_generation():
    with patch('src.ai.OpenAI') as client:
        client.return_value.models.list.return_value.data = [SimpleNamespace(id=GROQ_MODEL)]
        assert check_groq_access('fake') is True
        client.return_value.chat.completions.create.assert_not_called()

def test_groq_errors_do_not_direct_user_to_google():
    class Quota(Exception):
        status_code=429
    assert 'Groq' in analysis_error_message(Quota(),'groq')
    assert 'AI Studio' not in analysis_error_message(Quota(),'groq')
