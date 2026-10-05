"""Local single-process backend launcher, localhost only."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app
import uvicorn


if __name__ == '__main__':
    uvicorn.run('app.main:app', host='127.0.0.1', port=8000, workers=1)
