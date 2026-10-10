<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import { adminApi } from './adminApi'
import { FEATURE_TITLES } from '../lib/constants'
import { formatDate } from '../lib/format'
import type { AdminStats, Feature } from '../lib/types'

// Полная статистика сервиса: воронка, выручка, тарифы, запуски функций, платежи, покупатели.
const stats = ref<AdminStats | null>(null)
const busy = ref(false)
const error = ref('')
const query = ref('')

async function load() {
  busy.value = true
  error.value = ''
  try {
    stats.value = await adminApi.stats()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
onMounted(load)

const rub = (n: number) => `${Math.round(n).toLocaleString('ru-RU')} ₽`
const num = (n: number) => n.toLocaleString('ru-RU')
const pct = (a: number, b: number) => (b ? `${Math.round((a / b) * 100)}%` : '—')

const cards = computed(() => {
  const s = stats.value
  if (!s) return []
  const margin = s.revenue.last_30 - s.revenue.ai_cost_30
  return [
    { title: 'Выручка за 30 дней', value: rub(s.revenue.last_30), sub: `${s.revenue.payments_30} оплат` },
    { title: 'Траты на нейросети, 30 дней', value: `≈ ${rub(s.revenue.ai_cost_30)}`, sub: `разница ${rub(margin)}` },
    {
      title: 'Платящих сейчас',
      value: num(s.users.paying),
      sub: s.users.by_plan.map((p) => `${p.title}: ${p.count}`).join(' · ') || 'пока никого',
    },
    {
      title: 'Покупателей всего',
      value: num(s.users.total),
      sub: `+${s.users.new_7} за неделю · +${s.users.new_30} за месяц`,
    },
    { title: 'Выручка за всё время', value: rub(s.revenue.total), sub: `почту подтвердили ${num(s.users.verified)}` },
  ]
})

const funnel = computed(() => {
  const f = stats.value?.funnel_30
  if (!f) return []
  const steps = [
    { title: 'Открыли сайт', n: f.visits },
    { title: 'Зарегистрировались', n: f.registered },
    { title: 'Подтвердили почту', n: f.verified },
    { title: 'Пользовались', n: f.active },
    { title: 'Оплатили', n: f.paid },
  ]
  const top = Math.max(1, ...steps.map((s) => s.n))
  return steps.map((s, i) => ({
    ...s,
    width: `${Math.max(2, (s.n / top) * 100)}%`,
    conv: i ? pct(s.n, steps[i - 1].n) : '',
  }))
})

// четыре маленьких графика по дням: у каждого своя шкала — иначе визиты задавили бы оплаты
const SERIES = [
  { key: 'visits', title: 'Визиты' },
  { key: 'registered', title: 'Регистрации' },
  { key: 'runs', title: 'Запуски функций' },
  { key: 'revenue', title: 'Выручка, ₽' },
] as const
const charts = computed(() => {
  const daily = stats.value?.daily ?? []
  return SERIES.map((s) => {
    const values = daily.map((d) => d[s.key])
    const max = Math.max(1, ...values)
    return {
      ...s,
      total: values.reduce((a, b) => a + b, 0),
      max,
      bars: daily.map((d, i) => ({ day: d.day, v: values[i], h: (values[i] / max) * 100 })),
    }
  })
})
const firstDay = computed(() => stats.value?.daily[0]?.day.slice(5).split('-').reverse().join('.') ?? '')

const features = computed(() =>
  (stats.value?.features ?? []).map((f) => ({ ...f, title: FEATURE_TITLES[f.feature as Feature] ?? f.feature })),
)

const users = computed(() => {
  const q = query.value.trim().toLowerCase()
  const all = stats.value?.latest_users ?? []
  return q ? all.filter((u) => u.email.toLowerCase().includes(q) || u.plan.toLowerCase().includes(q)) : all
})

const STATUS: Record<string, string> = { succeeded: 'оплачен', pending: 'ожидает', canceled: 'отменён' }
</script>

<template>
  <div class="panel wide">
    <header class="ph">
      <div>
        <h1>Статистика</h1>
        <p>Воронка, выручка, тарифы и запуски функций за последние 30 дней. Траты на нейросети — оценка по замерам.</p>
      </div>
      <button class="btn pill" :disabled="busy" @click="load">
        <Loader2 v-if="busy" :size="15" class="spin" /><RefreshCw v-else :size="15" /> Обновить
      </button>
    </header>
    <p v-if="error" class="err">{{ error }}</p>
    <div v-if="!stats && busy" class="loading"><Loader2 :size="18" class="spin" /> Считаем…</div>

    <template v-if="stats">
      <section class="cards">
        <div v-for="c in cards" :key="c.title" class="kpi card">
          <span class="label">{{ c.title }}</span>
          <strong class="num">{{ c.value }}</strong>
          <span class="sub">{{ c.sub }}</span>
        </div>
      </section>

      <section class="card block">
        <h2 class="label">Воронка за 30 дней</h2>
        <div class="funnel">
          <div v-for="s in funnel" :key="s.title" class="step">
            <span class="st">{{ s.title }}</span>
            <div class="track"><i :style="{ width: s.width }" /></div>
            <span class="sn num">{{ num(s.n) }}</span>
            <span class="sc num">{{ s.conv }}</span>
          </div>
        </div>
        <p class="note">Справа — сколько процентов дошло с предыдущего шага.</p>
      </section>

      <section class="charts">
        <div v-for="ch in charts" :key="ch.key" class="card chart">
          <div class="ch-head">
            <span class="label">{{ ch.title }}</span>
            <span class="num total">{{ ch.key === 'revenue' ? rub(ch.total) : num(ch.total) }}</span>
          </div>
          <div class="bars" role="img" :aria-label="`${ch.title} по дням за 30 дней, всего ${ch.total}`">
            <i
              v-for="b in ch.bars"
              :key="b.day"
              :class="{ zero: !b.v }"
              :style="{ height: `${Math.max(b.h, 2)}%` }"
              :title="`${b.day}: ${ch.key === 'revenue' ? rub(b.v) : num(b.v)}`"
            />
          </div>
          <div class="axis num">
            <span>{{ firstDay }}</span
            ><span>сегодня</span>
          </div>
        </div>
      </section>

      <section class="card block">
        <h2 class="label">Запуски функций</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Функция</th>
                <th class="r">Сегодня</th>
                <th class="r">7 дней</th>
                <th class="r">30 дней</th>
                <th class="r">Всего</th>
                <th class="r">Траты за 30 дней</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="f in features" :key="f.feature">
                <th scope="row">{{ f.title }}</th>
                <td class="r num">{{ num(f.today) }}</td>
                <td class="r num">{{ num(f.week) }}</td>
                <td class="r num">{{ num(f.month) }}</td>
                <td class="r num">{{ num(f.total) }}</td>
                <td class="r num">{{ f.cost_30 ? `≈ ${rub(f.cost_30)}` : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card block">
        <h2 class="label">Последние платежи</h2>
        <p v-if="!stats.payments.length" class="note">Платежей пока не было.</p>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Дата</th>
                <th>Покупатель</th>
                <th>Тариф</th>
                <th class="r">Сумма</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(p, i) in stats.payments" :key="i">
                <td class="num">{{ formatDate(p.created_at) }}</td>
                <td class="mail">{{ p.email }}</td>
                <td>{{ p.plan }}</td>
                <td class="r num">{{ rub(p.amount) }}</td>
                <td>
                  <span class="pill-status" :class="p.status">{{ STATUS[p.status] ?? p.status }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card block">
        <div class="bh">
          <h2 class="label">Покупатели · последние {{ stats.latest_users.length }}</h2>
          <input
            v-model="query"
            class="input search"
            placeholder="Поиск по email или тарифу"
            aria-label="Поиск покупателей"
          />
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Email</th>
                <th>Регистрация</th>
                <th>Почта</th>
                <th>Тариф</th>
                <th>До</th>
                <th class="r">Запусков</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(u, i) in users" :key="i">
                <td class="mail">{{ u.email }}</td>
                <td class="num">{{ formatDate(u.created_at) }}</td>
                <td>{{ u.verified ? 'подтверждена' : 'нет' }}</td>
                <td>{{ u.plan }}</td>
                <td class="num">{{ u.pro_until ? formatDate(u.pro_until) : '—' }}</td>
                <td class="r num">{{ num(u.runs) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
@import './panel.css';
@import './report.css';

.panel.wide {
  max-width: 1100px;
}

.funnel {
  display: grid;
  gap: 8px;
}

.step {
  display: grid;
  grid-template-columns: 160px 1fr 70px 44px;
  gap: 12px;
  align-items: center;
  font-size: 13.5px;
}

.track {
  height: 22px;
  border-radius: 6px;
  background: var(--panel-2);
  overflow: hidden;
}

.track i {
  display: block;
  height: 100%;
  border-radius: 6px;
  background: var(--lime);
}

.sn {
  text-align: right;
  font-weight: 600;
}

.sc {
  font-size: 12px;
  color: var(--ink-3);
}

@media (max-width: 640px) {
  .step {
    grid-template-columns: 110px 1fr 54px;
  }
  .sc {
    display: none;
  }
}
</style>
