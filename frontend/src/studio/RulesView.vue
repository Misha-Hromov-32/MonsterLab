<script setup lang="ts">
import { ref } from 'vue'
import { request, withAuth } from '../api'
import type { Finding } from './types'
const market = ref('wb'),
  title = ref(''),
  description = ref(''),
  caption = ref(''),
  file = ref<File>(),
  busy = ref(false),
  error = ref('')
const result = ref<{ findings: Finding[]; image_status: string; source: string }>()
async function check() {
  busy.value = true
  error.value = ''
  result.value = undefined
  try {
    const form = new FormData()
    for (const [k, v] of Object.entries({
      market: market.value,
      title: title.value,
      description: description.value,
      caption: caption.value,
    }))
      form.set(k, v)
    if (file.value) form.set('cover', file.value)
    result.value = await request('/api/card-rules', withAuth({ method: 'POST', body: form }), { timeoutMs: 90000 })
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <section>
    <h1>Правила площадок</h1>
    <p>
      Проверьте формулировки и текст на обложке перед загрузкой. Замечания помогают найти фрагменты для сверки с
      правилами выбранной категории.
    </p>
    <p>Одна проверка — 2 импульса.</p>
    <form @submit.prevent="check" @input="result = undefined">
      <label class="field"
        >Площадка<select v-model="market" class="input">
          <option value="wb">Wildberries</option>
          <option value="ozon">Ozon</option>
        </select></label
      >
      <label class="field">Название товара<input v-model="title" maxlength="500" class="input" /></label>
      <label class="field"
        >Описание<textarea v-model="description" rows="4" maxlength="18000" class="input"></textarea>
      </label>
      <label class="field"
        >Обложка для распознавания текста<input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          @change="file = ($event.target as HTMLInputElement).files?.[0]"
      /></label>
      <label class="field">Надписи с обложки вручную<input v-model="caption" class="input" maxlength="5000" /></label>
      <button class="btn primary" :disabled="busy || !(title.trim() || description.trim() || caption.trim() || file)">
        {{ busy ? 'Проверяем…' : 'Проверить карточку' }}
      </button>
    </form>
    <p class="err" role="alert" v-if="error">{{ error }}</p>
    <div v-if="result" class="result" aria-live="polite">
      <h2>Результат проверки</h2>
      <p>{{ result.image_status }}</p>
      <p v-if="!result.findings.length">В проверенном тексте совпадений с правилами фильтра нет.</p>
      <article v-for="f in result.findings" :key="f.field + f.reason">
        <strong>{{ f.field }} · {{ f.reason }}</strong>
        <p>«{{ f.match }}» — {{ f.action }}</p>
        <small>{{ f.level === 'rule' ? 'Правило площадки' : 'Проверить контекст' }}</small>
      </article>
      <a :href="result.source" target="_blank" rel="noopener">Инструкция площадки</a>
    </div>
  </section>
</template>
