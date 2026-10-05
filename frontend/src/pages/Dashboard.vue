<script setup>
import { computed, onMounted } from 'vue'
import { api } from '../api/index.js'
import { useRequest } from '../useRequest.js'
import { formatNumber as number, showTime, shiftLabel, pollutants } from '../utils.js'
import { singleOption } from '../charts.js'
import Chart from '../components/Chart.vue'
import RequestState from '../components/RequestState.vue'
const { data, loading, error, run } = useRequest()
const option = computed(() => data.value ? singleOption(data.value.trend) : {})
function load() { run(async () => {
  const [summary, latest, model] = await Promise.all([api.summary(), api.latest(), api.modelInfo()])
  const start = shiftLabel(latest.source_label_datetime, -167)
  const trend = await api.trend({ metric: 'PM2.5', start, end: latest.source_label_datetime, granularity: 'hour', limit: 10000 })
  return { summary, latest, model, trend }
}) }
onMounted(load)
</script>
<template>
  <section class="page-heading"><div><p class="eyebrow">城市空气质量 · 数据工作台</p><h1>系统总览</h1><p>从历史数据出发，观察成都空气质量变化。</p></div><el-button @click="load" :loading="loading">刷新概览</el-button></section>
  <RequestState :loading="loading" :error="error" :empty="data && !data.summary.total_records" @retry="load" />
  <template v-if="data && !loading">
    <div class="overview-grid">
      <article class="stat-block"><span>数据开始时间</span><strong class="date-value">{{ showTime(data.summary.start_time) }}</strong><small>数据源时间</small></article>
      <article class="stat-block"><span>数据结束时间</span><strong class="date-value">{{ showTime(data.summary.end_time) }}</strong><small>数据源时间</small></article>
      <article class="stat-block"><span>数据库记录数</span><strong>{{ number(data.summary.total_records,0) }}</strong><small>城市级小时记录</small></article>
      <article class="stat-block"><span>PM2.5 有效记录数</span><strong>{{ number(data.summary.pm25_valid_count,0) }}</strong><small>保留原始缺失，不补齐</small></article>
    </div>
    <section class="panel latest-panel"><div class="panel-heading"><div><h2>本地数据最新记录</h2><p>源时间标签：{{ showTime(data.latest.source_label_datetime) }}</p></div><span class="subtle-tag">历史归档</span></div>
      <div class="pollutant-grid"><div v-for="p in pollutants" :key="p.column"><span><i :style="{background:p.color}" />{{ p.metric }}</span><strong>{{ number(data.latest[p.column]) }}</strong><small>{{ p.unit }}</small></div></div>
    </section>
    <div class="dashboard-columns">
      <section class="panel"><div class="panel-heading"><div><h2>归档末端 7 天 · PM2.5</h2><p>小时浓度 · μg/m³ · 缺失时刻保持断点</p></div><RouterLink to="/analysis" class="text-link">探索历史 →</RouterLink></div><Chart v-if="data.trend.points.length" :option="option" label="归档末端七天 PM2.5 小时趋势" /><el-empty v-else description="当前条件下暂无数据" /></section>
      <section class="panel model-card"><p class="eyebrow">冻结模型 · 1H</p><h2>下一小时 PM2.5 预测</h2><p class="model-name">{{ data.model.model_name }}</p><div class="score-list"><div><span>Test MAE</span><strong>{{ number(data.model.test.MAE,4) }}<small>μg/m³</small></strong></div><div><span>Test RMSE</span><strong>{{ number(data.model.test.RMSE,4) }}<small>μg/m³</small></strong></div><div><span>Test R²</span><strong>{{ number(data.model.test.R2,4) }}</strong></div></div><RouterLink to="/prediction" class="primary-link">进入预测工作台 →</RouterLink><p class="muted">固定模型，仅使用预测原点及以前的信息。</p></section>
    </div>
    <section class="panel"><div class="panel-heading"><h2>PM2.5 基础统计</h2><span class="muted">全归档有效值 · μg/m³</span></div><div class="summary-grid"><div v-for="[field,title] in [['pm25_mean','均值'],['pm25_max','最大值'],['pm25_min','最小值'],['pm25_std','标准差（ddof=1）']]" :key="field"><span>{{title}}</span><strong>{{number(data.summary[field])}}</strong></div></div></section>
  </template>
</template>
