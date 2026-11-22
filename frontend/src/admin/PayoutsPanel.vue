<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { call } from './adminApi'
import { jsonBody } from '../api'
type Payout = {
  id: number
  partner: number
  kopecks: number
  method: string
  provider_id: string | null
  details: string
  status: string
  reference: string
  at: number
}
const rows = ref<Payout[]>([]),
  references = ref<Record<number, string>>({}),
  error = ref(''),
  busy = ref(false)
const labels: Record<string, string> = {
  sending: 'Обрабатывается банком',
  pending: 'Ожидает перевода',
  paid: 'Выплачено',
  declined: 'Отклонено',
}
async function reload() {
  rows.value = await call<Payout[]>('/api/admin/payouts')
}
onMounted(async () => {
  try {
    await reload()
  } catch (e) {
    error.value = (e as Error).message
  }
})
async function transfer(r: Payout) {
  if (
    r.status === 'pending' &&
    !confirm('Перевести ' + (r.kopecks / 100).toLocaleString('ru-RU') + ' ₽ через СБП? Получатель: ' + r.details)
  )
    return
  busy.value = true
  error.value = ''
  try {
    await call(
      '/api/admin/payouts/' + r.id + '/transfer',
      jsonBody('POST', { provider_id: r.status === 'sending' ? references.value[r.id] || '' : '' }),
    )
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    try {
      await reload()
    } catch (e) {
      error.value = (e as Error).message
    }
    busy.value = false
  }
}
async function settle(id: number, status: string) {
  const reference = references.value[id]?.trim()
  if (!reference || reference.length < 2) {
    error.value = 'Введите номер перевода или причину отказа'
    return
  }
  busy.value = true
  error.value = ''
  try {
    await call('/api/admin/payouts/' + id, jsonBody('POST', { status, reference }))
    await reload()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="panel">
    <header class="ph">
      <div>
        <h1>Выплаты партнёрам</h1>
        <p>
          Для выплаты по СБП подтвердите перевод через ЮKassa. Для ручной выплаты внесите номер банковской операции. При
          отказе комиссия вернётся на баланс партнёра.
        </p>
      </div>
    </header>
    <p v-if="error" class="err" role="alert">{{ error }}</p>
    <p v-if="!rows.length">Заявок на выплату пока нет.</p>
    <section v-for="r in rows" :key="r.id" class="card">
      <h2>Заявка № {{ r.id }} · {{ (r.kopecks / 100).toLocaleString('ru-RU') }} ₽</h2>
      <p>
        Партнёр № {{ r.partner }} · {{ new Date(r.at * 1000).toLocaleDateString('ru-RU') }} · {{ labels[r.status] }}
      </p>
      <template v-if="r.status === 'pending'"
        ><p class="details">{{ r.details }}</p>
        <label class="field"
          >{{ r.method === 'sbp' ? 'Причина отказа (при отклонении)' : 'Номер перевода или причина отказа'
          }}<input class="input" v-model="references[r.id]" maxlength="200"
        /></label>
        <div class="actions">
          <button v-if="r.method === 'sbp'" class="btn primary" :disabled="busy" @click="transfer(r)">
            Перевести через СБП</button
          ><button v-else class="btn primary" :disabled="busy" @click="settle(r.id, 'paid')">Подтвердить перевод</button
          ><button class="btn pill" :disabled="busy" @click="settle(r.id, 'declined')">Отклонить</button>
        </div></template
      >
      <template v-else-if="r.status === 'sending'"
        ><label v-if="!r.provider_id" class="field"
          >ID выплаты для сверки, если известен<input
            class="input"
            v-model.trim="references[r.id]"
            maxlength="80" /></label
        ><button class="btn pill" :disabled="busy" @click="transfer(r)">Проверить статус в ЮKassa</button></template
      >
      <p v-else>{{ r.reference }}</p>
    </section>
  </div>
</template>
<style scoped>
@import './panel.css';
.card {
  padding: 18px;
  display: grid;
  gap: 10px;
}
.details {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
h2,
p {
  margin: 0;
}
</style>
