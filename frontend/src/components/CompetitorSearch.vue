<script setup lang="ts">
import { computed, ref } from 'vue'
import { Loader2, Search } from 'lucide-vue-next'
import { searchCompetitors, state } from '../store'
import { MAX_COMPETITORS } from '../lib/constants'

// запрос из данных о товаре — продавец уже вводил его слева, повторять не нужно
const query = ref(state.context.query)
const loading = computed(() => state.competitorSearch.status === 'loading')
const full = computed(() => state.competitors.length >= MAX_COMPETITORS)
</script>

<template>
  <form class="search" role="search" @submit.prevent="searchCompetitors(query)">
    <div class="row">
      <input
        v-model="query"
        class="input"
        type="search"
        maxlength="120"
        placeholder="Поисковый запрос, например «термокружка 500 мл»"
        aria-label="Поисковый запрос покупателя на Wildberries"
        :disabled="loading"
      />
      <button class="btn" type="submit" :disabled="loading || full || query.trim().length < 2">
        <Loader2 v-if="loading" :size="14" class="spin" /><Search v-else :size="14" />
        {{ loading ? 'Ищем…' : 'Найти на Wildberries' }}
      </button>
    </div>
    <p v-if="state.competitorSearch.status === 'error'" class="err" role="alert">{{ state.competitorSearch.error }}</p>
    <p v-else class="hint">
      {{ loading ? 'Собираем обложки из выдачи — обычно 5–15 секунд' : 'Возьмём топ выдачи по запросу' }}
    </p>
  </form>
</template>

<style scoped>
.search {
  display: grid;
  gap: 6px;
}

.row {
  display: flex;
  gap: 8px;
}

.row .input {
  flex: 1;
  min-width: 0;
}

.hint {
  margin: 0;
  font-size: 10.5px;
  color: var(--ink-3);
}

.err {
  margin: 0;
  font-size: 12px;
  color: var(--bad);
}

@media (max-width: 520px) {
  .row {
    flex-direction: column;
  }
  .row .btn {
    justify-content: center;
  }
}
</style>
