<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Check, Loader2, Pencil, Plus, Shuffle, Trash2, X } from 'lucide-vue-next'
import { adminApi } from './adminApi'
import { FEATURE_TITLES } from '../lib/constants'
import { formatDate, promoSummary } from '../lib/format'
import type { AdminSettings, Feature, PromoCode, PromoInput } from '../lib/types'

const props = defineProps<{ data: AdminSettings }>()
const emit = defineEmits<{ notify: [msg: string] }>()

// Границы — как на сервере (backend/app/services/promo.py, api/admin.py: PromoIn).
const MAX_DELTA = 10_000
const MAX_DAYS = 366
const CODE_RE = /^[A-Z0-9А-ЯЁ_-]{3,32}$/

const FEATURES = Object.keys(FEATURE_TITLES) as Feature[]
const plans = computed(() => props.data.billing.plans)
const planTitle = (id: string) => plans.value.find((p) => p.id === id)?.title ?? id

const items = ref<PromoCode[]>([])
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const editing = ref<number | null>(null) // id редактируемого; null — создаём новый

type Form = {
  code: string
  note: string
  bonus: Record<Feature, number>
  plan_id: string
  plan_days: number
  max_uses: number
  expires: string // YYYY-MM-DD из <input type="date">
  active: boolean
}

const empty = (): Form => ({
  code: '',
  note: '',
  bonus: Object.fromEntries(FEATURES.map((f) => [f, 0])) as Record<Feature, number>,
  plan_id: '',
  plan_days: 0,
  max_uses: 0,
  expires: '',
  active: true,
})
const form = ref<Form>(empty())

const code = computed(() => form.value.code.trim().toUpperCase())
const hasBonus = computed(() => FEATURES.some((f) => form.value.bonus[f]))
const valid = computed(
  () =>
    CODE_RE.test(code.value) &&
    FEATURES.every((f) => Number.isInteger(form.value.bonus[f]) && Math.abs(form.value.bonus[f]) <= MAX_DELTA) &&
    (form.value.plan_id ? form.value.plan_days >= 1 && form.value.plan_days <= MAX_DAYS : true) &&
    Number.isInteger(form.value.max_uses) &&
    form.value.max_uses >= 0 &&
    (hasBonus.value || !!form.value.plan_id),
)

function body(): PromoInput {
  const f = form.value
  const bonus = Object.fromEntries(FEATURES.filter((k) => f.bonus[k]).map((k) => [k, f.bonus[k]]))
  return {
    code: code.value,
    note: f.note.trim(),
    bonus,
    plan_id: f.plan_id || null,
    plan_days: f.plan_id ? f.plan_days : 0,
    max_uses: f.max_uses,
    // действует до конца выбранного дня по местному времени
    expires_at: f.expires ? new Date(`${f.expires}T23:59:59`).getTime() / 1000 : null,
    active: f.active,
  }
}

function generate() {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789' // без похожих 0/O и 1/I
  const bytes = crypto.getRandomValues(new Uint8Array(8))
  form.value.code = Array.from(bytes, (b) => alphabet[b % alphabet.length]).join('')
}

function edit(p: PromoCode) {
  editing.value = p.id
  error.value = ''
  const d = p.expires_at ? new Date(p.expires_at * 1000) : null
  form.value = {
    code: p.code,
    note: p.note,
    bonus: { ...empty().bonus, ...p.bonus } as Record<Feature, number>,
    plan_id: p.plan_id ?? '',
    plan_days: p.plan_days || 0,
    max_uses: p.max_uses,
    expires: d
      ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      : '',
    active: p.active,
  }
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function reset() {
  editing.value = null
  form.value = empty()
  error.value = ''
}

async function run(action: () => Promise<{ items: PromoCode[] }>, done: string) {
  busy.value = true
  error.value = ''
  try {
    items.value = (await action()).items
    emit('notify', done)
    return true
  } catch (e) {
    error.value = (e as Error).message
    return false
  } finally {
    busy.value = false
  }
}

async function submit() {
  if (!valid.value || busy.value) return
  const id = editing.value
  const ok = await run(
    () => (id === null ? adminApi.createPromo(body()) : adminApi.savePromo(id, body())),
    id === null ? `Промокод ${code.value} создан` : `Промокод ${code.value} сохранён`,
  )
  if (ok) reset()
}

async function toggle(p: PromoCode) {
  const { id, created_at: _c, uses: _u, ...rest } = p
  await run(
    () => adminApi.savePromo(id, { ...rest, active: !p.active }),
    p.active ? 'Промокод выключен' : 'Промокод включён',
  )
}

async function remove(p: PromoCode) {
  if (!confirm(`Удалить промокод ${p.code}? Активации тоже удалятся.`)) return
  if (editing.value === p.id) reset()
  await run(() => adminApi.deletePromo(p.id), `Промокод ${p.code} удалён`)
}

function status(p: PromoCode) {
  if (!p.active) return { text: 'выключен', cls: '' }
  if (p.expires_at && p.expires_at * 1000 < Date.now()) return { text: 'истёк', cls: 'bad' }
  if (p.max_uses && p.uses >= p.max_uses) return { text: 'закончился', cls: 'bad' }
  return { text: 'действует', cls: 'good' }
}

onMounted(async () => {
  try {
    items.value = (await adminApi.promos()).items
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="panel">
    <header class="ph">
      <div>
        <h1>Промокоды</h1>
        <p>
          Промокод прибавляет или убавляет запуски функций (бонусные — сверх квоты тарифа) и может выдать тариф на N
          дней. Покупатель вводит его в аккаунте; один покупатель — один раз.
        </p>
      </div>
    </header>

    <form class="card block" @submit.prevent="submit">
      <div class="bh">
        <h2 class="label">{{ editing === null ? 'Новый промокод' : `Правка ${code}` }}</h2>
        <button v-if="editing !== null" type="button" class="btn ghost sm" @click="reset">
          <X :size="14" /> Отменить
        </button>
      </div>

      <div class="row top">
        <label class="field">
          <span class="flabel">Код</span>
          <div class="code-row">
            <input v-model="form.code" class="input num upper" maxlength="32" placeholder="SPRING25" />
            <button
              type="button"
              class="btn ghost sm icon"
              title="Сгенерировать"
              aria-label="Сгенерировать код"
              @click="generate"
            >
              <Shuffle :size="15" />
            </button>
          </div>
        </label>
        <label class="field grow">
          <span class="flabel">Заметка для себя</span>
          <input v-model="form.note" class="input" maxlength="200" placeholder="Для кого и зачем" />
        </label>
      </div>

      <div>
        <span class="flabel">Запуски: плюс — начислить, минус — списать (не ниже нуля)</span>
        <div class="features">
          <label
            v-for="f in FEATURES"
            :key="f"
            class="feat"
            :class="{ plus: form.bonus[f] > 0, minus: form.bonus[f] < 0 }"
          >
            <span>{{ FEATURE_TITLES[f] }}</span>
            <input
              v-model.number="form.bonus[f]"
              class="input num"
              type="number"
              :min="-MAX_DELTA"
              :max="MAX_DELTA"
              step="1"
            />
          </label>
        </div>
      </div>

      <div class="row">
        <label class="field">
          <span class="flabel">Тариф в подарок</span>
          <select v-model="form.plan_id" class="input">
            <option value="">— без тарифа —</option>
            <option v-for="p in plans" :key="p.id" :value="p.id">{{ p.title }}</option>
          </select>
        </label>
        <label class="field">
          <span class="flabel">Дней тарифа</span>
          <input
            v-model.number="form.plan_days"
            class="input num"
            type="number"
            min="1"
            :max="MAX_DAYS"
            :disabled="!form.plan_id"
          />
        </label>
        <label class="field">
          <span class="flabel">Активаций всего (0 — без лимита)</span>
          <input v-model.number="form.max_uses" class="input num" type="number" min="0" step="1" />
        </label>
        <label class="field">
          <span class="flabel">Действует до (включительно)</span>
          <input v-model="form.expires" class="input" type="date" />
        </label>
        <label class="check"><input v-model="form.active" type="checkbox" /> Включён</label>
      </div>
      <p class="note">
        Если у покупателя уже есть платный тариф, тариф из промокода его не заменяет, а продлевает на те же дни.
      </p>

      <p v-if="error" class="err">{{ error }}</p>
      <div class="actions">
        <button class="btn primary" type="submit" :disabled="!valid || busy">
          <Loader2 v-if="busy" :size="15" class="spin" /><Check v-else-if="editing !== null" :size="15" /><Plus
            v-else
            :size="15"
          />
          {{ editing === null ? 'Создать' : 'Сохранить' }}
        </button>
        <span v-if="!valid && (form.code || hasBonus || form.plan_id)" class="dirty"
          >Код — 3–32 символа (буквы, цифры, - и _); нужен хотя бы один запуск или тариф с числом дней</span
        >
      </div>
    </form>

    <section class="card block">
      <h2 class="label">Все промокоды</h2>
      <p v-if="loading" class="note">Загружаем…</p>
      <p v-else-if="!items.length" class="note">Промокодов пока нет.</p>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="label">Код</th>
              <th class="label">Что даёт</th>
              <th class="label">Активаций</th>
              <th class="label">До</th>
              <th class="label">Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in items" :key="p.id" :class="{ off: !p.active }">
              <td>
                <strong class="num">{{ p.code }}</strong>
                <span v-if="p.note" class="sub">{{ p.note }}</span>
              </td>
              <td class="gives">{{ promoSummary(p, planTitle).join(', ') }}</td>
              <td class="num">{{ p.uses }}{{ p.max_uses ? ` / ${p.max_uses}` : '' }}</td>
              <td class="num">{{ p.expires_at ? formatDate(p.expires_at) : '—' }}</td>
              <td>
                <span class="st" :class="status(p).cls">{{ status(p).text }}</span>
              </td>
              <td class="acts">
                <button class="btn ghost sm" :disabled="busy" @click="toggle(p)">
                  {{ p.active ? 'Выключить' : 'Включить' }}
                </button>
                <button class="btn ghost sm icon" title="Изменить" :aria-label="`Изменить ${p.code}`" @click="edit(p)">
                  <Pencil :size="14" />
                </button>
                <button
                  class="btn ghost sm icon"
                  title="Удалить"
                  :aria-label="`Удалить ${p.code}`"
                  :disabled="busy"
                  @click="remove(p)"
                >
                  <Trash2 :size="14" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
@import './panel.css';

.panel {
  max-width: 1040px;
}

.block {
  display: grid;
  gap: 16px;
  padding: 20px 22px;
}

.block h2 {
  margin: 0;
}

.bh {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.row {
  display: grid;
  grid-template-columns: 1fr 0.7fr 1fr 1fr auto;
  gap: 12px;
  align-items: end;
}

.row.top {
  grid-template-columns: minmax(220px, 0.8fr) 1.6fr;
}

.field {
  display: grid;
  gap: 6px;
}

.code-row {
  display: flex;
  gap: 6px;
}

.code-row .input {
  flex: 1;
  min-width: 0;
}

.upper {
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.features {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 8px;
}

.feat {
  display: grid;
  grid-template-columns: 1fr 96px;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  font-size: 13.5px;
}

.feat.plus {
  border-color: color-mix(in srgb, var(--good) 45%, transparent);
  background: var(--good-soft);
}

.feat.minus {
  border-color: color-mix(in srgb, var(--bad) 45%, transparent);
  background: var(--bad-soft);
}

.check {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  font-size: 13px;
  white-space: nowrap;
}

.note {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--ink-3);
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 10px 8px;
  text-align: left;
  vertical-align: top;
  border-top: 1px solid var(--line);
  font-size: 13.5px;
}

thead th {
  border-top: 0;
}

.sub {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--ink-3);
}

.gives {
  max-width: 340px;
  color: var(--ink-2);
}

.off td {
  opacity: 0.6;
}

.st {
  font-size: 12px;
  color: var(--ink-3);
}

.st.good {
  color: var(--good);
}

.st.bad {
  color: var(--bad);
}

.acts {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .row,
  .row.top {
    grid-template-columns: 1fr 1fr;
  }
  .features {
    grid-template-columns: 1fr;
  }
}
</style>
