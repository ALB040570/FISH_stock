// Выбор вида внутри особых виджетов: вид из фильтра дашборда, иначе первый доступный.
import { computed, ref, watch } from 'vue'

export function useSpecies(props, listFn) {
  const list = computed(() => listFn() || [])
  const chosen = ref(null)
  const fromFilter = computed(() => props.filters?.species_ru)
  watch([list, fromFilter], () => {
    if (fromFilter.value && list.value.includes(fromFilter.value)) chosen.value = fromFilter.value
    else if (!list.value.includes(chosen.value)) chosen.value = list.value[0] || null
  }, { immediate: true })
  return { list, chosen }
}
