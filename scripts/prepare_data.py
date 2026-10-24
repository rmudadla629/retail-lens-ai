"""Reproduce the bundled UCI dataset and audit without notebook state."""
from pathlib import Path
import sys
import hashlib
import json
import zipfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from src.analytics import clean_data, kpis, aggregate
from src.currency import usd_view, FX

URL = 'https://archive.ics.uci.edu/static/public/352/online+retail.zip'

def main():
    path = ROOT / 'data/raw/online-retail.zip'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        urllib.request.urlretrieve(URL, path)
    with zipfile.ZipFile(path) as archive:
        name = next(n for n in archive.namelist() if n.endswith('.xlsx'))
        raw = pd.read_excel(archive.open(name), engine='openpyxl')
    df, report = clean_data(raw)
    out = ROOT / 'data/processed'
    out.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out / 'retail.parquet', index=False)
    raw.sample(n=min(3000, len(raw)), random_state=42).sort_values('InvoiceDate').to_csv(ROOT / 'data/upload_sample.csv', index=False)
    report.update({'source_zip_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'date_min': str(df.InvoiceDate.min()), 'date_max': str(df.InvoiceDate.max())})
    (out / 'quality.json').write_text(json.dumps(report, indent=2))
    (out / 'findings.json').write_text(json.dumps({'metrics': kpis(df), 'monthly': aggregate(df, 'month').to_dict('records'),
                                               'countries': aggregate(df, 'Country').to_dict('records')}, indent=2))
    usd = usd_view(df)
    (out / 'findings_usd.json').write_text(json.dumps({'currency': 'USD', 'fx': FX, 'metrics': kpis(usd, 'USD'),
                                                     'monthly': aggregate(usd, 'month', currency='USD').to_dict('records'),
                                                     'countries': aggregate(usd, 'Country', currency='USD').to_dict('records')}, indent=2))
    print(json.dumps(report, indent=2))
    print(json.dumps(kpis(df), indent=2))

if __name__ == '__main__':
    main()
