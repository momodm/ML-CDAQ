<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/index.js'
import { useRequest } from '../useRequest.js'
import { rangeParams, shiftLabel, pollutants } from '../utils.js'
import { multipleOption, correlationOption } from '../charts.js'
import Chart from '../components/Chart.vue'
import RequestState from '../components/RequestState.vue'
const start=ref(''),end=ref(''),granularity=ref('day')
const {data,loading,error,run,clear}=useRequest()
const trends=computed(()=>data.value?multipleOption(data.value.trend):{})
const correlation=computed(()=>data.value?correlationOption(data.value.correlation):{})
function query() { const params=rangeParams(start.value,end.value); return Promise.all([api.pollutants({...params,granularity:granularity.value}),api.correlation({start:params.start,end:params.end})]).then(([trend,correlation])=>({trend,correlation})) }
function load(){run(query)}
onMounted(()=>run(async()=>{const latest=await api.latest();end.value=latest.source_label_datetime.replace(' ','T');start.value=shiftLabel(end.value,-30*24);return query()}))
</script>
<template>
  <section class="page-heading"><div><p class="eyebrow">同期趋势 · Pearson 相关系数</p><h1>多污染物与相关性</h1><p>比较污染物变化，相关性不表示因果关系。</p></div></section>
  <form class="filter-panel" @submit.prevent="load"><label>开始源时间<input type="datetime-local" step="1" :disabled="loading" v-model="start" @input="clear" /></label><label>结束源时间<input type="datetime-local" step="1" :disabled="loading" v-model="end" @input="clear" /></label><label>聚合粒度<el-select :disabled="loading" v-model="granularity" aria-label="聚合粒度" @change="clear"><el-option label="小时" value="hour" /><el-option label="日均" value="day" /><el-option label="月均" value="month" /></el-select></label><el-button type="primary" native-type="submit" :loading="loading">查询污染物</el-button></form>
  <RequestState :loading="loading" :error="error" :empty="data && !data.trend.points.length" @retry="load" />
  <template v-if="data?.trend.points.length && !loading">
    <section class="panel"><div class="panel-heading"><div><h2>六污染物同期趋势</h2><p>{{data.trend.returned}} 个返回聚合点 · CO 使用右轴 mg/m³，其他污染物使用左轴 μg/m³</p></div></div><p v-if="data.trend.truncated" class="notice">结果已截断，请缩小范围；相关矩阵仍按完整查询范围计算。</p><Chart :option="trends" :height="350" label="六污染物同期趋势，CO右轴mg/m³，其他左轴μg/m³" /><div class="valid-counts"><span v-for="p in pollutants" :key="p.column">{{p.metric}} 有效：{{data.trend.points.reduce((n,row)=>n+row.valid_counts[p.column],0)}}</span></div></section>
    <section class="panel correlation-panel"><div class="panel-heading"><div><h2>Pearson 相关系数</h2><p>查询范围内 {{data.correlation.record_count}} 条原始小时记录 · 按有效配对计算</p></div><span class="subtle-tag">−1 至 1</span></div><Chart :option="correlation" :height="410" label="六污染物 Pearson 相关系数热力图" /><p class="chart-note">无定义的相关系数留空，不填零。悬停可查看相关系数及有效对数。</p></section>
  </template>
  <p v-if="!data && !loading && !error" class="muted">条件已变更，点击查询读取新结果。</p>
</template>
