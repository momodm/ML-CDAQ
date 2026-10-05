<script setup>
import { useRoute } from 'vue-router'
import { pages } from './router.js'
const route = useRoute()
const symbols = ['M4 14h16M4 8h10M4 20h13', 'M3 18l5-6 5 3 8-10', 'M5 5h5v5H5zM14 5h5v5h-5zM5 14h5v5H5zM14 14h5v5h-5z', 'M4 17l6-7 5 3 5-8M14 5h6v6', 'M12 11v7M12 7v1M4 4h16v16H4z']
</script>
<template>
  <div class="app-layout">
    <aside class="sidebar">
      <RouterLink to="/" class="brand"><span class="brand-symbol">蓉</span><span>成都空气质量<small>分析与预测系统</small></span></RouterLink>
      <p class="nav-caption">数据工作台</p>
      <nav aria-label="主导航"><RouterLink v-for="(page,index) in pages" :key="page.path" :to="page.path" :class="{active: route.name === page.name}"><svg viewBox="0 0 24 24" aria-hidden="true"><path :d="symbols[index]" /></svg>{{ page.title }}</RouterLink></nav>
      <div class="sidebar-note"><span class="archive-dot" />本地历史归档<small>城市级 · 成都<br>无时区源时间标签</small></div>
    </aside>
    <div class="workspace">
      <header class="topbar"><span>成都空气质量分析与预测系统</span><span class="scope-tag">历史数据研究展示</span></header>
      <main :key="route.path"><RouterView /></main>
      <footer>成都城市级历史空气质量 · 下一小时 PM2.5 预测<span>源标签时区未确认 · 非实时官方发布平台</span></footer>
    </div>
  </div>
</template>
