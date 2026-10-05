import axios from 'axios'

export const paths = {
  history: '/air-quality', latest: '/air-quality/latest', point: '/air-quality/{datetime}',
  summary: '/analysis/summary', trend: '/analysis/trend', pollutants: '/analysis/pollutants',
  correlation: '/analysis/correlation', byTime: '/predictions/by-time',
  manual: '/predictions/manual', modelInfo: '/model/info',
}

export class ApiError extends Error {
  constructor(code, message, missingFields = []) {
    super(message)
    this.code = code
    this.missingFields = missingFields
  }
}

export function friendlyError(error) {
  if (error instanceof ApiError) return error
  const payload = error.response?.data?.error
  const status = error.response?.status
  if (!payload && (!status || status >= 500)) {
    return new ApiError('BACKEND_UNAVAILABLE', '后端服务暂时无法连接，请确认服务已启动后重试。')
  }
  const code = payload?.code || `HTTP_${status}`
  const messages = {
    MODEL_INPUT_INCOMPLETE: '该时间点缺少模型所需历史数据，无法进行预测。',
    INVALID_TIME_RANGE: '开始时间不能晚于结束时间，请调整查询范围。',
    RECORD_NOT_FOUND: '指定源时间标签没有本地历史记录。',
    VALIDATION_ERROR: '输入格式、类型或范围不合法，请检查表单后重试。',
    INTERNAL_ERROR: '服务暂时无法完成请求，请稍后重试。',
    MODEL_OUTPUT_INVALID: '模型未返回有效预测值，请稍后重试。',
  }
  const fallback = status === 404 ? '未找到请求的记录或接口。' : '请求未能完成，请检查输入或稍后重试。'
  const missing = Array.isArray(payload?.details?.missing_fields)
    ? payload.details.missing_fields.filter(value => /^[a-z0-9_]+$/.test(value)) : []
  return new ApiError(code, messages[code] || fallback, missing)
}

export function createApi(baseURL = '/api') {
  const client = axios.create({ baseURL, timeout: 10000 })
  async function request(url, options = {}) {
    try {
      const response = await client.request({ url, ...options })
      if (response.data?.success !== true) {
        throw friendlyError({ response })
      }
      return response.data.data
    } catch (error) {
      throw friendlyError(error)
    }
  }
  return {
    history: params => request(paths.history, { params }),
    latest: () => request(paths.latest),
    point: label => request(paths.point.replace('{datetime}', encodeURIComponent(label))),
    summary: params => request(paths.summary, { params }),
    trend: params => request(paths.trend, { params }),
    pollutants: params => request(paths.pollutants, { params }),
    correlation: params => request(paths.correlation, { params }),
    byTime: origin_time => request(paths.byTime, { method: 'POST', data: { origin_time } }),
    manual: data => request(paths.manual, { method: 'POST', data }),
    modelInfo: () => request(paths.modelInfo),
  }
}
export const api = createApi(import.meta.env?.VITE_API_BASE_URL || '/api')
