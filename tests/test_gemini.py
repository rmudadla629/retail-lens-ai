from unittest.mock import patch, Mock
import json
import pytest
from src.ai import analyze, GEMINI_MODEL, GeminiRequestError, analysis_error_message
from src.analytics import clean_data
from src.currency import usd_view
from tests.test_analytics import sample


def response(text):
    return Mock(ok=True, json=Mock(return_value={'candidates':[{'content':{'parts':[{'text':text}]}}]}))


def test_native_google_request_and_usd_evidence():
    df, report = clean_data(sample())
    plan = {'operation':'summary','dimension':'Country','metric':'net_sales','limit':10}
    with patch('src.ai.requests.post') as post, patch('src.ai.OpenAI') as openai:
        post.side_effect = [response(json.dumps(plan)), response('USD summary')]
        _, evidence, answer = analyze('Summary',usd_view(df),report,{},'fake-test-key',GEMINI_MODEL,currency='USD',provider='gemini')
        assert evidence['metrics']['net_sales'] == 62.76
        assert evidence['currency'] == 'USD'
        assert answer == 'USD summary'
        assert post.call_count == 2
        first = post.call_args_list[0]
        assert first.args[0].endswith('/models/gemini-3.5-flash-lite:generateContent')
        assert 'fake-test-key' not in first.args[0]
        assert first.kwargs['headers']['x-goog-api-key'] == 'fake-test-key'
        config = first.kwargs['json']['generationConfig']
        assert config['responseMimeType'] == 'application/json'
        assert 'responseJsonSchema' in config
        assert 'reasoning_effort' not in config
        assert 'response_format' not in first.kwargs['json']
        openai.assert_not_called()


def test_quota_does_not_retry_or_fallback():
    df, report = clean_data(sample())
    with patch('src.ai.requests.post') as post, patch('src.ai.OpenAI') as openai:
        post.return_value = Mock(ok=False,status_code=429,json=Mock(return_value={'error':{'status':'RESOURCE_EXHAUSTED'}}))
        with pytest.raises(GeminiRequestError) as error:
            analyze('Summary',df,report,{},'fake',GEMINI_MODEL,provider='gemini')
        assert error.value.status_code == 429
        assert post.call_count == 1
        openai.assert_not_called()


def test_safe_diagnostics_identify_bad_settings_without_provider_message():
    df, report = clean_data(sample())
    with patch('src.ai.requests.post') as post:
        post.return_value = Mock(ok=False,status_code=400,json=Mock(return_value={'error':{
            'status':'INVALID_ARGUMENT','message':'Invalid responseJsonSchema fake-secret-do-not-print'}}))
        with pytest.raises(GeminiRequestError) as error:
            analyze('Summary',df,report,{},'fake',GEMINI_MODEL,provider='gemini')
        message = analysis_error_message(error.value)
        assert 'INVALID_ARGUMENT' in message
        assert 'responseJsonSchema' in message
        assert 'fake-secret-do-not-print' not in message


def test_missing_model_and_quota_messages_differ():
    missing=analysis_error_message(GeminiRequestError(404,'NOT_FOUND','request rejected',[]))
    quota=analysis_error_message(GeminiRequestError(429,'RESOURCE_EXHAUSTED','request rejected',[]))
    assert 'not a quota error' in missing
    assert 'rate or quota limit' in quota
