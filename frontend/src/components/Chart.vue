<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, VisualMapComponent, DataZoomComponent, AriaComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
echarts.use([LineChart, HeatmapChart, GridComponent, TooltipComponent, LegendComponent, VisualMapComponent, DataZoomComponent, AriaComponent, SVGRenderer])
const props = defineProps({ option: Object, label: String, height: { type: Number, default: 330 } })
const container = ref(null)
let chart, observer
onMounted(() => {
  chart = echarts.init(container.value, null, { renderer: 'svg' })
  chart.setOption({ ...props.option, aria: { enabled: true }, animation: false })
  observer = new ResizeObserver(() => chart.resize())
  observer.observe(container.value)
})
watch(() => props.option, option => chart?.setOption({ ...option, aria: { enabled: true }, animation: false }, true), { deep: true })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>
<template><div ref="container" class="chart" :style="{height: `${height}px`}" role="img" :aria-label="label" /></template>
