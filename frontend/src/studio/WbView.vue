<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { request, jsonBody, withAuth } from '../api'
import type { Finding } from './types'

type Run = { id: number; created: number; status: string }
type Report = Run & {
  message: string
  total: number
  checked: number
  flagged: number
  manual: number
  average_score: number | null
  items: { nm: number; sku: string; title: string; score: number | null; findings: Finding[]; image_status: string }[]
}
const runs = ref<Run[]>([]),
  report = ref<Report>(),
  token = ref(''),
  selected = ref(0),
  offset = ref(0),
  error = ref(''),
  busy = ref(false)
const labels: Record<string, string> = {
  import: 'Получаем карточки',
  photos: 'Проверяем обложки',
  done: 'Готово',
  error: 'Неполный отчёт',
  cancelled: 'Остановлено',
}
const running = computed(() => ['import', 'photos'].includes(report.value?.status || ''))
const active = computed(() => runs.value.some((r) => ['import', 'photos'].includes(r.status)))
let timer: ReturnType<typeof setTimeout>,
  disposed = false,
  version = 0
async function refresh() {
  clearTimeout(timer)
  const id = selected.value,
    gen = ++version
  if (!id) return
  try {
    const next = await request<Report>('/api/wb/audits/' + id + '?offset=' + offset.value, withAuth())
    if (gen !== version || disposed) return
    report.value = next
    const entry = runs.value.find((r) => r.id === id)
    if (entry) entry.status = next.status
    error.value = ''
  } catch (e) {
    if (gen === version) error.value = (e as Error).message
  }
  if (!disposed && gen === version && (running.value || error.value)) timer = setTimeout(refresh, 4000)
}
function choose(id: number) {
  selected.value = id
  offset.value = 0
  report.value = undefined
  void refresh()
}
async function list(id?: number) {
  runs.value = await request<Run[]>('/api/wb/audits', withAuth())
  choose(id || runs.value[0]?.id || 0)
}
async function start() {
  error.value = ''
  busy.value = true
  try {
    const { id } = await request<{ id: number }>(
      '/api/wb/audits',
      withAuth(jsonBody('POST', { token: token.value.trim() })),
    )
    token.value = ''
    await list(id)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
async function cancel() {
  busy.value = true
  try {
    await request('/api/wb/audits/' + selected.value + '/cancel', withAuth({ method: 'POST' }))
    await refresh()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
async function download() {
  busy.value = true
  try {
    const r = await fetch('/api/wb/audits/' + selected.value + '/export', withAuth())
    if (!r.ok) throw new Error('Не удалось скачать отчёт')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(await r.blob())
    a.download = 'wb-audit-' + selected.value + '.csv'
    a.click()
    setTimeout(() => URL.revokeObjectURL(a.href), 30000)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
function page(step: number) {
  offset.value += step
  void refresh()
}
onMounted(async () => {
  try {
    await list()
  } catch (e) {
    error.value = (e as Error).message
  }
})
onUnmounted(() => {
  disposed = true
  clearTimeout(timer)
})
</script>
<template>
  <section>
    <h1>Аудит каталога Wildberries</h1>
    <p>
      Проверим названия, описания, наличие фотографий а также надписи и заметность главной обложки каждого действующего
      артикула.
    </p>
    <p>Готовый отчёт по всему каталогу — 20 импульсов.</p>
    <form @submit.prevent="start">
      <label class="field"
        >Токен WB API<input
          v-model.trim="token"
          type="password"
          class="input ym-hide-content"
          autocomplete="off"
          maxlength="8192"
          required
      /></label>
      <small
        >В кабинете WB выпустите базовый токен или сервисный для MonStoreLab. Выберите «Контент» и доступ только на
        чтение. Токен удаляется после получения списка карточек.</small
      >
      <button :disabled="busy || active || !token" class="btn primary">Проверить весь каталог</button>
    </form>
    <p v-if="error" class="err" role="alert">{{ error }}</p>
    <label v-if="runs.length" class="field"
      >Отчёты<select
        :value="selected"
        @change="choose(Number(($event.target as HTMLSelectElement).value))"
        class="input"
      >
        <option v-for="r in runs" :key="r.id" :value="r.id">
          № {{ r.id }} · {{ new Date(r.created * 1000).toLocaleString('ru-RU') }} · {{ labels[r.status] }}
        </option>
      </select></label
    >
    <div v-if="report" class="result">
      <h2>{{ labels[report.status] }}</h2>
      <p role="status">{{ report.message }}</p>
      <div class="totals">
        <span
          >Артикулов <b>{{ report.total }}</b></span
        ><span
          >Обработано <b>{{ report.checked }}</b></span
        ><span v-if="report.average_score != null"
          >Средняя заметность <b>{{ report.average_score }}/100</b></span
        ><span
          >С замечаниями <b>{{ report.flagged }}</b></span
        ><span
          >Фото для ручной проверки <b>{{ report.manual }}</b></span
        >
      </div>
      <button v-if="running" class="btn pill" :disabled="busy" @click="cancel">Остановить проверку</button
      ><button v-else class="btn pill" :disabled="busy" @click="download">Скачать отчёт CSV</button>
      <article v-for="card in report.items" :key="card.nm">
        <strong>{{ card.title || 'Без названия' }}</strong
        ><small
          >WB {{ card.nm }} · {{ card.sku }}
          <span v-if="card.score != null">· Заметность {{ card.score }}/100</span></small
        >
        <p>{{ card.image_status || 'Обложка ожидает проверки' }}</p>
        <ul v-if="card.findings.length">
          <li v-for="f in card.findings" :key="f.field + f.reason">
            {{ f.field }} · {{ f.reason }} <span v-if="f.match">«{{ f.match }}»</span>. {{ f.action }}
          </li>
        </ul>
        <small v-else>Замечаний к проверенным полям пока нет.</small>
      </article>
      <div v-if="report.total > 40" class="pager">
        <button class="btn pill" :disabled="offset === 0" @click="page(-40)">Назад</button
        ><span>{{ offset + 1 }}–{{ Math.min(offset + 40, report.total) }} из {{ report.total }}</span
        ><button class="btn pill" :disabled="offset + 40 >= report.total" @click="page(40)">Дальше</button>
      </div>
    </div>
  </section>
</template>
