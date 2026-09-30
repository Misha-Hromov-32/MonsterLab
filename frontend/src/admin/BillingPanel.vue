<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, Loader2, Plus, Trash2 } from 'lucide-vue-next'
import { adminApi } from './adminApi'
import { FEATURE_TITLES } from '../lib/constants'
import type { AdminSettings, Feature, FeatureLimits, PlanInfo } from '../lib/types'

const props = defineProps<{ data: AdminSettings }>()
const emit = defineEmits<{ notify: [msg: string]; changed: [] }>()

// Границы — как на сервере (backend/app/api/admin.py: BillingSettings, PlanSettings, FeatureLimits).
const MAX_PRICE = 1_000_000
const MAX_DAYS = 366
const MAX_LIMIT = 100_000
const MAX_PLANS = 4
const ID_RE = /^[a-z0-9_-]{1,40}$/

const FEATURES = Object.keys(FEATURE_TITLES) as Feature[]
const saved = computed(() => props.data.billing)
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x))

const demo = ref<FeatureLimits>(clone(saved.value.demo))
const plans = ref<PlanInfo[]>(clone(saved.value.plans))
const busy = ref(false)
const error = ref('')

const body = computed(() => ({ demo: demo.value, plans: plans.value }))
const dirty = computed(
  () => JSON.stringify(body.value) !== JSON.stringify({ demo: saved.value.demo, plans: saved.value.plans }),
)

const inRange = (n: number, min: number, max: number) => Number.isInteger(n) && n >= min && n <= max
const quotasOk = (l: FeatureLimits) => FEATURES.every((f) => inRange(l[f], 0, MAX_LIMIT))
const valid = computed(
  () =>
    quotasOk(demo.value) &&
    plans.value.length > 0 &&
    new Set(plans.value.map((p) => p.id)).size === plans.value.length &&
    plans.value.every(
      (p) =>
        ID_RE.test(p.id) &&
        p.title.trim().length > 0 &&
        inRange(p.price_rub, 1, MAX_PRICE) &&
        inRange(p.period_days, 1, MAX_DAYS) &&
        quotasOk(p.limits),
    ),
)

function addPlan() {
  const last = plans.value[plans.value.length - 1]
  let n = plans.value.length + 1
  while (plans.value.some((p) => p.id === `plan-${n}`)) n++
  plans.value.push({
    id: `plan-${n}`,
    title: 'Новый тариф',
    price_rub: last ? last.price_rub * 2 : 990,
    period_days: 30,
    note: '',
    featured: false,
    limits: last ? { ...last.limits } : { ...demo.value },
  })
}

function removePlan(i: number) {
  plans.value.splice(i, 1)
}

// у существующих тарифов id не меняем: по нему привязаны оплаченные подписки
const savedIds = computed(() => new Set(saved.value.plans.map((p) => p.id)))

async function save() {
  busy.value = true
  error.value = ''
  try {
    await adminApi.saveBilling(body.value)
    emit('changed')
    emit('notify', 'Тарифы сохранены')
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
        <h1>Тарифы</h1>
        <p>Демо-доступ после подтверждения почты и платные тарифы: цена, срок и квоты на период оплаты.</p>
      </div>
      <span class="status" :class="{ on: saved.enabled }">
        <i class="dot" :class="{ good: saved.enabled }" />
        {{ saved.enabled ? 'Оплата подключена' : 'Оплата не подключена' }}
      </span>
    </header>
    <p class="note">
      Ключи ЮKassa задаются в переменных окружения <code>YOOKASSA_SHOP_ID</code> и <code>YOOKASSA_SECRET_KEY</code>.
      <template v-if="!saved.enabled">Пока их нет, кнопки оплаты на сайте скрыты, а демо-квоты уже действуют.</template>
    </p>
    <p v-if="error" class="err">{{ error }}</p>

    <section class="card block">
      <div class="bh">
        <h2 class="label">Платные тарифы</h2>
        <button class="btn sm pill" :disabled="plans.length >= MAX_PLANS" @click="addPlan">
          <Plus :size="14" /> Добавить
        </button>
      </div>
      <div v-for="(p, i) in plans" :key="i" class="plan">
        <label class="field">
          <span class="flabel">Название</span>
          <input v-model.trim="p.title" class="input" maxlength="40" />
        </label>
        <label class="field">
          <span class="flabel">id</span>
          <input
            v-model.trim="p.id"
            class="input num"
            maxlength="40"
            :readonly="savedIds.has(p.id)"
            :title="savedIds.has(p.id) ? 'По id привязаны оплаченные подписки — не меняется' : 'латиница, цифры, - и _'"
          />
        </label>
        <label class="field">
          <span class="flabel">Цена, ₽</span>
          <input v-model.number="p.price_rub" class="input num" type="number" min="1" :max="MAX_PRICE" step="1" />
        </label>
        <label class="field">
          <span class="flabel">Срок, дней</span>
          <input v-model.number="p.period_days" class="input num" type="number" min="1" :max="MAX_DAYS" step="1" />
        </label>
        <label class="field note-field">
          <span class="flabel">Подпись</span>
          <input v-model.trim="p.note" class="input" maxlength="80" placeholder="Для кого тариф" />
        </label>
        <label class="check"><input v-model="p.featured" type="checkbox" /> Выделить</label>
        <button
          class="btn ghost sm icon"
          :disabled="plans.length <= 1"
          :aria-label="`Удалить тариф «${p.title}»`"
          title="Удалить тариф"
          @click="removePlan(i)"
        >
          <Trash2 :size="15" />
        </button>
      </div>
    </section>

    <section class="card block">
      <h2 class="label">Квоты</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th />
              <th class="label">Демо</th>
              <th v-for="(p, i) in plans" :key="i" class="label">{{ p.title }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in FEATURES" :key="f">
              <th scope="row">{{ FEATURE_TITLES[f] }}</th>
              <td>
                <input
                  v-model.number="demo[f]"
                  class="input num"
                  type="number"
                  min="0"
                  :max="MAX_LIMIT"
                  step="1"
                  :aria-label="`${FEATURE_TITLES[f]}, демо`"
                />
              </td>
              <td v-for="(p, i) in plans" :key="i">
                <input
                  v-model.number="p.limits[f]"
                  class="input num"
                  type="number"
                  min="0"
                  :max="MAX_LIMIT"
                  step="1"
                  :aria-label="`${FEATURE_TITLES[f]}, тариф ${p.title}`"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="note">
        Демо — на всё время, тарифы — на период оплаты. 0 — функция недоступна. Анализ, полка и подбор конкурентов почти
        ничего не стоят; разбор, выбор покупателя и улучшенная обложка — это запросы к нейросетям (≈8, ≈3–15 и ≈14 ₽).
      </p>
    </section>

    <div class="actions">
      <button class="btn primary" :disabled="!dirty || !valid || busy" @click="save">
        <Loader2 v-if="busy" :size="15" class="spin" /><Check v-else :size="15" /> Сохранить
      </button>
      <span v-if="!valid" class="dirty"
        >Проверьте: у тарифов разные id и названия, цена от 1 ₽, срок 1–{{ MAX_DAYS }} дней, квоты 0–{{
          MAX_LIMIT.toLocaleString('ru-RU')
        }}</span
      >
      <span v-else-if="dirty" class="dirty">Есть несохранённые изменения</span>
    </div>
  </div>
</template>

<style scoped>
@import './panel.css';

.panel {
  max-width: 920px;
}

.status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 30px;
  padding: 0 12px;
  border-radius: 99px;
  border: 1px solid var(--line);
  font-size: 13px;
  color: var(--ink-2);
}

.status.on {
  color: var(--good);
  border-color: color-mix(in srgb, var(--good) 40%, transparent);
  background: var(--good-soft);
}

.block {
  display: grid;
  gap: 12px;
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

.plan {
  display: grid;
  grid-template-columns: 1.2fr 0.9fr 0.8fr 0.7fr 1.6fr auto auto;
  gap: 10px;
  align-items: end;
  padding-top: 12px;
  border-top: 1px solid var(--line);
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

code {
  font-size: 11.5px;
  color: var(--ink-2);
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
  padding: 6px 8px;
  text-align: left;
}

th:first-child {
  padding-left: 0;
}

tbody th {
  font-size: 13.5px;
  font-weight: 500;
  white-space: nowrap;
}

td .input {
  width: 100%;
  min-width: 80px;
}

@media (max-width: 760px) {
  .plan {
    grid-template-columns: 1fr 1fr;
  }
  .note-field {
    grid-column: 1 / -1;
  }
}
</style>
