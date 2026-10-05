"""Display analyses from the query database, without new research artifacts."""
from app.database import COLUMNS, METRICS, UNITS
from app.model_service import ServiceError


def check_range(start, end):
    if start is not None and end is not None and start > end:
        raise ServiceError(400, 'INVALID_TIME_RANGE', 'start 必须小于或等于 end')


def trend(repository, metric, start, end, granularity, limit):
    column = METRICS[metric]
    rows, count = repository.aggregate([column], start, end, granularity, limit)
    points = [{'period': row['period'], 'value': row[column], 'valid_count': row[column + '_valid_count'],
               'record_count': row['record_count']} for row in rows]
    return {'metric': metric, 'unit': UNITS[column], 'granularity': granularity, 'points': points,
            'returned': len(points), 'total_points': count, 'truncated': count > len(points)}


def pollutants(repository, start, end, granularity, limit):
    rows, count = repository.aggregate(COLUMNS, start, end, granularity, limit)
    points = [{'period': row['period'], 'values': {c: row[c] for c in COLUMNS},
               'valid_counts': {c: row[c + '_valid_count'] for c in COLUMNS}, 'record_count': row['record_count']} for row in rows]
    return {'units': UNITS, 'granularity': granularity, 'points': points,
            'returned': len(points), 'total_points': count, 'truncated': count > len(points)}
