"""Retail Lens AI: one standalone portfolio project."""
from pathlib import Path
import hashlib
import html
import json
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from src.analytics import aggregate, clean_data, execute_plan, filter_data, formulas, kpis, make_plan
from src.ai import analyze, GEMINI_MODEL, GROQ_MODEL, analysis_error_message, check_groq_access
from src.currency import FX, usd_view, usd_export

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
st.set_page_config(page_title='Retail Lens AI | Sales Intelligence', page_icon='✦', layout='wide')
st.markdown((ROOT / 'assets/style.css').read_text(), unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def bundled_data():
    return usd_view(pd.read_parquet(ROOT / 'data/processed/retail.parquet')), json.loads((ROOT / 'data/processed/quality.json').read_text())


@st.cache_data(show_spinner=False)
def uploaded_data(content):
    df, report = clean_data(pd.read_csv(__import__('io').BytesIO(content), dtype={'InvoiceNo': str, 'StockCode': str, 'CustomerID': str}))
    return usd_view(df), report


def secret(name, default=''):
    value = os.getenv(name)
    if value:
        return value
    try:
        return str(st.secrets.get(name, default))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default


def chart_style(fig, height=320):
    fig.update_layout(height=height, margin=dict(l=8, r=16, t=12, b=12),
                      template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Arial', color='#B5BDD8', size=12),
                      hoverlabel=dict(bgcolor='#202A44', font=dict(color='#F3F0FF', size=13)),
                      legend=dict(orientation='h', y=1.15, title_text=''))
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor='#29324B', zeroline=False)
    return fig


def money(value):
    return f'${value:,.0f}'


with st.sidebar:
    st.markdown('<div class="logo">✦ <span>retail<span class="logo-light">lens</span><sup> AI</sup></span></div>', unsafe_allow_html=True)
    st.caption('YOUR RETAIL ANALYTICS WORKSPACE')
    st.markdown('<div class="side-active">◈ &nbsp; Sales intelligence</div>', unsafe_allow_html=True)
    st.markdown('#### Dataset')
    uploaded = st.file_uploader('Bring your own retail CSV', type=['csv'], help='Use the sample file headers. Maximum 30 MB; input prices must be GBP. The app converts them to USD.')
    st.download_button('↓ Get upload sample', (ROOT / 'data/upload_sample.csv').read_bytes(), 'retail_upload_sample.csv', 'text/csv', width='stretch')
    st.caption('No CSV? The real UCI retail dataset is already loaded.')

try:
    if uploaded is not None:
        content = uploaded.getvalue()
        if len(content) > 30_000_000:
            raise ValueError('Please use a CSV smaller than 30 MB.')
        with st.spinner('Validating your dataset…'):
            data, quality = uploaded_data(content)
        source = uploaded.name
        fingerprint = hashlib.sha256(content).hexdigest()[:16]
    else:
        data, quality = bundled_data()
        source, fingerprint = 'UCI Online Retail · full dataset', 'uci-retail-full'
except (ValueError, TypeError, OSError, pd.errors.ParserError) as error:
    st.error(f'Could not load the dataset: {error}')
    st.info('Download the sample CSV in the sidebar to check the required format. Remove your upload to return to the UCI dataset.')
    st.stop()

min_date, max_date = data.InvoiceDate.min().date(), data.InvoiceDate.max().date()
with st.sidebar:
    st.markdown('#### Shape your view')
    date_range = st.date_input('Date range', value=(min_date, max_date), min_value=min_date, max_value=max_date, key=f'dates_{fingerprint}')
    countries = st.multiselect('Countries', sorted(data.Country.unique()), placeholder='All countries', key=f'countries_{fingerprint}')
    st.caption('Dates and countries apply to every chart and analysis. Empty country selection means all countries.')
    st.divider()
    st.markdown('#### ✧ AI connection')
    provider_name = st.selectbox('AI provider', ['Groq — free-plan option', 'Google Gemini — free-tier option', 'OpenAI — optional paid API'], key='ai_provider')
    provider = 'groq' if provider_name.startswith('Groq') else 'gemini' if provider_name.startswith('Google') else 'openai'
    key_name = {'groq':'GROQ_API_KEY','gemini':'GEMINI_API_KEY','openai':'OPENAI_API_KEY'}[provider]
    connection_key = secret(key_name)
    if not connection_key:
        connection_key = st.text_input({'groq':'Groq API key','gemini':'Gemini API key','openai':'OpenAI API key'}[provider], type='password', autocomplete='off', key=f'session_api_key_{provider}', help='Held only in this server session; never saved to the project or GitHub.')
    connection_key = connection_key.strip()
    if provider == 'groq':
        model = GROQ_MODEL
        st.caption('Model: GPT-OSS 20B, hosted by Groq. Keep your Groq account on the Free plan. Limits and model access depend on your account. No automatic retry or paid fallback.')
        st.caption('Your question and calculated aggregates go to Groq. The key is sent only to Groq, not Google or OpenAI. Use the public sample data for testing.')
        if st.button('Check Groq access', disabled=not bool(connection_key), key='check_groq'):
            try:
                if check_groq_access(connection_key):
                    st.success('Groq accepted the key and lists the selected model. Enable AI and ask a question to test generation; quotas still apply.')
                else:
                    st.warning('Groq accepted the key but the selected model is not listed. Check model permissions in Groq Console.')
            except Exception as error:
                st.error(analysis_error_message(error, 'groq'))
    elif provider == 'gemini':
        model = GEMINI_MODEL
        st.caption('Model: Gemini 3.5 Flash-Lite. Keep your Google project on Free tier with paid billing disabled. Free quota depends on your account; the app stops on quota errors and never switches to a paid provider.')
        st.caption('Questions and aggregate results go to Google. Free-tier content may be used to improve Google products. Use public/sample data here.')
    else:
        model = st.text_input('Model', value=secret('OPENAI_MODEL', 'gpt-4.1-mini'))
        st.caption('Questions and aggregate results go to OpenAI. API usage is separately billed. No automatic paid-provider fallback.')
    enable_ai = st.toggle('Use real AI analysis', value=False, disabled=not bool(connection_key), key=f'enable_ai_{provider}')
    st.caption('Individual transactions and customer IDs are not sent. Each question uses up to two AI requests: one analysis plan and one explanation.')
    st.markdown('<div class="side-note">ONE DATASET. MANY DISCOVERIES.<br><span>Python · SQL · Plotly · AI</span></div>', unsafe_allow_html=True)

if len(date_range) != 2:
    st.info('Select an end date to complete your date range.')
    st.stop()
start, end = date_range
df = filter_data(data, start, end, countries)
filters = {'start': str(start), 'end': str(end), 'countries': countries or ['All countries'], 'dataset': source, 'currency': 'USD', 'fx': FX}
context_id = hashlib.sha256(json.dumps([fingerprint, filters], sort_keys=True).encode()).hexdigest()
if st.session_state.get('context_id') != context_id:
    st.session_state.context_id = context_id
    st.session_state.answers = []
st.markdown('<div class="topline"><span>WORKSPACE &nbsp; / &nbsp; SALES INTELLIGENCE</span><span class="project-tag">PORTFOLIO PROJECT 01</span></div>', unsafe_allow_html=True)
st.markdown('<div class="hero"><div class="hero-copy"><div class="eyebrow">A FRESH PERSPECTIVE ON YOUR NUMBERS</div><h1>Big questions.<br><span>Brighter insights.</span></h1><p>Your sales story, beautifully connected.<br>Explore performance. Find opportunities. Ask your AI analyst.</p><div class="hero-tags"><span>✦ Interactive analytics</span><span>✧ AI-assisted exploration</span></div></div><div class="hero-art"><div class="orb orb-one"></div><div class="orb orb-two"></div><div class="float-card"><small>DATA → DECISIONS</small><strong>See the bigger<br>picture.</strong><div class="mini-bars"><i></i><i></i><i></i><i></i><i></i><i></i></div></div><div class="little-star">✦</div></div></div>', unsafe_allow_html=True)
safe_source = html.escape(source)
st.markdown(f'<div class="source-strip"><span>● &nbsp; {safe_source}</span><span>{len(df):,} cleaned lines &nbsp; · &nbsp; {start:%d %b %Y} – {end:%d %b %Y} &nbsp; · &nbsp; USD ($)</span></div>', unsafe_allow_html=True)
st.caption(f"USD equivalents · 1 GBP = {FX['rate']} USD · reference date {FX['date']} · fixed rate, not transaction-day FX.")
st.caption('Historical transactions, not live sales. Net sales = gross sales − returns/cancellations. Product cost data is unavailable, so profit is not estimated.')

if df.empty:
    st.warning('No transactions match these filters. Select another date range or country.')
    st.stop()

m = kpis(df, 'USD')
colors = ['purple', 'blue', 'teal', 'orange']
cards = [('Net sales', money(m['net_sales']), 'After returns & cancellations', '↗'),
         ('Purchase orders', f"{m['orders']:,}", 'Distinct non-return invoices', '▦'),
         ('Known customers', f"{m['customers']:,}", 'Anonymous sales stay included', '◎'),
         ('Average order value', money(m['average_order_value']), 'Gross sales ÷ purchase orders', '◈')]
for col, color, (label, value, note, icon) in zip(st.columns(4), colors, cards):
    with col:
        st.markdown(f'<div class="kpi {color}"><div class="kpi-label">{label}<span>{icon}</span></div><div class="kpi-number">{value}</div><div class="kpi-note">{note}</div></div>', unsafe_allow_html=True)

overview, products, explorer, assistant, methodology = st.tabs(['✦ Overview', '◈ Products & markets', '▦ Data explorer', '✧ Ask AI', 'ⓘ Method & quality'])

with overview:
    left, right = st.columns([1.7, 1])
    with left, st.container(border=True):
        st.markdown('#### The sales story')
        st.caption('Monthly gross sales, net sales, and cancellation value · USD')
        trend = df.groupby('month')[['sales_cents_usd', 'return_cents_usd', 'net_cents_usd']].sum().reset_index()
        fig = go.Figure()
        for column, name, color in [('sales_cents_usd', 'Gross sales', '#51B7F9'), ('net_cents_usd', 'Net sales', '#BB8BFF'), ('return_cents_usd', 'Returns / cancellations', '#FFAA65')]:
            fig.add_trace(go.Scatter(x=trend.month, y=trend[column]/100, name=name, mode='lines+markers',
                                     line=dict(color=color, width=3), marker=dict(size=6), hovertemplate='%{x}<br>$%{y:,.2f}<extra>%{fullData.name}</extra>'))
        fig.update_yaxes(tickprefix='$', title=None)
        st.plotly_chart(chart_style(fig), width='stretch')
        st.caption('Boundary months can be partial. The UCI source ends on 9 Dec 2011; no growth percentage assumes December is complete.')
    with right, st.container(border=True):
        st.markdown('#### Where sales happen')
        st.caption('Top six countries by net sales · USD')
        country = aggregate(df, 'Country', 'net_sales', 6, currency='USD').sort_values('net_sales')
        fig = px.bar(country, y='Country', x='net_sales', orientation='h', color='Country',
                     color_discrete_sequence=['#BBA6FB', '#60C9CA', '#FFBD7C', '#7CBAFA', '#EF97D1', '#AA86FF'])
        fig.update_traces(hovertemplate='%{y}<br>$%{x:,.2f}<extra></extra>')
        fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title=None)
        fig.update_xaxes(tickprefix='$')
        st.plotly_chart(chart_style(fig), width='stretch')
    c1, c2 = st.columns([1.7, 1])
    top = aggregate(df, 'Description', 'net_sales', 1, currency='USD')
    with c1:
        if not top.empty:
            name, value = top.iloc[0].tolist()
            st.markdown(f'<div class="insight-box"><span class="insight-icon">✧</span><div><b>A little insight. A useful next question.</b><p>{html.escape(str(name))} leads product net sales at <strong>{money(value)}</strong> in this view. Explore its cancellation value before deciding where to focus.</p><small>Computed from your current filters · descriptive finding</small></div></div>', unsafe_allow_html=True)
    with c2:
        rate = f"{m['return_value_rate']:.1f}%" if m['return_value_rate'] is not None else 'N/A'
        st.html(f'<div class="return-box"><span>RETURNS &amp; CANCELLATIONS · USD</span><strong>{money(m["returns"])}</strong><p>{rate} of gross sales value · rounded to the nearest dollar</p></div>')

with products:
    col1, col2 = st.columns(2)
    with col1:
        metric = st.selectbox('Rank products by', ['net_sales', 'gross_sales', 'returns', 'orders'], format_func=lambda s:s.replace('_',' ').title())
    with col2:
        count = st.slider('Number of products', 5, 20, 10)
    rankings = aggregate(df, 'Description', metric, count, currency='USD')
    fig = px.bar(rankings.sort_values(metric), x=metric, y='Description', orientation='h',
                 color_discrete_sequence=['#B794FF'], labels={metric:metric.replace('_', ' ').title(), 'Description':''})
    if metric != 'orders':
        fig.update_xaxes(tickprefix='$', title=metric.replace('_', ' ').title() + ' (USD)')
    st.plotly_chart(chart_style(fig, max(350, count*30)), width='stretch')
    st.caption('Product rankings use merchandise codes (five digits, optionally followed by letters). Administrative lines such as postage stay in total sales but are excluded here. Product order counts overlap across invoices. Descriptions are not categories.')
    st.dataframe(aggregate(df, 'Country', 'net_sales', 40, currency='USD').rename(columns={'net_sales':'net_sales_usd'}), width='stretch', hide_index=True)

with explorer:
    st.markdown('#### The numbers behind the story')
    st.caption('First 500 matching rows shown. Export includes all filtered rows with derived amount fields.')
    st.dataframe(usd_export(df.head(500)), width='stretch', hide_index=True)
    if st.button('Prepare filtered CSV', key='prepare_export'):
        st.download_button('Download filtered rows', usd_export(df).to_csv(index=False).encode(), 'retail_filtered_usd.csv', 'text/csv', key='export')
    st.download_button('Download monthly summary', aggregate(df, 'month', currency='USD').rename(columns={'net_sales':'net_sales_usd'}).assign(Currency='USD', GBP_to_USD_rate=FX['rate'], FX_reference_date=FX['date']).to_csv(index=False), 'monthly_net_sales_usd.csv', 'text/csv')

with assistant:
    st.markdown('### Meet your analytical sidekick. ✧')
    st.write('Ask a question, inspect the calculation, and explore the evidence.')
    st.info(f'AI mode is on: {provider_name}. Connection is verified only when an answer succeeds.' if enable_ai else 'Guided mode: calculated answers with no language model. Add a key and enable AI in the sidebar for natural-language analysis.')
    suggested = ['Summarize sales performance', 'Which products lead net sales?', 'Show monthly sales trends', 'Review data quality']
    for col, suggestion in zip(st.columns(4), suggested):
        if col.button(suggestion, width='stretch'):
            st.session_state.next_question = suggestion
    question = st.chat_input('Ask about sales, products, countries, returns, or data quality…', max_chars=1000)
    question = question or st.session_state.pop('next_question', None)
    if question:
        st.session_state.answers = []
        with st.spinner('Following the numbers…'):
            try:
                if enable_ai:
                    plan, evidence, answer = analyze(question, df, quality, filters, connection_key, model, currency='USD', provider=provider)
                    label = provider_name + ' · AI interpretation · verify against the evidence'
                else:
                    plan = make_plan(question)
                    evidence = execute_plan(df, plan, quality, currency='USD')
                    answer = ('This question needs analysis beyond guided mode. Try the suggested questions. Profit requires cost data, '
                              'and causal explanations or predictions require additional methods.' if plan['operation']=='unsupported' else
                              'The calculated results below use your current filters. Amounts are USD equivalents at the documented fixed reference rate. Open the evidence panel to inspect the formula and analysis plan.')
                    label = 'Calculated answer · no AI model used'
                st.session_state.answers = [{'question':question, 'answer':answer, 'plan':plan, 'evidence':evidence, 'label':label}]
            except Exception as error:
                # Never show provider response bodies, which may contain sensitive input.
                st.error(analysis_error_message(error, provider))
    for entry in st.session_state.get('answers', [])[-1:]:
        with st.chat_message('user'):
            st.write(entry['question'])
        with st.chat_message('assistant'):
            st.caption(entry['label'])
            st.write(entry['answer'])
            ev, plan = entry['evidence'], entry['plan']
            if plan['operation']=='summary':
                result = pd.DataFrame([{'metric':k, 'value':v} for k,v in ev['metrics'].items()])
                st.caption('Monetary values are USD equivalents; orders/customers are counts and return_value_rate is a percentage.')
                st.dataframe(result, hide_index=True, width='stretch')
            if 'table' in ev:
                result = pd.DataFrame(ev['table'])
                st.caption('Amounts in USD equivalents; order counts are not currency amounts.')
                st.dataframe(result, hide_index=True, width='stretch')
                if not result.empty:
                    dimension, metric = plan['dimension'], plan['metric']
                    fig = px.line(result, x=dimension, y=metric, markers=True, color_discrete_sequence=['#B794FF']) if dimension=='month' else px.bar(result, x=dimension, y=metric, color_discrete_sequence=['#B794FF'])
                    if metric != 'orders':
                        fig.update_yaxes(tickprefix='$', title=metric.replace('_', ' ').title() + ' (USD)')
                    st.plotly_chart(chart_style(fig), width='stretch')
            if 'dataset_quality_before_filters' in ev:
                st.json(ev['dataset_quality_before_filters'])
            with st.expander('Show calculation, filters & evidence'):
                st.json({'filters':filters, 'plan':plan, 'formulas':formulas('USD'), 'calculated_evidence':ev})
    if st.button('Clear answer'):
        st.session_state.answers = []
        st.rerun()
    st.caption('Only the latest answer is shown. Choose any question again to see its answer. Changing filters clears the current answer.')

with methodology:
    st.markdown('### Transparent analysis, from source to chart')
    st.markdown('**Dataset:** [Online Retail — Daqing Chen, UCI (2015)](https://doi.org/10.24432/C5BW33), licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Bundled data covers December 2010 to December 2011. This app is an independent portfolio project.')
    st.markdown('**Cleaning:** remove exact duplicates and invalid dates, IDs, quantities, and nonpositive prices. Retain anonymous purchases. Fill missing product/country labels. A cancellation invoice or negative quantity is a return/cancellation; its magnitude reduces net sales. Amounts round per unit to integer pence before aggregation.')
    st.markdown('**Limits:** cancellation value is a proxy, not a confirmed matched refund. No cost, profit, acquisition spending, or verified churn data is present. No forecasting or causal claims are made. Boundary months are incomplete. Customer counts exclude missing IDs; their sales remain included. Uploaded prices must be in GBP. All displayed amounts are USD equivalents at the fixed reference rate, with each transaction amount rounded to cents before aggregation. This is not transaction-date FX conversion. The original GBP data is preserved.')
    st.markdown(f"**Currency:** USD equivalent = GBP × {FX['rate']}; fixed rate dated {FX['date']}. [Rate source]({FX['source_url']}). Unit prices are rounded separately for display; multiplying rounded USD unit prices by quantities may differ from converted line totals.")
    st.json(quality)
    st.dataframe(pd.DataFrame([{'metric':k, 'definition':v} for k,v in formulas('USD').items()]), hide_index=True, width='stretch')
    st.markdown('**AI workflow:** question → structured plan → validated allowlisted Pandas operation → computed table → AI interpretation. No model-generated code or SQL is executed. The model sees schema, questions, and aggregate evidence, not individual transactions or customer IDs.')
st.markdown('<div class="footer"><b>✦ RETAIL LENS AI</b><span>Explore with curiosity. Decide with evidence.</span></div>', unsafe_allow_html=True)
