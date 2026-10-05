import { createRouter, createWebHistory } from 'vue-router'

export const pages = [
  { path: '/', name: 'dashboard', title: '系统总览', component: () => import('./pages/Dashboard.vue') },
  { path: '/analysis', name: 'analysis', title: '历史分析', component: () => import('./pages/Analysis.vue') },
  { path: '/pollutants', name: 'pollutants', title: '污染物与相关性', component: () => import('./pages/Pollutants.vue') },
  { path: '/prediction', name: 'prediction', title: 'PM2.5 预测', component: () => import('./pages/Prediction.vue') },
  { path: '/about', name: 'about', title: '模型与数据说明', component: () => import('./pages/About.vue') },
]
export default createRouter({ history: createWebHistory(), routes: pages, scrollBehavior: () => ({ top: 0 }) })
