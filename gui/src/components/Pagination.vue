<template>
  <div v-if="totalPages > 1" class="pagination">
    <button class="page-btn" :disabled="page <= 1" @click="$emit('change', page - 1)">‹</button>
    <button
      v-for="p in pages"
      :key="p"
      class="page-btn"
      :class="{ active: p === page }"
      @click="$emit('change', p)"
    >{{ p }}</button>
    <button class="page-btn" :disabled="page >= totalPages" @click="$emit('change', page + 1)">›</button>
    <span class="page-info">共 {{ total }} 条</span>
  </div>
</template>

<script>
import { computed } from 'vue'

export default {
  name: 'Pagination',
  props: {
    page: { type: Number, required: true },
    total: { type: Number, required: true },
    pageSize: { type: Number, default: 20 },
  },
  emits: ['change'],
  setup(props) {
    const totalPages = computed(() => Math.ceil(props.total / props.pageSize) || 1)

    const pages = computed(() => {
      const tp = totalPages.value
      const cur = props.page
      if (tp <= 7) {
        return Array.from({ length: tp }, (_, i) => i + 1)
      }
      const res = []
      if (cur <= 4) {
        for (let i = 1; i <= 5; i++) res.push(i)
        res.push(-1, tp)
      } else if (cur >= tp - 3) {
        res.push(1, -1)
        for (let i = tp - 4; i <= tp; i++) res.push(i)
      } else {
        res.push(1, -1)
        for (let i = cur - 1; i <= cur + 1; i++) res.push(i)
        res.push(-1, tp)
      }
      return res
    })

    return { totalPages, pages }
  },
}
</script>

<style scoped>
/* Minimal - global pagination styles are in App.vue */
</style>
