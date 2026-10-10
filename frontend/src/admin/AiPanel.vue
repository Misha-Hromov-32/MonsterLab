<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-vue-next'
import { adminApi } from './adminApi'
import { FEATURE_TITLES } from '../lib/constants'
import type { AdminAi } from '../lib/types'

// Расходы ProxyAPI: остаток, списания и пополнения, на какие функции ушли деньги, журнал запросов к моделям.
// ProxyAPI не отдаёт историю списаний — сервер сам замеряет баланс и делит падение между запросами.
const data = ref<AdminAi | null>(null)
const busy = ref(false)
const error = ref('')

async function load() {
  busy.value = true
  error.value = ''
  try {
    data.value = await adminApi.ai()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
onMounted(load)

const TITLES: Record<string, string> = {
  ...FEATURE_TITLES,
  check: 'Проверка ключа в админке',
  background: 'Фоновые задачи',
  other: 'Прочее',
}
const title = (f: string) => TITLES[f] ?? f

const rub = (n: number) => `${n.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`
const num = (n: number) => n.toLocaleString('ru-RU')
const signed = (n: number) => `${n > 0 ? '+' : '−'}${rub(Math.abs(n))}`
const dateTime = (s: number) =>
  new Date(s * 1000).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
const date = (s: number) => new Date(s * 1000).toLocaleDateString('ru-RU')

const current = computed(() => data.value?.current)

// на сколько хватит остатка при среднем расходе последних 30 дней (или с начала учёта, если он короче)
const runway = computed(() => {
  const d = data.value
  if (!d || d.current.balance === undefined || !d.spent.month || !d.tracking_since) return ''
  const days = Math.min(30, Math.max(1, (d.generated_at - d.tracking_since) / 86400))
  const left = d.current.balance / (d.spent.month / days)
  return left > 365 ? 'хватит больше чем на год' : `хватит примерно на ${Math.round(left)} дн.`
})

const cards = computed(() => {
  const d = data.value
  if (!d) return []
  return [
    { title: 'Списано сегодня', value: rub(d.spent.today) },
    { title: 'За 7 дней', value: rub(d.spent.week) },
    { title: 'За 30 дней', value: rub(d.spent.month) },
    { title: 'Пополнения за 30 дней', value: rub(d.topups_30) },
  ]
})

const chart = computed(() => {
  const daily = data.value?.daily ?? []
  const max = Math.max(0.01, ...daily.map((d) => d.spent))
  return daily.map((d) => ({ ...d, h: (d.spent / max) * 100 }))
})
const firstDay = computed(() => data.value?.daily[0]?.day.slice(5).split('-').reverse().join('.') ?? '')

const features = computed(() => {
  const list = data.value?.features ?? []
  const total = list.reduce((a, f) => a + f.rub, 0)
  return list.map((f) => ({ ...f, share: total ? `${Math.round((f.rub / total) * 100)}%` : '—' }))
})

function breakdown(c: AdminAi['changes'][number]) {
  if (c.delta > 0) return 'Пополнение'
  const parts = c.by_feature
    .filter((f) => f.rub > 0 || f.calls)
    .map((f) => `${title(f.feature)} ×${f.calls}${f.rub ? ` ≈ ${rub(f.rub)}` : ''}`)
  return parts.join(' · ') || 'Запросов с сайта не было — ключ использовали в другом месте?'
}
</script>

<template>
  <div class="panel wide">
    <header class="ph">
      <div>
        <h1>Расходы ProxyAPI</h1>
        <p>
          Остаток на счёте, списания и пополнения, на какие функции ушли деньги. ProxyAPI не отдаёт историю списаний —
          сервер сам замеряет баланс после запросов и делит каждое списание между ними по оценке их цены.
        </p>
      </div>
      <button class="btn pill" :disabled="busy" @click="load">
        <Loader2 v-if="busy" :size="15" class="spin" /><RefreshCw v-else :size="15" /> Обновить
      </button>
    </header>
    <p v-if="error" class="err">{{ error }}</p>
    <div v-if="!data && busy" class="loading"><Loader2 :size="18" class="spin" /> Спрашиваем ProxyAPI…</div>

    <template v-if="data && current">
      <section class="top">
        <div class="card balance" :class="{ bad: current.error }">
          <span class="label">Остаток на счёте</span>
          <template v-if="current.balance !== undefined">
            <strong class="num">{{ rub(current.balance) }}</strong>
            <span class="sub">
              <template v-if="runway">{{ runway }} · </template>проверено {{ dateTime(current.checked_at) }}
            </span>
            <span v-if="current.budget?.limit" class="sub num">
              Бюджет ключа: потрачено {{ rub(current.budget.used ?? 0) }} из {{ rub(current.budget.limit) }}
            </span>
          </template>
          <template v-else>
            <strong class="warn-title"><AlertTriangle :size="18" /> Баланс недоступен</strong>
            <span class="sub">{{ current.error?.message }}</span>
            <ol v-if="current.error?.code === 'forbidden'" class="howto">
              <li>
                Откройте <a href="https://proxyapi.ru" target="_blank" rel="noopener">личный кабинет ProxyAPI</a> →
                «Ключи API».
              </li>
              <li>У ключа, который подключён к сайту, включите разрешение «Запрос баланса» и сохраните.</li>
              <li>Нажмите «Обновить» здесь. Журнал запросов ниже ведётся и без этого.</li>
            </ol>
          </template>
        </div>
        <div class="cards">
          <div v-for="c in cards" :key="c.title" class="kpi card">
            <span class="label">{{ c.title }}</span>
            <strong class="num">{{ c.value }}</strong>
          </div>
        </div>
      </section>

      <section class="card chart">
        <div class="ch-head">
          <span class="label">Списания по дням, 30 дней</span>
          <span class="num total">{{ rub(data.spent.month) }}</span>
        </div>
        <div class="bars tall" role="img" :aria-label="`Списания по дням за 30 дней, всего ${rub(data.spent.month)}`">
          <i
            v-for="b in chart"
            :key="b.day"
            :class="{ zero: !b.spent }"
            :style="{ height: `${Math.max(b.h, 2)}%` }"
            :title="`${b.day}: ${rub(b.spent)}, запросов ${b.calls}`"
          />
        </div>
        <div class="axis num">
          <span>{{ firstDay }}</span
          ><span>сегодня</span>
        </div>
        <p v-if="data.tracking_since" class="note">Учёт баланса — с {{ date(data.tracking_since) }}.</p>
      </section>

      <div class="two">
        <section class="card block">
          <h2 class="label">На что ушли деньги · 30 дней</h2>
          <p v-if="!features.length" class="note">Запросов к нейросетям не было.</p>
          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Функция</th>
                  <th class="r">Запросов</th>
                  <th class="r">Токенов</th>
                  <th class="r">≈ ₽</th>
                  <th class="r">Доля</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="f in features" :key="f.feature">
                  <th scope="row">
                    {{ title(f.feature) }}
                    <span v-if="f.failed" class="muted">· ошибок {{ f.failed }}</span>
                  </th>
                  <td class="r num">{{ num(f.calls) }}</td>
                  <td class="r num">{{ num(f.tokens) }}</td>
                  <td class="r num">{{ rub(f.rub) }}</td>
                  <td class="r num">{{ f.share }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="card block">
          <h2 class="label">Модели · 30 дней</h2>
          <p v-if="!data.models.length" class="note">Пока пусто.</p>
          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Модель</th>
                  <th class="r">Запросов</th>
                  <th class="r">Токенов</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="m in data.models" :key="m.model">
                  <th scope="row" class="mono">{{ m.model }}</th>
                  <td class="r num">{{ num(m.calls) }}</td>
                  <td class="r num">{{ num(m.tokens) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section class="card block">
        <h2 class="label">Списания и пополнения</h2>
        <p v-if="!data.changes.length" class="note">
          Изменений баланса пока не было. Первое появится после очередного запроса к нейросети.
        </p>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Когда</th>
                <th class="r">Сумма</th>
                <th class="r">Остаток</th>
                <th>На что</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in data.changes" :key="c.ts">
                <td class="num">{{ dateTime(c.ts) }}</td>
                <td class="r num" :class="c.delta > 0 ? 'plus' : 'minus'">{{ signed(c.delta) }}</td>
                <td class="r num">{{ rub(c.balance) }}</td>
                <td class="wrap">{{ breakdown(c) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card block">
        <h2 class="label">Журнал запросов · последние {{ data.calls.length }}</h2>
        <p v-if="!data.calls.length" class="note">Запросов к нейросетям ещё не было.</p>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Когда</th>
                <th>Покупатель</th>
                <th>Функция</th>
                <th>Модель</th>
                <th class="r">Токены: вход / ответ</th>
                <th class="r">≈ ₽</th>
                <th>Итог</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(c, i) in data.calls" :key="i">
                <td class="num">{{ dateTime(c.ts) }}</td>
                <td class="mail">{{ c.email || '—' }}</td>
                <td>{{ title(c.feature) }}</td>
                <td class="mono">{{ c.model }}</td>
                <td class="r num">{{ num(c.prompt_tokens) }} / {{ num(c.completion_tokens) }}</td>
                <td class="r num">{{ c.rub === null ? '—' : rub(c.rub) }}</td>
                <td>
                  <span class="pill-status" :class="{ succeeded: c.ok }">{{ c.ok ? 'ок' : 'ошибка' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="note">
          «—» в рублях — баланс после запроса ещё не замерен (раз в минуту) или запрос завершился ошибкой.
        </p>
      </section>
    </template>
  </div>
</template>

<style scoped>
@import './panel.css';
@import './report.css';

.panel.wide {
  max-width: 1180px;
}

.top {
  display: grid;
  grid-template-columns: minmax(280px, 1.1fr) 2fr;
  gap: 12px;
}

.balance {
  display: grid;
  align-content: start;
  gap: 8px;
  padding: 20px 22px;
}

.balance strong.num {
  font-size: 40px;
  font-weight: 300;
  letter-spacing: -0.04em;
}

.balance.bad {
  border-color: color-mix(in srgb, var(--warn) 50%, var(--line));
}

.warn-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 500;
  color: var(--warn);
}

.howto {
  display: grid;
  gap: 4px;
  margin: 4px 0 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--ink-2);
}

.top .cards {
  grid-template-columns: repeat(2, 1fr);
}

.bars.tall {
  height: 120px;
}

.two {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 12px;
}

.muted {
  color: var(--ink-3);
  font-weight: 400;
}

.mono {
  font-family: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
  font-size: 12px;
  font-weight: 400;
}

.plus {
  color: var(--good);
}

.minus {
  color: var(--bad);
}

td.wrap {
  min-width: 260px;
  white-space: normal;
  color: var(--ink-2);
}

@media (max-width: 860px) {
  .top,
  .two {
    grid-template-columns: 1fr;
  }
}
</style>
