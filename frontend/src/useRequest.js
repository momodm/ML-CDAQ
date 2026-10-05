import { onUnmounted, ref } from 'vue'

export function useRequest() {
  const data = ref(null), loading = ref(false), error = ref(null)
  let ticket = 0
  function clear() {
    ticket += 1
    data.value = null; error.value = null; loading.value = false
  }
  async function run(task) {
    const current = ++ticket
    data.value = null; error.value = null; loading.value = true
    try {
      const result = await task()
      if (current === ticket) data.value = result
      return result
    } catch (failure) {
      if (current === ticket) error.value = failure
    } finally {
      if (current === ticket) loading.value = false
    }
  }
  onUnmounted(() => { ticket += 1 })
  return { data, loading, error, run, clear }
}
