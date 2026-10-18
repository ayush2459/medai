#!/usr/bin/env python3
"""Align all synthetic GlucoTwin patient streams to the current time for demos.

Run from the repository root. Creates a timestamped backup before changing data.
This only shifts timestamps; it does not invent or alter glucose values.
"""
from pathlib import Path
from datetime import datetime, timezone
import shutil
import pandas as pd

candidates = [Path('data/sample/wearable.parquet'), Path('data/wearable.parquet')]
path = next((p for p in candidates if p.exists()), None)
if path is None:
    raise SystemExit('Could not find data/sample/wearable.parquet or data/wearable.parquet')

df = pd.read_parquet(path)
required = {'patient_id', 'timestamp', 'glucose_mg_dl'}
missing = required - set(df.columns)
if missing:
    raise SystemExit(f'Missing required columns: {sorted(missing)}')

backup = path.with_name(path.name + '.before_realtime_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
shutil.copy2(path, backup)
# Normalize timestamps to UTC for consistent comparisons, then preserve the file's
# original timestamp style as UTC-aware values (API should serialize ISO timestamps).
ts = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
if ts.isna().any():
    raise SystemExit(f'{int(ts.isna().sum())} timestamps could not be parsed; original file remains untouched (backup: {backup})')
df['timestamp'] = ts
now = pd.Timestamp.now(tz='UTC').floor('5min')
for patient_id, idx in df.groupby(df['patient_id'].astype(str)).groups.items():
    latest = df.loc[idx, 'timestamp'].max()
    # Shift each patient's full stream so its last row lands at current time.
    df.loc[idx, 'timestamp'] = df.loc[idx, 'timestamp'] + (now - latest)

df = df.sort_values(['patient_id', 'timestamp']).reset_index(drop=True)
tmp = path.with_suffix(path.suffix + '.tmp')
df.to_parquet(tmp, index=False)
tmp.replace(path)
print(f'Updated {path}; backup: {backup}')
print(f'Patients: {df.patient_id.nunique()}, rows: {len(df)}, latest timestamp: {df.timestamp.max().isoformat()}')
for pid, group in df.groupby('patient_id'):
    print(f'{pid}: {len(group)} rows, latest={group.timestamp.max().isoformat()}, glucose={int(group.glucose_mg_dl.notna().sum())} non-null')
