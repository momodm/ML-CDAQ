import { displayGaps, pollutants, formatNumber } from './utils.js'

const base = {
  textStyle: { fontFamily: 'Microsoft YaHei, sans-serif', color: '#61716e' },
  grid: { left: 64, right: 28, top: 60, bottom: 58 },
  legend: { top: 8 },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', boundaryGap: false, name: '源时间标签', nameLocation: 'middle', nameGap: 32,
    axisLine: { lineStyle: { color: '#d8e2df' } }, axisLabel: { formatter: value => value.slice(5, 16) } },
  yAxis: { type: 'value', name: 'μg/m³', splitLine: { lineStyle: { color: '#edf1f0' } } },
}

export function singleOption(result) {
  const points = displayGaps(result.points, result.granularity)
  const color = pollutants.find(p => p.metric === result.metric).color
  return { ...base, xAxis: { ...base.xAxis, data: points.map(p => p.period) },
    yAxis: { ...base.yAxis, name: result.unit },
    tooltip: { trigger: 'axis', valueFormatter: value => value == null ? '缺失' : `${formatNumber(value)} ${result.unit}` },
    series: [{ type: 'line', name: result.metric, data: points.map(p => p.value), connectNulls: false, showSymbol: points.length < 60,
      symbolSize: 4, lineStyle: { width: 2.2, color }, itemStyle: { color }, areaStyle: { color, opacity: .055 } }] }
}

export function multipleOption(result) {
  const points = displayGaps(result.points, result.granularity)
  return { ...base, grid: { ...base.grid, right: 65 },
    xAxis: { ...base.xAxis, data: points.map(p => p.period) },
    yAxis: [{ ...base.yAxis, name: 'μg/m³ · 非CO' }, { type: 'value', name: 'mg/m³ · CO', splitLine: { show: false } }],
    tooltip: { trigger: 'axis', formatter: entries => [entries[0]?.axisValue, ...entries.map(entry => {
      const unit = entry.seriesName === 'CO' ? 'mg/m³' : 'μg/m³'
      return `${entry.marker}${entry.seriesName}　${entry.value == null ? '缺失' : formatNumber(entry.value)} ${unit}`
    })].join('<br>') },
    series: pollutants.map(p => ({ type: 'line', name: p.metric, yAxisIndex: p.metric === 'CO' ? 1 : 0,
      data: points.map(point => point.values?.[p.column] ?? null), connectNulls: false, showSymbol: false,
      lineStyle: { width: 1.7, color: p.color }, itemStyle: { color: p.color } })) }
}

export function correlationOption(result) {
  const data = []
  pollutants.forEach((a, y) => pollutants.forEach((b, x) => {
    const value = result.matrix[a.column][b.column]
    if (value != null) data.push([x, y, value])
  }))
  const names = pollutants.map(p => p.metric)
  return { textStyle: base.textStyle, grid: { left: 70, right: 25, top: 22, bottom: 78 },
    xAxis: { type: 'category', data: names, splitArea: { show: true } },
    yAxis: { type: 'category', data: names, splitArea: { show: true } },
    tooltip: { formatter: ({ value }) => {
      const [x,y,correlation] = value
      return `${names[x]} / ${names[y]}<br>相关系数：${correlation.toFixed(3)}<br>有效对数：${result.pair_counts[pollutants[y].column][pollutants[x].column]}`
    } },
    visualMap: { min: -1, max: 1, calculable: false, orient: 'horizontal', left: 'center', bottom: 4,
      text: ['1 · 正相关', '−1 · 负相关'], inRange: { color: ['#d49b86', '#f6f7f4', '#267f74'] } },
    series: [{ type: 'heatmap', name: 'Pearson 相关系数', data, label: { show: true, formatter: params => params.value[2].toFixed(2) },
      itemStyle: { borderColor: '#fff', borderWidth: 3 } }] }
}
