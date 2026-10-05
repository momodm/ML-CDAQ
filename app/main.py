"""M4 FastAPI routes; startup owns database initialization and model loading."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.database import BASELINE, DATABASE, AirRepository, initialize_database
from app.model_service import MODEL_DIR, RESULTS_FILE, FrozenModel, ServiceError
from app.schemas import (AirRecord, ByTimeRequest, Correlation, Failure, Granularity,
                         HistoryPage, ManualPrediction, ManualRequest, Metric, ModelInfo,
                         PollutantsTrend, Prediction, SourceTime, Success, Summary, Trend)
from app.services import check_range, pollutants, trend

Limit = Annotated[int, Query(ge=1, le=10000, description='最多返回条数，1–10000；结果显式说明是否截断')]


def create_app(database=DATABASE, baseline=BASELINE, model_dir=MODEL_DIR, results_file=RESULTS_FILE):
    @asynccontextmanager
    async def lifespan(application):
        application.state.import_metadata = initialize_database(Path(database), Path(baseline))
        application.state.repository = AirRepository(database)
        application.state.frozen_model = FrozenModel(model_dir, results_file)
        yield
        del application.state.frozen_model

    application = FastAPI(title='成都空气质量历史分析与 PM2.5 预测', version='M4_V1',
        description='本地历史归档查询与冻结模型单步预测。时间为无时区源标签，时区与真实发布延迟未确认。',
        lifespan=lifespan, responses={code: {'model': Failure, 'description': description} for code, description in
            [(400, '请求逻辑或历史模型输入不完整'), (404, '记录或接口不存在'), (422, '字段校验失败'), (500, '内部服务错误')]})

    def failure(status, code, message, details=None):
        body = Failure(error={'code': code, 'message': message, 'details': details})
        return JSONResponse(status_code=status, content=body.model_dump(mode='json'))

    @application.exception_handler(ServiceError)
    async def service_error(request, error):
        return failure(error.status, error.code, error.message, error.details)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        details = [{'field': '.'.join(map(str, item['loc'])), 'reason': item['msg']} for item in error.errors()]
        return failure(422, 'VALIDATION_ERROR', '请求字段格式、类型或范围不合法', details)

    @application.exception_handler(HTTPException)
    async def http_error(request, error):
        return failure(error.status_code, 'HTTP_ERROR', '接口不存在' if error.status_code == 404 else 'HTTP 请求错误')

    @application.exception_handler(Exception)
    async def internal_error(request, error):
        logging.getLogger(__name__).error('Backend request failed', exc_info=error)
        return failure(500, 'INTERNAL_ERROR', '内部服务错误，请查看后端日志')

    @application.get('/api/air-quality', response_model=Success[HistoryPage], tags=['历史空气质量'], summary='按源时间范围查询小时记录')
    def history(start: SourceTime | None = None, end: SourceTime | None = None, limit: Limit = 100):
        check_range(start, end)
        return {'data': application.state.repository.history(start, end, limit)}

    # Fixed routes precede the datetime route so "latest" is never parsed as a label.
    @application.get('/api/air-quality/latest', response_model=Success[AirRecord], tags=['历史空气质量'], summary='本地归档中最新 PM2.5 有效记录')
    def latest():
        row = application.state.repository.latest()
        if row is None:
            raise ServiceError(404, 'RECORD_NOT_FOUND', '本地没有有效 PM2.5 记录')
        return {'data': row}

    @application.get('/api/air-quality/{datetime}', response_model=Success[AirRecord], tags=['历史空气质量'], summary='查询一个精确源时间标签')
    def one(datetime: SourceTime):
        row = application.state.repository.by_time(datetime)
        if row is None:
            raise ServiceError(404, 'RECORD_NOT_FOUND', '指定源时间标签没有本地记录')
        return {'data': row}

    @application.get('/api/analysis/summary', response_model=Success[Summary], tags=['基础分析'], summary='查询库基本统计；标准差 ddof=1')
    def summary(start: SourceTime | None = None, end: SourceTime | None = None):
        check_range(start, end)
        return {'data': application.state.repository.summary(start, end)}

    @application.get('/api/analysis/trend', response_model=Success[Trend], tags=['基础分析'], summary='单污染物小时、日或月趋势')
    def single_trend(metric: Metric = 'PM2.5', start: SourceTime | None = None, end: SourceTime | None = None,
                     granularity: Granularity = 'day', limit: Limit = 1000):
        check_range(start, end)
        return {'data': trend(application.state.repository, metric, start, end, granularity, limit)}

    @application.get('/api/analysis/pollutants', response_model=Success[PollutantsTrend], tags=['基础分析'], summary='六污染物同期趋势与各自有效计数')
    def multiple_trend(start: SourceTime | None = None, end: SourceTime | None = None,
                       granularity: Granularity = 'day', limit: Limit = 1000):
        check_range(start, end)
        return {'data': pollutants(application.state.repository, start, end, granularity, limit)}

    @application.get('/api/analysis/correlation', response_model=Success[Correlation], tags=['基础分析'], summary='查询库六污染物 Pearson 相关与有效对数')
    def correlation(start: SourceTime | None = None, end: SourceTime | None = None):
        check_range(start, end)
        return {'data': application.state.repository.correlation(start, end)}

    @application.post('/api/predictions/by-time', response_model=Success[Prediction], tags=['模型预测'], summary='按历史原点查询精确 lag 并预测下一小时')
    def predict_by_time(body: ByTimeRequest):
        return {'data': application.state.frozen_model.by_time(application.state.repository, body.origin_time)}

    @application.post('/api/predictions/manual', response_model=Success[ManualPrediction], tags=['模型预测'], summary='严格18字段手工模型推理')
    def predict_manual(body: ManualRequest):
        return {'data': application.state.frozen_model.predict(body.model_dump())}

    @application.get('/api/model/info', response_model=Success[ModelInfo], tags=['模型信息'], summary='冻结模型与 M3 已保存成绩，不暴露内部路径')
    def model_info():
        return {'data': application.state.frozen_model.info()}

    return application


app = create_app()
