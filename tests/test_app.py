from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

def test_dashboard_filter_and_guided_answer():
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60).run()
    assert not app.exception
    assert any('UCI Online Retail' in m.value for m in app.markdown)
    assert any('USD ($)' in m.value for m in app.markdown)
    assert any('$15,292,808' in m.value for m in app.markdown)
    app.multiselect[0].set_value(['France']).run()
    assert not app.exception
    assert app.session_state['context_id']
    next(button for button in app.button if button.label == 'Summarize sales performance').click().run()
    assert not app.exception
    assert len(app.session_state['answers']) == 1
    assert app.session_state['answers'][0]['label'].startswith('Calculated')
    assert app.session_state['answers'][0]['evidence']['currency'] == 'USD'
    next(button for button in app.button if button.label == 'Show monthly sales trends').click().run()
    assert not app.exception
    assert app.chat_message[0].markdown[0].value == 'Show monthly sales trends'
    assert len(app.chat_message) == 2
    assert len(app.session_state['answers']) == 1
    next(button for button in app.button if button.label == 'Summarize sales performance').click().run()
    assert not app.exception
    assert len(app.chat_message) == 2
    assert app.chat_message[0].markdown[0].value == 'Summarize sales performance'
    app.multiselect[0].set_value(['Germany']).run()
    assert not app.exception
    assert app.session_state['answers'] == []
