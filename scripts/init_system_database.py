"""Idempotent query-store initialization; explicit rebuild only."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.database import initialize_database


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='初始化成都系统查询库；不修改 M1 基线')
    parser.add_argument('--rebuild', action='store_true', help='明确从冻结 CSV 原子重建查询库')
    options = parser.parse_args()
    print(json.dumps(initialize_database(rebuild=options.rebuild), ensure_ascii=False, indent=2))
