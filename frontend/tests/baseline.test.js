import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createApi, paths } from '../src/api/index.js'
import { shiftLabel, nextPeriod, displayGaps, manualPayload, manualFields, lags, pollutants, rangeParams } from '../src/utils.js'
import { singleOption, multipleOption } from '../src/charts.js'

const api = createApi(process.env.M5_API_URL || 'http://127.0.0.1:5173/api')
test('源标签日历运算、缺口显示和表单边界', () => {
  assert.equal(shiftLabel('2024-03-01T00:00:00', -1), '2024-02-29T23:00:00')
  assert.equal(nextPeriod('2025-12', 'month'), '2026-01')
  const source = [{ period: '2026-01-01 00:00:00', value: 10 }, { period: '2026-01-01 02:00:00', value: 20 }]
  assert.equal(displayGaps(source, 'hour')[1].value, null)
  assert.equal(source.length, 2)
  assert.throws(() => manualPayload({}), /合法数值/)
  assert.throws(() => rangeParams('2026-02-01T00:00', '2026-01-01T00:00'), /开始时间/)
  const valid = Object.fromEntries(manualFields.map(f => [f.name, f.min || 0]))
  assert.equal(Object.keys(manualPayload(valid)).length, 18)
  for (const [key, value] of [['pm25_t', -1], ['co_t', Infinity], ['source_hour', 24], ['day_of_week', 1.5], ['month', 0]]) {
    assert.throws(() => manualPayload({ ...valid, [key]: value }), /合法数值/)
  }
})
test('统一 API 路径与冻结 M4 OpenAPI 一致', () => {
  const schema = JSON.parse(readFileSync(new URL('../../outputs/system/M4_OpenAPI.json', import.meta.url)))
  assert.deepEqual(Object.values(paths).map(p => '/api' + p).sort(), Object.keys(schema.paths).sort())
})
test('真实 Vite 代理：归档、统计、单位、缺失和模型信息', async () => {
  const [summary, latest, model, history, trend, multi, corr] = await Promise.all([
    api.summary(), api.latest(), api.modelInfo(), api.history({ limit: 3 }),
    api.trend({ metric: 'CO', granularity: 'hour', start: '2026-01-05T00:00:00', end: '2026-01-05T23:00:00' }),
    api.pollutants({ granularity: 'day', start: '2026-01-01T00:00:00', end: '2026-01-07T23:00:00' }),
    api.correlation({ start: '2026-01-01T00:00:00', end: '2026-01-07T23:00:00' }),
  ])
  assert.equal(summary.total_records, 58537)
  assert.equal(summary.pm25_valid_count, 58337)
  assert.equal(latest.source_label_datetime, '2026-09-26T23:00:00')
  assert.equal(model.feature_count, 18)
  assert.equal(model.encoded_feature_count, 55)
  assert.equal(history.returned, 3)
  assert.equal(trend.unit, 'mg/m³')
  assert.equal(singleOption(trend).series[0].connectNulls, false)
  const chart = multipleOption(multi)
  assert.equal(chart.series.find(s => s.name === 'CO').yAxisIndex, 1)
  assert.equal(chart.yAxis[1].name, 'mg/m³ · CO')
  assert.equal(corr.matrix.pm25.pm25, 1)
  assert.ok(corr.pair_counts.pm25.co > 0)
  await assert.rejects(api.point('2019-01-01T00:00:00'), e => e.code === 'RECORD_NOT_FOUND')
  await assert.rejects(api.summary({ start: '2026-02-01T00:00:00', end: '2026-01-01T00:00:00' }), e => e.code === 'INVALID_TIME_RANGE')
  await assert.rejects(api.manual({}), e => e.code === 'VALIDATION_ERROR')
  await assert.rejects(api.byTime('2020-01-22T05:00:00'), e => e.code === 'MODEL_INPUT_INCOMPLETE' && e.missingFields.length > 0)
})
test('真实历史和手工预测一致；无真实目标值时保留 null', async () => {
  const origin = '2026-01-05T22:00:00'
  const records = await Promise.all([api.point(origin), ...lags.map(k => api.point(shiftLabel(origin, -k)))])
  const raw = { pm25_t: records[0].pm25, source_hour: 22, day_of_week: 0, month: 1 }
  lags.forEach((k, i) => { raw[`pm25_lag_${k}`] = records[i + 1].pm25 })
  pollutants.slice(1).forEach(p => { raw[`${p.column}_t`] = records[0][p.column] })
  const [historical, manual, endpoint] = await Promise.all([api.byTime(origin), api.manual(manualPayload(raw)), api.byTime('2026-09-26T23:00:00')])
  assert.equal(historical.predicted_pm25, manual.predicted_pm25)
  assert.equal(historical.target_time, '2026-01-05T23:00:00')
  assert.equal(historical.actual_pm25, records[0].pm25 === null ? null : (await api.point(historical.target_time)).pm25)
  assert.equal(endpoint.actual_pm25, null)
  assert.equal(endpoint.target_time, '2026-09-27T00:00:00')
  assert.equal('target_time' in manual, false)
})

