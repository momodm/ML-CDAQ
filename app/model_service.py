"""Startup-only loading and exact-time historical inference."""
import json
import math
import threading
from datetime import timedelta
from pathlib import Path

from app import ROOT
from app.database import sha256, time_text
from app.schemas import ManualRequest
from predict_chengdu_pm25 import load_artifact, predict_raw
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

MODEL_DIR = ROOT / 'outputs/models'
RESULTS_FILE = ROOT / 'outputs/modeling/M3验收状态.json'
MODEL_VERSION = '成都PM25_1H_V1_20261005'
LAGS = [1, 2, 3, 6, 12, 24, 48, 72, 168]
FIELDS = list(ManualRequest.model_fields)


class ServiceError(Exception):
    def __init__(self, status, code, message, details=None):
        self.status, self.code, self.message, self.details = status, code, message, details


class FrozenModel:
    def __init__(self, directory=MODEL_DIR, results_file=RESULTS_FILE):
        directory = Path(directory)
        required = ['最终模型.joblib', '最终预处理器.joblib', '模型元数据.json', '模型冻结记录.json']
        if any(not (directory / name).is_file() for name in required):
            raise RuntimeError('冻结模型产物缺失，后端拒绝启动')
        metadata = json.loads((directory / '模型元数据.json').read_text(encoding='utf-8'))
        if metadata['model_version'] != MODEL_VERSION or metadata['model_name'] != 'HistGradientBoostingRegressor':
            raise RuntimeError('模型名称或版本不符，后端拒绝启动')
        if metadata['raw_feature_order'] != FIELDS or metadata['encoded_width'] != 55 or metadata['feature_set'] != 'B':
            raise RuntimeError('冻结原始字段 Schema 不符，后端拒绝启动')
        frozen = json.loads((directory / '模型冻结记录.json').read_text(encoding='utf-8'))
        for name in required[:3]:
            if sha256(directory / name) != frozen['artifact_sha256'][name]:
                raise RuntimeError('冻结模型产物哈希不符，后端拒绝启动')
        self.model, self.preprocessor, self.metadata = load_artifact(directory)
        if not isinstance(self.model, HistGradientBoostingRegressor) or self.model.n_features_in_ != 55:
            raise RuntimeError('模型对象类型或编码输入宽度不符')
        if self.preprocessor.feature_names_in_.tolist() != FIELDS or self.preprocessor.get_feature_names_out().tolist() != metadata['encoded_feature_order']:
            raise RuntimeError('保存预处理器的字段顺序不符')
        self.results = json.loads(Path(results_file).read_text(encoding='utf-8'))
        if self.results['M3_GATE'] != 'PASS' or self.results['FINAL_MODEL'] != metadata['model_name']:
            raise RuntimeError('模型缺少有效的 M3 验收结果')
        # ponytail: one inference lock per process; remove only after concurrent prediction benchmarks.
        self.lock = threading.Lock()

    def predict(self, features):
        frame = pd.DataFrame([[features[field] for field in FIELDS]], columns=FIELDS)
        with self.lock:
            value = float(predict_raw(self.model, self.preprocessor, self.metadata, frame)[0])
        if not math.isfinite(value):
            raise ServiceError(500, 'MODEL_OUTPUT_INVALID', '模型返回非有限预测值')
        return {'predicted_pm25': value, 'model_version': self.metadata['model_version']}

    def features_at(self, repository, origin):
        times = [origin] + [origin - timedelta(hours=k) for k in LAGS]
        records = repository.by_times(times)
        current = records.get(time_text(origin), {})
        values = {'pm25_t': current.get('pm25')}
        for k in LAGS:
            historical = records.get(time_text(origin - timedelta(hours=k)), {})
            values[f'pm25_lag_{k}'] = historical.get('pm25')
        for field, column in zip(['pm10_t', 'no2_t', 'so2_t', 'co_t', 'o3_t'], ['pm10', 'no2', 'so2', 'co', 'o3']):
            values[field] = current.get(column)
        values.update(source_hour=origin.hour, day_of_week=origin.weekday(), month=origin.month)
        missing = [field for field, value in values.items() if value is None or not math.isfinite(value) or value < 0]
        if missing:
            raise ServiceError(400, 'MODEL_INPUT_INCOMPLETE', '本地历史数据缺少模型必需字段，未插值或填补',
                               {'missing_fields': missing, 'origin_time': origin.isoformat()})
        return values

    def by_time(self, repository, origin):
        features = self.features_at(repository, origin)
        result = self.predict(features)
        target = origin + timedelta(hours=1)
        actual = repository.by_time(target)
        return {**result, 'origin_time': origin, 'target_time': target,
                'actual_pm25': actual['pm25'] if actual else None}

    def info(self):
        results, metadata = self.results, self.metadata
        return {'model_version': metadata['model_version'], 'model_name': metadata['model_name'],
                'feature_count': len(FIELDS), 'encoded_feature_count': 55, 'training_period': metadata['training_period'],
                'validation': metadata['validation_metrics'],
                'test': {key: results['FINAL_TEST_' + key] for key in ['MAE', 'RMSE', 'R2']},
                'test_blind_status': metadata['test_blind_status']}
