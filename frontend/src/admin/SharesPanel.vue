<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { call } from './adminApi'
import { jsonBody } from '../api'
type Claim = { id: number; buyer: number; url: string; link: string }
const rows = ref<Claim[]>([]),
  error = ref(''),
  busy = ref(false)
async function load() {
  busy.value = true
  error.value = ''
  try {
    rows.value = await call('/api/admin/shares')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
async function review(id: number, status: string) {
  busy.value = true
  error.value = ''
  try {
    await call('/api/admin/shares/' + id, jsonBody('POST', { status }))
    await load()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
<template>
  <section>
    <h2>Бонусы за публикации</h2>
    <p>Откройте запись и сверьте персональную ссылку в тексте перед начислением.</p>
    <button class="btn" :disabled="busy" @click="load">Обновить</button>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="!busy && !error && !rows.length">Заявок на проверку пока нет.</p>
    <article v-for="r in rows" :key="r.id">
      <strong>Заявка №{{ r.id }}</strong
      ><a :href="r.url" target="_blank" rel="noopener noreferrer">Открыть публикацию ↗</a><code>{{ r.link }}</code>
      <div>
        <button class="btn primary" :disabled="busy" @click="review(r.id, 'approved')">Одобрить</button>
        <button class="btn" :disabled="busy" @click="review(r.id, 'declined')">Отклонить</button>
      </div>
    </article>
  </section>
</template>
<style scoped>
article {
  display: grid;
  gap: 12px;
  border-top: 1px solid var(--line);
  margin-top: 16px;
  padding: 18px 0;
}
code {
  overflow-wrap: anywhere;
}
</style>
