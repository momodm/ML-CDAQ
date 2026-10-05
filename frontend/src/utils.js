export const pollutants = [
  { metric: 'PM2.5', column: 'pm25', unit: 'μg/m³', color: '#0b7668' },
  { metric: 'PM10', column: 'pm10', unit: 'μg/m³', color: '#547cac' },
  { metric: 'NO2', column: 'no2', unit: 'μg/m³', color: '#ad6f59' },
  { metric: 'SO2', column: 'so2', unit: 'μg/m³', color: '#8a739d' },
  { metric: 'CO', column: 'co', unit: 'mg/m³', color: '#d69a29' },
  { metric: 'O3', column: 'o3', unit: 'μg/m³', color: '#50999b' },
]
export const lags = [1, 2, 3, 6, 12, 24, 48, 72, 168]
export const manualFields = [
  { name: 'pm25_t', label: '当前 PM2.5', unit: 'μg/m³' },
  ...lags.map(k => ({ name: `pm25_lag_${k}`, label: `PM2.5 · t−${k}h`, unit: 'μg/m³' })),
  ...pollutants.slice(1).map(p => ({ name: `${p.column}_t`, label: `当前 ${p.metric}`, unit: p.unit })),
  { name: 'source_hour', label: '源小时', unit: '0–23', integer: true, max: 23 },
  { name: 'day_of_week', label: '星期（周一为0）', unit: '0–6', integer: true, max: 6 },
  { name: 'month', label: '月份', unit: '1–12', integer: true, min: 1, max: 12 },
]

export function formatNumber(value, digits = 2) {
  return value == null ? '—' : Number(value).toLocaleString('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: digits })
}
export const showTime = value => value?.replace('T', ' ') || '—'
export function sourceTime(value) {
  if (!value) throw new Error('请选择数据源时间。')
  return value.length === 16 ? `${value}:00` : value.replace(' ', 'T')
}

export function shiftLabel(value, hours) {
  // Calendar arithmetic on source components only: no browser-zone conversion or observed timezone assignment.
  const parts = value.replace('T', ' ').match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/)
  if (!parts) throw new Error('源时间格式不合法。')
  const [, y, m, d, h, minute, second] = parts.map(Number)
  const calendar = new Date(Date.UTC(y, m - 1, d, h, minute, second) + hours * 3600000)
  const pad = number => String(number).padStart(2, '0')
  return `${calendar.getUTCFullYear()}-${pad(calendar.getUTCMonth() + 1)}-${pad(calendar.getUTCDate())}T${pad(calendar.getUTCHours())}:${pad(calendar.getUTCMinutes())}:${pad(calendar.getUTCSeconds())}`
}

export function nextPeriod(period, granularity) {
  if (granularity === 'month') {
    const [y, m] = period.split('-').map(Number)
    return `${m === 12 ? y + 1 : y}-${String(m === 12 ? 1 : m + 1).padStart(2, '0')}`
  }
  const label = granularity === 'day' ? `${period}T00:00:00` : period.replace(' ', 'T')
  const next = shiftLabel(label, granularity === 'day' ? 24 : 1)
  return granularity === 'day' ? next.slice(0, 10) : next.replace('T', ' ')
}

export function displayGaps(points, granularity) {
  if (!points.length) return []
  const map = new Map(points.map(point => [point.period, point]))
  const result = []
  for (let period = points[0].period; period <= points.at(-1).period; period = nextPeriod(period, granularity)) {
    // Display-only missing slots. Counts and API observations are never expanded or filled.
    result.push(map.get(period) || { period, value: null, values: null })
  }
  return result
}

export function manualPayload(values) {
  const result = {}, invalid = []
  for (const field of manualFields) {
    const raw = values[field.name]
    const value = raw === '' || raw == null ? NaN : Number(raw)
    if (!Number.isFinite(value) || value < (field.min || 0) || value > (field.max ?? Infinity) || (field.integer && !Number.isInteger(value))) invalid.push(field.label)
    else result[field.name] = value
  }
  if (invalid.length) throw new Error(`请填写合法数值：${invalid.join('、')}。`)
  return result
}

export function rangeParams(start, end) {
  const first = start ? sourceTime(start) : undefined, last = end ? sourceTime(end) : undefined
  if (first && last && first > last) throw new Error('开始时间不能晚于结束时间。')
  return { start: first, end: last, limit: 10000 }
}
