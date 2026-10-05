<script setup>
defineProps({ loading: Boolean, error: Object, empty: Boolean })
defineEmits(['retry'])
</script>
<template>
  <div v-if="loading" class="state-box" role="status" aria-live="polite"><el-skeleton :rows="4" animated /><p>正在读取本地数据…</p></div>
  <div v-else-if="error" class="error-box" role="alert">
    <strong>本次请求未完成</strong><p>{{ error.message }}</p>
    <details v-if="error.missingFields?.length"><summary>查看缺失字段（{{ error.missingFields.length }}）</summary><code>{{ error.missingFields.join('、') }}</code></details>
    <el-button @click="$emit('retry')">重试</el-button>
  </div>
  <el-empty v-else-if="empty" description="当前条件下暂无数据" :image-size="70" />
</template>
