<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, Loader2 } from 'lucide-vue-next'
import { adminApi } from './adminApi'
import { FEATURE_TITLES } from '../lib/constants'
import type { AdminSettings, Feature, FeatureLimits, Plan } from '../lib/types'

const props = defineProps<{ data: AdminSettings }>()
const emit = defineEmits<{ notify: [msg: string]; changed: [] }>()

// Границы — как на сервере (backend/app/api/admin.py: BillingSettings, FeatureLimits).
const MAX_PRICE = 1_000_000
const MAX_DAYS = 366
const MAX_LIMIT = 10_000

const FEATURES = Object.keys(FEATURE_TITLES) as Feature[]
const PLANS: { id: Plan; title: string }[] = [
  { id: 'free', title: 'Бесплатный' },
  { id: 'pro', title: 'Pro' },
]

const saved = computed(() => props.data.billing)
const copy = (l: FeatureLimits): FeatureLimits => ({ ...l })

const price = ref(saved.value.price_rub)
const days = ref(saved.value.period_days)
const limits = ref<Record<Plan, FeatureLimits>>({
  free: copy(saved.value.limits.free),
  pro: copy(saved.value.limits.pro),
})
const busy = ref(false)
const error = ref('')

const body = computed(() => ({ price_rub: price.value, period_days: days.value, limits: limits.value }))
const dirty = computed(
  () =>
    JSON.stringify(body.value) !==
    JSON.stringify({
      price_rub: saved.value.price_rub,
      period_days: saved.value.period_days,
      limits: saved.value.limits,
    }),
)

const inRange = (n: number, min: number, max: number) => Number.isInteger(n) && n >= min && n <= max
const valid = computed(
  () =>
    inRange(price.value, 1, MAX_PRICE) &&
    inRange(days.value, 1, MAX_DAYS) &&
    PLANS.every((p) => FEATURES.every((f) => inRange(limits.value[p.id][f], 0, MAX_LIMIT))),
)

async function save() {
  busy.value = true
  error.value = ''
  try {
    await adminApi.saveBilling(body.value)
    emit('changed')
    emit('notify', 'Условия подписки сохранены')
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
        <h1>Подписка</h1>
        <p>
          Цена и срок подписки Pro и сколько раз в день можно пользоваться платными функциями. Разбор обложек, тест
          полки и примеры бесплатны для всех.
        </p>
      </div>
      <span class="status" :class="{ on: saved.enabled }">
        <i class="dot" :class="{ good: saved.enabled }" />
        {{ saved.enabled ? 'Оплата подключена' : 'Оплата не подключена' }}
      </span>
    </header>
    <p class="note">
      Ключи ЮKassa задаются в переменных окружения <code>YOOKASSA_SHOP_ID</code> и <code>YOOKASSA_SECRET_KEY</code>.
      <template v-if="!saved.enabled"
        >Пока их нет, кнопка оплаты на сайте скрыта, а лимиты бесплатного тарифа уже действуют.</template
      >
    </p>
    <p v-if="error" class="err">{{ error }}</p>

    <section class="card block">
      <h2 class="label">Цена и срок</h2>
      <div class="grid2">
        <label class="field">
          <span class="flabel">Цена, ₽</span>
          <input v-model.number="price" class="input" type="number" min="1" :max="MAX_PRICE" step="1" />
        </label>
        <label class="field">
          <span class="flabel">Срок, дней</span>
          <input v-model.number="days" class="input" type="number" min="1" :max="MAX_DAYS" step="1" />
        </label>
      </div>
    </section>

    <section class="card block">
      <h2 class="label">Лимиты в день</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th />
              <th v-for="p in PLANS" :key="p.id" class="label">{{ p.title }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in FEATURES" :key="f">
              <th scope="row">{{ FEATURE_TITLES[f] }}</th>
              <td v-for="p in PLANS" :key="p.id">
                <input
                  v-model.number="limits[p.id][f]"
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
      <p class="note">0 — функция на этом тарифе недоступна.</p>
    </section>

    <div class="actions">
      <button class="btn primary" :disabled="!dirty || !valid || busy" @click="save">
        <Loader2 v-if="busy" :size="15" class="spin" /><Check v-else :size="15" /> Сохранить
      </button>
      <span v-if="!valid" class="dirty"
        >Проверьте числа: цена от 1 ₽, срок 1–{{ MAX_DAYS }} дней, лимиты 0–{{ MAX_LIMIT }}</span
      >
      <span v-else-if="dirty" class="dirty">Есть несохранённые изменения</span>
    </div>
  </div>
</template>

<style scoped>
@import './panel.css';

.panel {
  max-width: 820px;
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
  min-width: 90px;
}

@media (max-width: 560px) {
  .grid2 {
    grid-template-columns: 1fr;
  }
}
</style>
