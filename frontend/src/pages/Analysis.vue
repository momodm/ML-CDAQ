<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/index.js'
import { useRequest } from '../useRequest.js'
import { pollutants, rangeParams, shiftLabel } from '../utils.js'
import { singleOption } from '../charts.js'
import Chart from '../components/Chart.vue'
import RequestState from '../components/RequestState.vue'
const start = ref(''), end = ref(''), metric = ref('PM2.5'), granularity = ref('day')
const { data, loading, error, run, clear } = useRequest()
const option = computed(() => data.value ? singleOption(data.value) : {})
const validCount = computed(() => data.value?.points.reduce((sum,p) => sum+p.valid_count,0) || 0)
function load() { run(() => api.trend({ ...rangeParams(start.value,end.value), metric: metric.value, granularity: granularity.value })) }
onMounted(() => run(async () => {
  const latest = await api.latest()
  end.value = latest.source_label_datetime.replace(' ', 'T'); start.value = shiftLabel(end.value,-30*24)
  return api.trend({ ...rangeParams(start.value,end.value), metric: metric.value, granularity: granularity.value })
}))
</script>
<template>
  <section class="page-heading"><div><p class="eyebrow">按时间探索 · 六种污染物</p><h1>空气质量历史分析</h1><p>选择范围与粒度，查看已观测值的变化。</p></div></section>
  <form class="filter-panel" @submit.prevent="load"><label>开始源时间<input type="datetime-local" step="1" :disabled="loading" v-model="start" @input="clear" /></label><label>结束源时间<input type="datetime-local" step="1" :disabled="loading" v-model="end" @input="clear" /></label><label>污染物<el-select :disabled="loading" v-model="metric" aria-label="污染物" @change="clear"><el-option v-for="p in pollutants" :key="p.metric" :label="p.metric" :value="p.metric" /></el-select></label><label>聚合粒度<el-select :disabled="loading" v-model="granularity" aria-label="聚合粒度" @change="clear"><el-option label="小时" value="hour" /><el-option label="日均" value="day" /><el-option label="月均" value="month" /></el-select></label><el-button type="primary" native-type="submit" :loading="loading">查询趋势</el-button></form>
  <RequestState :loading="loading" :error="error" :empty="data && !data.points.length" @retry="load" />
  <section v-if="data?.points.length && !loading" class="panel"><div class="panel-heading"><div><h2>{{data.metric}} 浓度趋势</h2><p>单位 {{data.unit}} · {{data.returned}} 个返回数据点 · {{validCount}} 条有效记录</p></div><span class="subtle-tag">{{{hour:'小时',day:'日均',month:'月均'}[data.granularity]}}</span></div><p v-if="data.truncated" class="notice">范围内共有 {{data.total_points}} 个聚合点，当前只返回前 {{data.returned}} 个；请缩小范围。</p><Chart :option="option" :height="420" :label="`${data.metric} 历史趋势，单位${data.unit}`" /><p class="chart-note">聚合均值仅使用查询范围内非空值；缺失值及未出现时刻不补齐。</p></section>
  <p v-if="!data && !loading && !error" class="muted">条件已变更，点击“查询趋势”读取新结果。</p>
</template>
