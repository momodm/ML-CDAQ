"""SQLite query store; never mutates the accepted CSV."""
import hashlib
import json
import math
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np
from app import ROOT

BASELINE = ROOT / 'data/processed/成都空气质量基线数据.csv'
DATABASE = ROOT / 'data/system/成都空气质量系统.db'
COLUMNS = ['pm25', 'pm10', 'no2', 'so2', 'co', 'o3']
METRICS = dict(zip(['PM2.5', 'PM10', 'NO2', 'SO2', 'CO', 'O3'], COLUMNS))
UNITS = {column: 'mg/m³' if column == 'co' else 'μg/m³' for column in COLUMNS}


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def readonly(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    return connection


def initialize_database(path=DATABASE, baseline=BASELINE, rebuild=False):
    path, baseline = Path(path), Path(baseline)
    source_sha = sha256(baseline)
    accepted = json.loads((ROOT / 'outputs/modeling/M3验收状态.json').read_text(encoding='utf-8'))
    model_meta = json.loads((ROOT / 'outputs/models/模型元数据.json').read_text(encoding='utf-8'))
    input_hashes = {Path(key).as_posix(): value for key, value in model_meta['input_hashes'].items()}
    expected_sha = input_hashes['data/processed/成都空气质量基线数据.csv']
    if accepted['M3_GATE'] != 'PASS' or source_sha != expected_sha:
        raise RuntimeError('查询库输入不是已冻结 M3 使用的 M1 基线')
    if path.exists() and not rebuild:
        with closing(readonly(path)) as connection:
            stored = connection.execute('SELECT * FROM import_metadata').fetchone()
            count = connection.execute('SELECT COUNT(*) FROM air_quality_hourly').fetchone()[0]
            if stored['baseline_sha256'] != source_sha or count != stored['record_count'] or count != 58537:
                raise RuntimeError('查询库与冻结基线不符；请明确执行 --rebuild，不能静默覆盖')
            return dict(stored)
    frame = pd.read_csv(baseline, usecols=['source_label_datetime', 'date', 'hour'] + list(METRICS))
    if len(frame) != 58537 or frame['PM2.5'].count() != 58337:
        raise RuntimeError('冻结基线数量不符，不改写或清洗数据')
    labels = pd.to_datetime(frame['source_label_datetime'], format='%Y-%m-%d %H:%M:%S')
    values = frame[list(METRICS)].to_numpy(dtype=float)
    if not labels.is_unique or not labels.is_monotonic_increasing or labels.dt.tz is not None:
        raise RuntimeError('源标签必须有序、唯一且无时区')
    if np.isinf(values).any() or (values < 0).any():
        raise RuntimeError('输入不符；不在系统导入时实施数据清洗')
    rows = pd.DataFrame({'source_label_datetime': frame['source_label_datetime'],
                         'source_date': labels.dt.strftime('%Y-%m-%d'), 'source_hour': frame['hour']})
    for pollutant, column in METRICS.items():
        rows[column] = frame[pollutant]
    rows = rows.astype(object).where(rows.notna(), None)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.building', delete=False) as temporary:
        staging = Path(temporary.name)
    try:
        with closing(sqlite3.connect(staging)) as connection:
            connection.executescript('''
                CREATE TABLE air_quality_hourly (
                    id INTEGER PRIMARY KEY,
                    source_label_datetime TEXT NOT NULL UNIQUE,
                    source_date TEXT NOT NULL,
                    source_hour INTEGER NOT NULL CHECK(source_hour BETWEEN 0 AND 23),
                    pm25 REAL CHECK(pm25 >= 0), pm10 REAL CHECK(pm10 >= 0),
                    no2 REAL CHECK(no2 >= 0), so2 REAL CHECK(so2 >= 0),
                    co REAL CHECK(co >= 0), o3 REAL CHECK(o3 >= 0)
                );
                CREATE TABLE import_metadata (
                    baseline_sha256 TEXT NOT NULL, record_count INTEGER NOT NULL,
                    pm25_valid_count INTEGER NOT NULL, imported_at_utc TEXT NOT NULL,
                    schema_version INTEGER NOT NULL
                );
            ''')
            connection.executemany('INSERT INTO air_quality_hourly (source_label_datetime,source_date,source_hour,pm25,pm10,no2,so2,co,o3) VALUES (?,?,?,?,?,?,?,?,?)', rows.itertuples(index=False, name=None))
            metadata = {'baseline_sha256': source_sha, 'record_count': len(frame), 'pm25_valid_count': int(frame['PM2.5'].count()),
                        'imported_at_utc': datetime.now(timezone.utc).isoformat(), 'schema_version': 1}
            connection.execute('INSERT INTO import_metadata VALUES (?,?,?,?,?)', tuple(metadata.values()))
            connection.commit()
        if sha256(baseline) != source_sha:
            raise RuntimeError('导入期间基线变更，未发布查询库')
        staging.replace(path)
        return metadata
    finally:
        if staging.exists():
            staging.unlink()


def time_text(value):
    return value.strftime('%Y-%m-%d %H:%M:%S')


def range_clause(start, end):
    parts, args = [], []
    if start is not None:
        parts.append('source_label_datetime >= ?'); args.append(time_text(start))
    if end is not None:
        parts.append('source_label_datetime <= ?'); args.append(time_text(end))
    return (' WHERE ' + ' AND '.join(parts) if parts else ''), args


class AirRepository:
    def __init__(self, path):
        self.path = Path(path)

    def query(self, sql, parameters=()):
        with closing(readonly(self.path)) as connection:
            return [dict(row) for row in connection.execute(sql, parameters).fetchall()]

    def by_time(self, value):
        rows = self.query('SELECT * FROM air_quality_hourly WHERE source_label_datetime=?', [time_text(value)])
        return rows[0] if rows else None

    def by_times(self, times):
        labels = [time_text(value) for value in times]
        rows = self.query('SELECT * FROM air_quality_hourly WHERE source_label_datetime IN (' + ','.join('?' for _ in labels) + ')', labels)
        return {row['source_label_datetime']: row for row in rows}

    def latest(self):
        rows = self.query('SELECT * FROM air_quality_hourly WHERE pm25 IS NOT NULL ORDER BY source_label_datetime DESC LIMIT 1')
        return rows[0] if rows else None

    def history(self, start, end, limit):
        where, args = range_clause(start, end)
        count = self.query('SELECT COUNT(*) AS n FROM air_quality_hourly' + where, args)[0]['n']
        records = self.query('SELECT * FROM air_quality_hourly' + where + ' ORDER BY source_label_datetime LIMIT ?', args + [limit])
        return {'records': records, 'returned': len(records), 'total_matches': count, 'truncated': count > len(records)}

    def summary(self, start, end):
        where, args = range_clause(start, end)
        row = self.query('''SELECT MIN(source_label_datetime) AS start_time, MAX(source_label_datetime) AS end_time,
            COUNT(*) AS total_records, COUNT(pm25) AS pm25_valid_count, AVG(pm25) AS pm25_mean,
            MAX(pm25) AS pm25_max, MIN(pm25) AS pm25_min, SUM(pm25*pm25) AS sum_squares
            FROM air_quality_hourly''' + where, args)[0]
        n, mean, squares = row['pm25_valid_count'], row['pm25_mean'], row.pop('sum_squares')
        row['pm25_std'] = math.sqrt(max(0, (squares - n * mean * mean) / (n - 1))) if n > 1 else None
        return row

    def aggregate(self, columns, start, end, granularity, limit):
        where, args = range_clause(start, end)
        bucket = {'hour': 'source_label_datetime', 'day': 'substr(source_label_datetime,1,10)',
                  'month': 'substr(source_label_datetime,1,7)'}[granularity]
        selections = [f'{bucket} AS period', 'COUNT(*) AS record_count']
        for column in columns:
            selections += [f'AVG({column}) AS {column}', f'COUNT({column}) AS {column}_valid_count']
        group = ' FROM air_quality_hourly' + where + f' GROUP BY {bucket}'
        count = self.query('SELECT COUNT(*) AS n FROM (SELECT ' + bucket + group + ')', args)[0]['n']
        points = self.query('SELECT ' + ','.join(selections) + group + ' ORDER BY period LIMIT ?', args + [limit])
        return points, count

    def correlation(self, start, end):
        where, args = range_clause(start, end)
        rows = self.query('SELECT ' + ','.join(COLUMNS) + ' FROM air_quality_hourly' + where, args)
        frame = pd.DataFrame(rows, columns=COLUMNS, dtype=float)
        coefficients = frame.corr(min_periods=2)
        counts = frame.notna().astype(int).T.dot(frame.notna().astype(int))
        return {'record_count': len(frame),
                'matrix': {a: {b: float(coefficients.loc[a, b]) if pd.notna(coefficients.loc[a, b]) else None for b in COLUMNS} for a in COLUMNS},
                'pair_counts': counts.to_dict()}
