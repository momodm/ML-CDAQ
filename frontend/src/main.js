import { createApp } from 'vue'
import { ElButton, ElSelect, ElOption, ElTabs, ElTabPane, ElEmpty, ElSkeleton } from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import router from './router.js'

const app = createApp(App)
for (const [name, component] of Object.entries({ ElButton, ElSelect, ElOption, ElTabs, ElTabPane, ElEmpty, ElSkeleton })) {
  app.component(name, component)
}
app.use(router).mount('#app')
