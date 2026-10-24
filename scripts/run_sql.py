from pathlib import Path
import sqlite3
import pandas as pd
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.currency import usd_view

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    df = usd_view(pd.read_parquet(ROOT/'data/processed/retail.parquet'))
    with sqlite3.connect(':memory:') as conn:
        df.to_sql('retail',conn,index=False)
        # Strip full-line comments before splitting; explanatory comments may contain semicolons.
        sql = '\n'.join(line for line in (ROOT/'sql/analysis.sql').read_text().splitlines() if not line.lstrip().startswith('--'))
        for number, query in enumerate(sql.split(';'), 1):
            if query.strip():
                result = pd.read_sql_query(query,conn)
                print(f'\nAnalysis {number}\n{result.to_string(index=False)}')
