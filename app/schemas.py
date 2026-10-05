"""Chinese API schemas; source labels have no timezone."""
import re
from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def naive_label(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', value):
        raise ValueError('请使用无时区 YYYY-MM-DDTHH:MM:SS，不接受偏移量或日期简写')
    return datetime.fromisoformat(value)


SourceTime = Annotated[datetime, BeforeValidator(naive_label)]
Concentration = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Metric = Literal['PM2.5', 'PM10', 'NO2', 'SO2', 'CO', 'O3']
Granularity = Literal['hour', 'day', 'month']
T = TypeVar('T')


class Success(BaseModel, Generic[T]):
    success: Literal[True] = True
    data: T


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | list | None = None


class Failure(BaseModel):
    success: Literal[False] = False
    error: ErrorDetail


class AirValues(BaseModel):
    pm25: float | None
    pm10: float | None
    no2: float | None
    so2: float | None
    co: float | None
    o3: float | None


class AirRecord(AirValues):
    id: int
    source_label_datetime: datetime
    source_date: str
    source_hour: int


class HistoryPage(BaseModel):
    records: list[AirRecord]
    returned: int
    total_matches: int
    truncated: bool
    time_semantics: Literal['NAIVE_SOURCE_LABEL'] = 'NAIVE_SOURCE_LABEL'


class Summary(BaseModel):
    start_time: datetime | None
    end_time: datetime | None
    total_records: int
    pm25_valid_count: int
    pm25_mean: float | None
    pm25_max: float | None
    pm25_min: float | None
    pm25_std: float | None
    std_ddof: Literal[1] = 1
    unit: Literal['μg/m³'] = 'μg/m³'
    time_semantics: Literal['NAIVE_SOURCE_LABEL'] = 'NAIVE_SOURCE_LABEL'


class TrendPoint(BaseModel):
    period: str
    value: float | None
    valid_count: int
    record_count: int


class Trend(BaseModel):
    metric: Metric
    unit: str
    granularity: Granularity
    points: list[TrendPoint]
    returned: int
    total_points: int
    truncated: bool
    time_semantics: Literal['NAIVE_SOURCE_LABEL'] = 'NAIVE_SOURCE_LABEL'


class PollutantPoint(BaseModel):
    period: str
    values: AirValues
    valid_counts: dict[str, int]
    record_count: int


class PollutantsTrend(BaseModel):
    granularity: Granularity
    units: dict[str, str]
    points: list[PollutantPoint]
    returned: int
    total_points: int
    truncated: bool
    time_semantics: Literal['NAIVE_SOURCE_LABEL'] = 'NAIVE_SOURCE_LABEL'


class Correlation(BaseModel):
    method: Literal['PEARSON_PAIRWISE_COMPLETE'] = 'PEARSON_PAIRWISE_COMPLETE'
    record_count: int
    matrix: dict[str, dict[str, float | None]]
    pair_counts: dict[str, dict[str, int]]


class ByTimeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    origin_time: SourceTime = Field(description='整点无时区源标签，例如 2026-06-01T12:00:00')

    @field_validator('origin_time')
    @classmethod
    def require_hour(cls, value):
        if value.minute or value.second:
            raise ValueError('预测原点必须是源标签整点')
        return value


class ManualRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pm25_t: Concentration = Field(description='t 的 PM2.5，μg/m³')
    pm25_lag_1: Concentration = Field(description='t−1小时的 PM2.5，μg/m³')
    pm25_lag_2: Concentration
    pm25_lag_3: Concentration
    pm25_lag_6: Concentration
    pm25_lag_12: Concentration
    pm25_lag_24: Concentration
    pm25_lag_48: Concentration
    pm25_lag_72: Concentration
    pm25_lag_168: Concentration
    pm10_t: Concentration
    no2_t: Concentration
    so2_t: Concentration
    co_t: Concentration = Field(description='t 的 CO，mg/m³')
    o3_t: Concentration
    source_hour: Annotated[int, Field(strict=True, ge=0, le=23)]
    day_of_week: Annotated[int, Field(strict=True, ge=0, le=6)]
    month: Annotated[int, Field(strict=True, ge=1, le=12)]


class Prediction(BaseModel):
    origin_time: datetime
    target_time: datetime
    predicted_pm25: float
    actual_pm25: float | None
    model_version: str
    unit: Literal['μg/m³'] = 'μg/m³'
    time_semantics: Literal['NAIVE_SOURCE_LABEL'] = 'NAIVE_SOURCE_LABEL'


class ManualPrediction(BaseModel):
    predicted_pm25: float
    model_version: str
    forecast_target: Literal['PM2.5'] = 'PM2.5'
    forecast_horizon: Literal['1H'] = '1H'
    unit: Literal['μg/m³'] = 'μg/m³'


class Scores(BaseModel):
    MAE: float
    RMSE: float
    R2: float


class ModelInfo(BaseModel):
    model_version: str
    model_name: str
    forecast_target: Literal['PM2.5'] = 'PM2.5'
    forecast_horizon: Literal['1H'] = '1H'
    feature_count: int
    encoded_feature_count: int
    training_period: list[str]
    validation: Scores
    test: Scores
    test_blind_status: str
    air_timezone: Literal['UNCONFIRMED'] = 'UNCONFIRMED'
    system_scope: str = '本地历史空气质量分析与冻结数据条件下的下一小时 PM2.5 预测'
