"""Two M4 acceptance rounds: unittest+HTTP smoke, then real HTTP samples."""
import json
import math
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager, closing
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app
from app.database import BASELINE, DATABASE, initialize_database, readonly, sha256
from app.main import create_app
from app.model_service import FrozenModel, MODEL_DIR, FIELDS
from app.schemas import (AirRecord, Correlation, Failure, HistoryPage, ManualPrediction,
                         ModelInfo, PollutantsTrend, Prediction, Success, Summary, Trend)
from fastapi.testclient import TestClient
from predict_chengdu_pm25 import load_artifact, predict_raw
import pandas as pd

OUT = ROOT / 'outputs/system'
TEMP_ROOT = ROOT / '.runtime/m4_checks'
TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def samples():
    matrix = pd.read_csv(ROOT / 'outputs/modeling/M3监督学习矩阵.csv')
    sample = matrix.loc[matrix['split'] == 'TEST'].iloc[100]
    features = {field: (int(sample[field]) if field in ['source_hour', 'day_of_week', 'month'] else float(sample[field])) for field in FIELDS}
    plan = pd.read_csv(ROOT / 'outputs/analysis/M2预测样本可用性索引.csv')
    gap = plan.loc[plan['eligible_current_target_pair'] & ~plan['lag_1_available'] & (plan['origin_datetime'] > '2020-01-08')].iloc[0]
    return sample['origin_datetime'].replace(' ', 'T'), features, gap['origin_datetime'].replace(' ', 'T')


def assert_success(response, schema):
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['success'] is True and 'error' not in payload
    Success[schema].model_validate(payload)
    return payload['data']


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.origin, cls.features, cls.gap = samples()
        cls.backend = create_app()
        from app.model_service import load_artifact as real_loader
        cls.load_patch = patch('app.model_service.load_artifact', wraps=real_loader)
        cls.loader = cls.load_patch.start()
        cls.client = TestClient(cls.backend, raise_server_exceptions=False)
        cls.client.__enter__()
        cls.baseline = pd.read_csv(BASELINE)

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.load_patch.stop()

    def error(self, response, status, code=None):
        self.assertEqual(response.status_code, status, response.text)
        payload = response.json()
        Failure.model_validate(payload)
        self.assertFalse(payload['success'])
        self.assertNotIn('data', payload)
        if code:
            self.assertEqual(payload['error']['code'], code)
        return payload

    def test_database_idempotence_and_rebuild(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            path = Path(directory) / 'query.db'
            before = sha256(BASELINE)
            first = initialize_database(path)
            digest = sha256(path)
            second = initialize_database(path)
            self.assertEqual(first, second)
            self.assertEqual(sha256(path), digest)
            rebuilt = initialize_database(path, rebuild=True)
            self.assertEqual(rebuilt['record_count'], 58537)
            with closing(readonly(path)) as connection:
                self.assertEqual(connection.execute('SELECT COUNT(pm25) FROM air_quality_hourly').fetchone()[0], 58337)
                self.assertTrue(connection.execute("PRAGMA index_list('air_quality_hourly')").fetchall())
                with self.assertRaises(sqlite3.OperationalError):
                    connection.execute('DELETE FROM air_quality_hourly')
            self.assertEqual(sha256(BASELINE), before)

    def test_history_range_and_inclusive_end(self):
        data = assert_success(self.client.get('/api/air-quality', params={'start': '2020-01-01T00:00:00', 'end': '2020-01-01T02:00:00', 'limit': 2}), HistoryPage)
        self.assertEqual(data['total_matches'], 3)
        self.assertEqual(data['returned'], 2)
        self.assertTrue(data['truncated'])
        self.assertEqual(data['records'][0]['pm25'], 117.0)
        self.assertIsNone(datetime.fromisoformat(data['records'][0]['source_label_datetime']).tzinfo)
        full = assert_success(self.client.get('/api/air-quality', params={'limit': 1}), HistoryPage)
        self.assertEqual(full['total_matches'], 58537)

    def test_point_and_no_invented_aqi(self):
        data = assert_success(self.client.get('/api/air-quality/' + self.origin), AirRecord)
        self.assertEqual(data['pm25'], self.features['pm25_t'])
        self.assertNotIn('aqi', data)

    def test_latest_route_precedence(self):
        data = assert_success(self.client.get('/api/air-quality/latest'), AirRecord)
        latest = self.baseline.loc[self.baseline['PM2.5'].notna()].iloc[-1]
        self.assertEqual(data['source_label_datetime'], latest['source_label_datetime'].replace(' ', 'T'))

    def test_nonexistent_and_unknown_route(self):
        self.error(self.client.get('/api/air-quality/2019-01-01T00:00:00'), 404, 'RECORD_NOT_FOUND')
        self.error(self.client.get('/not-a-route'), 404, 'HTTP_ERROR')

    def test_range_and_limit_errors(self):
        self.error(self.client.get('/api/air-quality', params={'start': '2026-01-02T00:00:00', 'end': '2026-01-01T00:00:00'}), 400, 'INVALID_TIME_RANGE')
        for value in [0, 10001]:
            self.error(self.client.get('/api/air-quality', params={'limit': value}), 422, 'VALIDATION_ERROR')

    def test_source_time_validation(self):
        for value in ['2026-01-01', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00+08:00', '2026-02-30T00:00:00']:
            self.error(self.client.get('/api/air-quality', params={'start': value}), 422, 'VALIDATION_ERROR')
        self.error(self.client.post('/api/predictions/by-time', json={'origin_time': '2026-01-01T00:30:00'}), 422, 'VALIDATION_ERROR')

    def test_summary_values_and_sample_std(self):
        data = assert_success(self.client.get('/api/analysis/summary'), Summary)
        values = self.baseline['PM2.5'].dropna()
        self.assertEqual(data['total_records'], 58537)
        self.assertEqual(data['pm25_valid_count'], 58337)
        self.assertAlmostEqual(data['pm25_mean'], values.mean(), places=9)
        self.assertAlmostEqual(data['pm25_std'], values.std(ddof=1), places=9)
        self.assertEqual(data['pm25_min'], values.min())
        self.assertEqual(data['pm25_max'], values.max())

    def test_trend_aggregation_and_whitelist(self):
        expected = self.baseline.loc[self.baseline['source_label_datetime'].str.startswith('2020-01-01'), 'PM2.5']
        params = {'start': '2020-01-01T00:00:00', 'end': '2020-01-01T23:00:00', 'metric': 'PM2.5'}
        data = assert_success(self.client.get('/api/analysis/trend', params={**params, 'granularity': 'day'}), Trend)
        self.assertAlmostEqual(data['points'][0]['value'], expected.mean())
        self.assertEqual(data['points'][0]['valid_count'], expected.count())
        for granularity in ['hour', 'month']:
            assert_success(self.client.get('/api/analysis/trend', params={**params, 'granularity': granularity}), Trend)
        self.error(self.client.get('/api/analysis/trend', params={'metric': 'AQI'}), 422, 'VALIDATION_ERROR')
        self.error(self.client.get('/api/analysis/trend', params={'granularity': 'year'}), 422, 'VALIDATION_ERROR')

    def test_multi_pollutants_units_and_counts(self):
        data = assert_success(self.client.get('/api/analysis/pollutants', params={'granularity': 'month', 'limit': 1}), PollutantsTrend)
        self.assertEqual(data['units']['co'], 'mg/m³')
        self.assertEqual(data['units']['pm25'], 'μg/m³')
        self.assertEqual(set(data['points'][0]['values']), {'pm25', 'pm10', 'no2', 'so2', 'co', 'o3'})
        self.assertEqual(data['total_points'], 81)
        self.assertTrue(data['truncated'])

    def test_correlation_pair_counts_and_empty_ranges(self):
        data = assert_success(self.client.get('/api/analysis/correlation', params={'start': '2020-01-01T00:00:00', 'end': '2020-01-01T23:00:00'}), Correlation)
        selected = self.baseline.loc[self.baseline['source_label_datetime'].str.startswith('2020-01-01')]
        self.assertAlmostEqual(data['matrix']['pm25']['pm10'], selected['PM2.5'].corr(selected['PM10']))
        self.assertEqual(data['pair_counts']['pm25']['pm10'], int(selected[['PM2.5', 'PM10']].notna().all(axis=1).sum()))
        params = {'start': '2030-01-01T00:00:00'}
        empty = assert_success(self.client.get('/api/analysis/summary', params=params), Summary)
        self.assertEqual(empty['total_records'], 0)
        self.assertIsNone(empty['pm25_std'])
        correlation = assert_success(self.client.get('/api/analysis/correlation', params=params), Correlation)
        self.assertEqual(correlation['record_count'], 0)
        self.assertIsNone(correlation['matrix']['pm25']['pm10'])

    def test_model_loaded_once_and_schema(self):
        self.client.get('/api/model/info')
        self.client.post('/api/predictions/manual', json=self.features)
        self.assertEqual(self.loader.call_count, 1)
        frozen = self.backend.state.frozen_model
        self.assertEqual(frozen.metadata['raw_feature_order'], FIELDS)
        self.assertEqual(len(frozen.preprocessor.get_feature_names_out()), 55)

    def test_model_startup_failure_is_explicit(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as directory:
            empty = Path(directory)
            with self.assertRaisesRegex(RuntimeError, '缺失'):
                FrozenModel(empty)
            for name in ['最终模型.joblib', '最终预处理器.joblib', '模型元数据.json', '模型冻结记录.json']:
                shutil.copyfile(MODEL_DIR / name, empty / name)
            metadata = json.loads((empty / '模型元数据.json').read_text(encoding='utf-8'))
            metadata['model_version'] = 'WRONG'
            save_json(empty / '模型元数据.json', metadata)
            with self.assertRaisesRegex(RuntimeError, '版本'):
                FrozenModel(empty)
            metadata['model_version'] = '成都PM25_1H_V1_20261005'
            metadata['raw_feature_order'] = FIELDS[::-1]
            save_json(empty / '模型元数据.json', metadata)
            with self.assertRaisesRegex(RuntimeError, 'Schema'):
                FrozenModel(empty)

    def test_history_prediction_matches_m3(self):
        data = assert_success(self.client.post('/api/predictions/by-time', json={'origin_time': self.origin}), Prediction)
        frozen = self.backend.state.frozen_model
        expected = predict_raw(frozen.model, frozen.preprocessor, frozen.metadata, pd.DataFrame([self.features], columns=FIELDS))[0]
        self.assertAlmostEqual(data['predicted_pm25'], expected, places=10)
        self.assertEqual(data['target_time'], (datetime.fromisoformat(self.origin) + timedelta(hours=1)).isoformat())

    def test_missing_exact_lag_is_named(self):
        payload = self.error(self.client.post('/api/predictions/by-time', json={'origin_time': self.gap}), 400, 'MODEL_INPUT_INCOMPLETE')
        self.assertIn('pm25_lag_1', payload['error']['details']['missing_fields'])

    def test_actual_target_not_a_model_input(self):
        frozen = self.backend.state.frozen_model
        expected = frozen.predict(self.features)['predicted_pm25']
        repository = self.backend.state.repository
        with patch.object(repository, 'by_time', return_value={'pm25': 999999.0}):
            data = assert_success(self.client.post('/api/predictions/by-time', json={'origin_time': self.origin}), Prediction)
        self.assertEqual(data['actual_pm25'], 999999.0)
        self.assertAlmostEqual(data['predicted_pm25'], expected, places=10)

    def test_manual_prediction_and_object_key_order(self):
        features = dict(reversed(list(self.features.items())))
        manual = assert_success(self.client.post('/api/predictions/manual', json=features), ManualPrediction)
        historical = assert_success(self.client.post('/api/predictions/by-time', json={'origin_time': self.origin}), Prediction)
        self.assertAlmostEqual(manual['predicted_pm25'], historical['predicted_pm25'], places=10)
        self.assertNotIn('origin_time', manual)

    def test_manual_missing_negative_and_wrong_type(self):
        bad = self.features.copy(); bad.pop('pm25_lag_24')
        self.error(self.client.post('/api/predictions/manual', json=bad), 422, 'VALIDATION_ERROR')
        for value in [-1, '3', True, None]:
            self.error(self.client.post('/api/predictions/manual', json={**self.features, 'pm25_t': value}), 422, 'VALIDATION_ERROR')
        self.error(self.client.post('/api/predictions/manual', json={**self.features, 'target_pm25': 42}), 422, 'VALIDATION_ERROR')

    def test_manual_calendar_ranges_and_nonfinite(self):
        for field, value in [('source_hour', 24), ('source_hour', 12.5), ('day_of_week', 7), ('month', 0), ('month', 13)]:
            self.error(self.client.post('/api/predictions/manual', json={**self.features, field: value}), 422, 'VALIDATION_ERROR')
        for value in [math.nan, math.inf, -math.inf]:
            body = json.dumps({**self.features, 'pm25_t': value})
            self.error(self.client.post('/api/predictions/manual', content=body, headers={'Content-Type': 'application/json'}), 422, 'VALIDATION_ERROR')

    def test_latest_origin_without_target(self):
        data = assert_success(self.client.post('/api/predictions/by-time', json={'origin_time': '2026-09-26T23:00:00'}), Prediction)
        self.assertEqual(data['target_time'], '2026-09-27T00:00:00')
        self.assertIsNone(data['actual_pm25'])

    def test_model_info_no_paths_and_saved_scores(self):
        data = assert_success(self.client.get('/api/model/info'), ModelInfo)
        self.assertEqual(data['feature_count'], 18)
        self.assertEqual(data['encoded_feature_count'], 55)
        self.assertEqual(data['model_version'], '成都PM25_1H_V1_20261005')
        self.assertAlmostEqual(data['test']['MAE'], 2.0434112843309045)
        self.assertEqual(data['test_blind_status'], 'NOT_BLIND_EDA_EXPOSED')
        self.assertNotIn('E:', json.dumps(data))

    def test_error_500_envelope_and_no_internal_path(self):
        with patch.object(self.backend.state.repository, 'latest', side_effect=RuntimeError('E:/private/path')):
            with self.assertLogs('app.main', level='ERROR'):
                payload = self.error(self.client.get('/api/air-quality/latest'), 500, 'INTERNAL_ERROR')
        self.assertNotIn('private', json.dumps(payload))

    def test_openapi_schemas_and_swagger(self):
        response = self.client.get('/openapi.json')
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertEqual(len(schema['paths']), 10)
        manual = schema['components']['schemas']['ManualRequest']
        self.assertEqual(set(manual['required']), set(FIELDS))
        self.assertFalse(manual['additionalProperties'])
        for route, methods in schema['paths'].items():
            for method, description in methods.items():
                self.assertIn('summary', description)
                for status in ['200', '400', '404', '422', '500']:
                    response_schema = description['responses'][status]['content']['application/json']['schema']
                    self.assertIn('$ref', response_schema)
                    self.assertIn(response_schema['$ref'].split('/')[-1], schema['components']['schemas'])
        docs = self.client.get('/docs')
        self.assertEqual(docs.status_code, 200)
        self.assertIn('SwaggerUIBundle', docs.text)
        save_json(OUT / 'M4_OpenAPI.json', schema)


def http_call(base, method, path, body=None):
    encoded = json.dumps(body, ensure_ascii=False).encode('utf-8') if body is not None else None
    request = Request(base + path, data=encoded, method=method, headers={'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, response.read().decode('utf-8')
    except HTTPError as response:
        return response.code, response.read().decode('utf-8')


@contextmanager
def live_server(label):
    with socket.socket() as socket_handle:
        socket_handle.bind(('127.0.0.1', 0))
        port = socket_handle.getsockname()[1]
    code = f"import sys; sys.path.insert(0, {str(ROOT)!r}); import app; import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', port={port}, workers=1)"
    log_path = OUT / f'M4_{label}服务日志.txt'
    environment = os.environ.copy()
    environment.update(PYTHONIOENCODING='utf-8', OMP_NUM_THREADS='4', OPENBLAS_NUM_THREADS='1')
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-c', code], cwd=ROOT, stdout=log, stderr=log, env=environment)
        base = f'http://127.0.0.1:{port}'
        try:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError('Owned smoke server failed; see ' + str(log_path))
                try:
                    status, text = http_call(base, 'GET', '/api/model/info')
                    assert status == 200
                    break
                except URLError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Owned server startup timed out')
                    time.sleep(.1)
            yield base
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()


def first_round():
    protected = [BASELINE, ROOT / 'docs/modeling/最终模型契约.md', ROOT / 'docs/modeling/M3模型实验报告.md',
                 ROOT / 'scripts/predict_chengdu_pm25.py'] + list(MODEL_DIR.glob('*'))
    before = {str(path.relative_to(ROOT)): sha256(path) for path in protected}
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ApiTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise AssertionError(f'M4 round1 automated tests failed: {len(result.failures)} failures, {len(result.errors)} errors')
    origin, features, gap = samples()
    smoke = []
    with live_server('第1轮') as base:
        for method, path, body, expected in [('GET', '/api/air-quality/latest', None, 200),
                                             ('POST', '/api/predictions/by-time', {'origin_time': origin}, 200),
                                             ('GET', '/openapi.json', None, 200)]:
            status, text = http_call(base, method, path, body)
            assert status == expected
            smoke.append({'method': method, 'path': path, 'http_status': status})
    for relative, sha in before.items():
        assert sha256(ROOT / relative) == sha, relative
    return {'result': 'PASS', 'automated_test_count': result.testsRun, 'automated_pass_count': result.testsRun,
            'http_smoke_test_count': len(smoke), 'http_smoke_tests': smoke,
            'protected_input_sha256': before, 'database_record_count': initialize_database()['record_count'],
            'model_api_matches_m3_predictor': True}


def second_round():
    origin, features, gap = samples()
    model, proc, metadata = load_artifact()
    expected = float(predict_raw(model, proc, metadata, pd.DataFrame([features], columns=FIELDS))[0])
    calls = [('GET', '/api/air-quality/' + origin, None, 200, AirRecord),
             ('POST', '/api/predictions/by-time', {'origin_time': origin}, 200, Prediction),
             ('POST', '/api/predictions/by-time', {'origin_time': gap}, 400, None),
             ('POST', '/api/predictions/manual', features, 200, ManualPrediction),
             ('GET', '/api/model/info', None, 200, ModelInfo), ('GET', '/docs', None, 200, None)]
    evidence = []
    with live_server('第2轮') as base:
        for method, path, body, expected_status, schema in calls:
            status, text = http_call(base, method, path, body)
            assert status == expected_status, text
            if path == '/docs':
                assert 'SwaggerUIBundle' in text and '/openapi.json' in text
                result = {'html_title': 'Swagger UI', 'openapi_url': '/openapi.json'}
            else:
                result = json.loads(text)
                if schema is None:
                    Failure.model_validate(result)
                    assert result['error']['code'] == 'MODEL_INPUT_INCOMPLETE'
                    assert 'pm25_lag_1' in result['error']['details']['missing_fields']
                else:
                    Success[schema].model_validate(result)
                    if schema in [Prediction, ManualPrediction]:
                        assert abs(result['data']['predicted_pm25'] - expected) < 1e-10
            evidence.append({'method': method, 'path': path, 'http_status': status, 'response': result})
    round1 = json.loads((OUT / 'M4验证第1轮.json').read_text(encoding='utf-8'))
    for relative, sha in round1['protected_input_sha256'].items():
        assert sha256(ROOT / relative) == sha, relative
    return {'result': 'PASS', 'method': 'Owned real Uvicorn subprocess on localhost, six HTTP calls; no TestClient',
            'sample_origin': origin, 'missing_exact_lag_origin': gap, 'raw_model_fields': features,
            'm3_direct_prediction': expected, 'http_sample_count': len(evidence), 'samples': evidence,
            'model_api_matches_m3_predictor': True, 'owned_server_stopped': True}


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    round_number = int(sys.argv[1])
    if round_number not in [1, 2]:
        raise SystemExit('Only M4 acceptance rounds 1 and 2 are permitted')
    record = OUT / f'M4验证第{round_number}轮.json'
    if record.exists():
        raise SystemExit('Accepted round already recorded; no repeated audit')
    if round_number == 2:
        assert json.loads((OUT / 'M4验证第1轮.json').read_text(encoding='utf-8'))['result'] == 'PASS'
    result = first_round() if round_number == 1 else second_round()
    save_json(record, result)
    print(f'M4_VALIDATION_ROUND_{round_number}=PASS')
