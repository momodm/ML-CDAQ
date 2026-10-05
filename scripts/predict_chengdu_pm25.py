"""Load the trusted M3 artifact and predict from ordered raw feature rows."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.runtime/m3_training'))
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import joblib
import numpy as np
import pandas as pd


def load_artifact(directory=ROOT / 'outputs/models'):
    directory = Path(directory)
    metadata = json.loads((directory / '模型元数据.json').read_text(encoding='utf-8'))
    return (joblib.load(directory / '最终模型.joblib'),
            joblib.load(directory / '最终预处理器.joblib'), metadata)


def predict_raw(model, preprocessor, metadata, frame):
    fields = metadata['raw_feature_order']
    if list(frame.columns) != fields:
        raise ValueError('Input columns must exactly match raw_feature_order')
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError('All raw inputs must be finite and nonnegative; no imputation')
    for field, domain in metadata['calendar_categories'].items():
        if not frame[field].isin(domain).all():
            raise ValueError('Invalid calendar category: ' + field)
    encoded = preprocessor.transform(frame)
    if isinstance(model, dict):
        return encoded[:, model['encoded_column_index']].copy()
    return model.predict(encoded)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: predict_chengdu_pm25.py INPUT_CSV OUTPUT_CSV')
    model, preprocessor, metadata = load_artifact()
    raw = pd.read_csv(sys.argv[1])
    result = pd.DataFrame({'predicted_pm25': predict_raw(model, preprocessor, metadata, raw)})
    result.to_csv(sys.argv[2], index=False, encoding='utf-8-sig')
