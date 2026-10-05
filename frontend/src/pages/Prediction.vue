<script setup>
import { reactive, ref, watch } from 'vue'
import { api } from '../api/index.js'
import { useRequest } from '../useRequest.js'
import { sourceTime, shiftLabel, manualFields, manualPayload, formatNumber as number, showTime, lags, pollutants } from '../utils.js'
import RequestState from '../components/RequestState.vue'
const tab=ref('history'),origin=ref('2026-01-05T22:00:00')
const history=useRequest(),manual=useRequest(),inputLoad=useRequest()
const values=reactive(Object.fromEntries(manualFields.map(field=>[field.name,''])))
watch(inputLoad.data, result=>{if(result) Object.assign(values,result.features)})
function clearOrigin(){history.clear();manual.clear();inputLoad.clear()}
function predictHistory(){history.run(()=>api.byTime(sourceTime(origin.value)))}
function predictManual(){manual.run(()=>api.manual(manualPayload(values)))}
async function loadInputs(){inputLoad.run(async()=>{
  manual.clear()
  Object.assign(values,Object.fromEntries(manualFields.map(field=>[field.name,''])))
  const label=sourceTime(origin.value)
  const records=await Promise.all([api.point(label),...lags.map(k=>api.point(shiftLabel(label,-k)))])
  const current=records[0], data={pm25_t:current.pm25,source_hour:current.source_hour,month:Number(label.slice(5,7))}
  // Calendar weekday from label components; no observed timezone is assigned.
  const weekday=new Date(Date.UTC(Number(label.slice(0,4)),Number(label.slice(5,7))-1,Number(label.slice(8,10)))).getUTCDay()
  data.day_of_week=(weekday+6)%7
  lags.forEach((k,index)=>{data[`pm25_lag_${k}`]=records[index+1].pm25})
  pollutants.slice(1).forEach(p=>{data[`${p.column}_t`]=current[p.column]})
  manualPayload(data)
  return {source:label,features:data}
})}
</script>
<template>
  <section class="page-heading"><div><p class="eyebrow">冻结模型 · 下一小时 · 18 个原始特征</p><h1>PM2.5 预测工作台</h1><p>使用预测原点及以前的信息，预测下一小时浓度。</p></div><span class="subtle-tag">固定模型 · 不重新训练</span></section>
  <el-tabs v-model="tab" class="prediction-tabs">
    <el-tab-pane label="历史时刻预测" name="history">
      <section class="panel"><form class="prediction-form" @submit.prevent="predictHistory"><label>预测原点 · 数据源时间<input type="datetime-local" step="3600" :disabled="history.loading.value || inputLoad.loading.value" v-model="origin" @input="clearOrigin" aria-label="预测原点 · 数据源时间" /></label><el-button type="primary" native-type="submit" :loading="history.loading.value">开始历史预测</el-button></form><p class="muted">系统自动查询精确小时 lag。若缺少必需字段，返回失败并保留缺失。</p></section>
      <RequestState :loading="history.loading.value" :error="history.error.value" @retry="predictHistory" />
      <section v-if="history.data.value && !history.loading.value" class="panel prediction-result"><p class="eyebrow">下一小时预测值</p><div class="forecast-value">{{number(history.data.value.predicted_pm25)}}<span>μg/m³</span></div><div class="result-grid"><div><span>预测原点</span><strong>{{showTime(history.data.value.origin_time)}}</strong></div><div><span>目标源时间</span><strong>{{showTime(history.data.value.target_time)}}</strong></div><div><span>历史真实 PM2.5</span><strong>{{history.data.value.actual_pm25 == null ? '目标时刻无历史真实值' : `${number(history.data.value.actual_pm25)} μg/m³`}}</strong></div><div v-if="history.data.value.actual_pm25 != null"><span>绝对误差 · 仅历史参考</span><strong>{{number(Math.abs(history.data.value.predicted_pm25-history.data.value.actual_pm25))}} μg/m³</strong></div></div><p class="model-version">模型版本：{{history.data.value.model_version}}</p></section>
    </el-tab-pane>
    <el-tab-pane label="手工输入预测" name="manual">
      <section class="panel"><div class="panel-heading"><div><h2>18 个必需输入</h2><p>所有 lag 均相对原点 t；手工输入无法确定唯一目标时间。</p></div></div><div class="manual-import"><label>读取输入的历史原点<input type="datetime-local" step="3600" :disabled="history.loading.value || inputLoad.loading.value" v-model="origin" aria-label="读取输入的历史原点" @input="clearOrigin" /></label><el-button @click="loadInputs" :loading="inputLoad.loading.value">从历史原点读取真实输入</el-button></div><RequestState :loading="inputLoad.loading.value" :error="inputLoad.error.value" @retry="loadInputs" /><p v-if="inputLoad.data.value" class="import-success">已从 {{showTime(inputLoad.data.value.source)}} 及指定历史标签读取输入，可编辑后预测。</p>
      <form @submit.prevent="predictManual" novalidate><div class="manual-grid"><label v-for="field in manualFields" :key="field.name" :for="`manual_${field.name}`">{{field.label}}<small>{{field.unit}}</small><input :id="`manual_${field.name}`" :name="field.name" type="number" :disabled="manual.loading.value || inputLoad.loading.value" :min="field.min || 0" :max="field.max" :step="field.integer ? 1 : 'any'" v-model="values[field.name]" @input="manual.clear" required /></label></div><div class="form-bottom"><span class="muted">前端基础校验，后端为最终校验准则。</span><el-button type="primary" native-type="submit" :loading="manual.loading.value">开始手工预测</el-button></div></form></section>
      <RequestState :loading="manual.loading.value" :error="manual.error.value" @retry="predictManual" /><section v-if="manual.data.value && !manual.loading.value" class="panel prediction-result"><p class="eyebrow">手工输入 · 下一小时 PM2.5</p><div class="forecast-value">{{number(manual.data.value.predicted_pm25)}}<span>μg/m³</span></div><p class="model-version">模型版本：{{manual.data.value.model_version}}</p><p class="muted">未提供唯一日期，不推测原点或目标时间。</p></section>
    </el-tab-pane>
  </el-tabs>
</template>
