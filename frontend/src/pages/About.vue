<script setup>
import { onMounted } from 'vue'
import { api } from '../api/index.js'
import { useRequest } from '../useRequest.js'
import { formatNumber as number, showTime } from '../utils.js'
import RequestState from '../components/RequestState.vue'
const {data,loading,error,run}=useRequest()
function load(){run(async()=>{const [model,summary]=await Promise.all([api.modelInfo(),api.summary()]);return {model,summary}})}
onMounted(load)
</script>
<template>
  <section class="page-heading"><div><p class="eyebrow">模型卡 · 数据边界</p><h1>模型与数据说明</h1><p>透明呈现模型能力、数据来源和使用范围。</p></div></section>
  <RequestState :loading="loading" :error="error" @retry="load" />
  <template v-if="data && !loading"><section class="panel about-model"><p class="eyebrow">冻结模型</p><h2>{{data.model.model_name}}</h2><p class="model-version">{{data.model.model_version}}</p><div class="summary-grid"><div><span>预测目标</span><strong>{{data.model.forecast_target}}</strong></div><div><span>预测提前量</span><strong>下一小时</strong></div><div><span>原始输入字段</span><strong>{{data.model.feature_count}}</strong></div><div><span>编码后字段</span><strong>{{data.model.encoded_feature_count}}</strong></div></div></section>
    <section class="panel"><div class="panel-heading"><h2>冻结实验成绩</h2><span class="muted">API读取 · 非重新评价</span></div><table class="scores-table"><thead><tr><th>数据分区</th><th>MAE（μg/m³）</th><th>RMSE（μg/m³）</th><th>R²</th></tr></thead><tbody><tr v-for="[key,title] in [['validation','Validation'],['test','Test']]" :key="key"><th>{{title}}</th><td>{{number(data.model[key].MAE,6)}}</td><td>{{number(data.model[key].RMSE,6)}}</td><td>{{number(data.model[key].R2,6)}}</td></tr></tbody></table><p class="chart-note">按 Validation MAE 选模；不表示所有指标都优于 Persistence。测试期描述数据曾用于 EDA，不属于完全盲测。</p></section>
    <section class="panel"><div class="panel-heading"><h2>数据与系统边界</h2><span class="subtle-tag">本地历史归档</span></div><dl class="data-description"><div><dt>数据范围</dt><dd>{{showTime(data.summary.start_time)}} 至 {{showTime(data.summary.end_time)}}</dd></div><div><dt>模型训练期</dt><dd>{{data.model.training_period.join(' 至 ')}}</dd></div><div><dt>数据来源</dt><dd>通过 QuotSoft 历史归档获得的成都城市级空气质量。</dd></div><div><dt>时间语义</dt><dd>使用无时区源时间标签，精确时区与真实发布延迟尚未确认。</dd></div><div><dt>系统范围</dt><dd>本地历史空气质量分析与冻结模型下一小时 PM2.5 预测。</dd></div><div><dt>当前边界</dt><dd>不属于实时官方空气质量发布平台；当前不融合气象数据。</dd></div></dl></section>
  </template>
</template>
