<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ChevronDown, Download, Loader2, RefreshCw } from 'lucide-vue-next'
import { adminApi } from './adminApi'
import { FEATURE_TITLES } from '../lib/constants'
import type { AdminUser, AdminUsers, Feature } from '../lib/types'

// Все покупатели: как вошли, тариф и квоты, запуски, оплаты, промокоды. Строка раскрывается в подробности.
const PAGE = 200 // строк за раз: длинный список дорисовывается кнопкой «Показать ещё»
const data = ref<AdminUsers | null>(null)
const busy = ref(false)
const error = ref('')
const query = ref('')
const filter = ref<Filter>('all')
const sort = ref<Sort>('new')
const open = ref<number | null>(null)
const shown = ref(PAGE)

async function load() {
  busy.value = true
  error.value = ''
  try {
    data.value = await adminApi.users()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
onMounted(load)

const PROVIDERS: Record<string, string> = { vk: 'VK ID', yandex: 'Яндекс ID' }
const FEATURES = Object.keys(FEATURE_TITLES) as Feature[]

type Filter = 'all' | 'paying' | 'demo' | 'unverified' | 'vk' | 'yandex'
const FILTERS: { id: Filter; title: string; test: (u: AdminUser) => boolean }[] = [
  { id: 'all', title: 'Все', test: () => true },
  { id: 'paying', title: 'Платные', test: (u) => u.plan !== 'demo' },
  { id: 'demo', title: 'Демо', test: (u) => u.plan === 'demo' },
  { id: 'unverified', title: 'Почта не подтверждена', test: (u) => !u.verified },
  { id: 'vk', title: 'VK ID', test: (u) => u.providers.includes('vk') },
  { id: 'yandex', title: 'Яндекс ID', test: (u) => u.providers.includes('yandex') },
]

type Sort = 'new' | 'active' | 'runs' | 'paid'
const SORTS: Record<Sort, { title: string; key: (u: AdminUser) => number }> = {
  new: { title: 'Сначала новые', key: (u) => u.created_at },
  active: { title: 'Недавно активные', key: (u) => u.last_active ?? 0 },
  runs: { title: 'Больше запусков', key: (u) => u.runs_total },
  paid: { title: 'Больше оплат', key: (u) => u.paid_total },
}

const num = (n: number) => n.toLocaleString('ru-RU')
const rub = (n: number) => `${n.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽`
const date = (s: number) => new Date(s * 1000).toLocaleDateString('ru-RU')
const dateTime = (s: number) =>
  new Date(s * 1000).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

const cards = computed(() => {
  const s = data.value?.summary
  if (!s) return []
  return [
    { title: 'Всего', value: num(s.total), sub: `почту подтвердили ${num(s.verified)}` },
    { title: 'Платный тариф', value: num(s.paying), sub: `демо — ${num(s.total - s.paying)}` },
    { title: 'Активны за 30 дней', value: num(s.active_30), sub: 'запускали хоть одну функцию' },
    {
      title: 'Вход через сервисы',
      value: num(s.vk + s.yandex),
      sub: `VK ID ${num(s.vk)} · Яндекс ID ${num(s.yandex)}`,
    },
    { title: 'Без почты', value: num(s.no_email), sub: 'вошли через VK ID без адреса' },
  ]
})

const list = computed(() => {
  const q = query.value.trim().toLowerCase()
  const test = FILTERS.find((f) => f.id === filter.value)!.test
  const key = SORTS[sort.value].key
  return (data.value?.items ?? [])
    .filter(test)
    .filter(
      (u) =>
        !q ||
        u.email.toLowerCase().includes(q) ||
        String(u.id) === q.replace(/^#/, '') ||
        u.plan_title.toLowerCase().includes(q) ||
        u.promos.some((p) => p.code.toLowerCase().includes(q)),
    )
    .sort((a, b) => key(b) - key(a) || b.id - a.id)
})
const visible = computed(() => list.value.slice(0, shown.value))

function quota(u: AdminUser, f: Feature) {
  const bonus = u.bonus[f] ?? 0
  return `${num(u.usage[f])} / ${num(u.limits[f])}${bonus ? ` + ${num(bonus)} бонус` : ''}`
}

const STATUS: Record<string, string> = { succeeded: 'оплачен', pending: 'ожидает', canceled: 'отменён' }

// CSV для Excel: точка с запятой и BOM, иначе кириллица и столбцы разъедутся
function exportCsv() {
  const head = ['ID', 'Email', 'Вход', 'Регистрация', 'Почта подтверждена', 'Тариф', 'Тариф до', 'Запусков всего']
  head.push('Оплачено, ₽', 'Последняя активность', 'Промокоды', 'Обложек в библиотеке')
  const rows = list.value.map((u) => [
    u.id,
    u.email,
    u.providers.map((p) => PROVIDERS[p] ?? p).join(', ') || 'почта',
    date(u.created_at),
    u.verified ? 'да' : 'нет',
    u.plan_title,
    u.pro_until ? date(u.pro_until) : '',
    u.runs_total,
    u.paid_total,
    u.last_active ? dateTime(u.last_active) : '',
    u.promos.map((p) => p.code).join(', '),
    u.covers,
  ])
  const cell = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`
  const csv = [head, ...rows].map((r) => r.map(cell).join(';')).join('\r\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' }))
  a.download = `monstorelab-users-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}
</script>

<template>
  <div class="panel wide">
    <header class="ph">
      <div>
        <h1>Пользователи</h1>
        <p>
          Все покупатели: как вошли, тариф и остаток квот, запуски, оплаты и промокоды. Нажмите на строку — подробности.
        </p>
      </div>
      <div class="actions">
        <button class="btn ghost pill" :disabled="!list.length" @click="exportCsv"><Download :size="15" /> CSV</button>
        <button class="btn pill" :disabled="busy" @click="load">
          <Loader2 v-if="busy" :size="15" class="spin" /><RefreshCw v-else :size="15" /> Обновить
        </button>
      </div>
    </header>
    <p v-if="error" class="err">{{ error }}</p>
    <div v-if="!data && busy" class="loading"><Loader2 :size="18" class="spin" /> Загружаем…</div>

    <template v-if="data">
      <section class="cards">
        <div v-for="c in cards" :key="c.title" class="kpi card">
          <span class="label">{{ c.title }}</span>
          <strong class="num">{{ c.value }}</strong>
          <span class="sub">{{ c.sub }}</span>
        </div>
      </section>

      <section class="card block">
        <div class="bh">
          <div class="chips" role="group" aria-label="Фильтр">
            <button
              v-for="f in FILTERS"
              :key="f.id"
              class="chip"
              :class="{ on: filter === f.id }"
              :aria-pressed="filter === f.id"
              @click="((filter = f.id), (shown = PAGE))"
            >
              {{ f.title }}
            </button>
          </div>
          <div class="tools">
            <select v-model="sort" class="input sort" aria-label="Сортировка">
              <option v-for="(s, id) in SORTS" :key="id" :value="id">{{ s.title }}</option>
            </select>
            <input
              v-model="query"
              class="input search"
              placeholder="Email, #id, тариф или промокод"
              aria-label="Поиск покупателей"
              @input="shown = PAGE"
            />
          </div>
        </div>

        <p v-if="!list.length" class="note">Никого не нашли.</p>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Покупатель</th>
                <th>Регистрация</th>
                <th>Тариф</th>
                <th class="r">Запусков</th>
                <th class="r">Оплачено</th>
                <th>Был активен</th>
                <th aria-label="Подробности" />
              </tr>
            </thead>
            <tbody>
              <template v-for="u in visible" :key="u.id">
                <tr class="row" :class="{ open: open === u.id }" @click="open = open === u.id ? null : u.id">
                  <td class="num muted">#{{ u.id }}</td>
                  <td>
                    <span class="who">
                      <span class="mail">{{ u.email || 'без почты' }}</span>
                      <span v-for="p in u.providers" :key="p" class="tag" :class="p">{{ PROVIDERS[p] ?? p }}</span>
                      <span v-if="!u.verified" class="tag warn">не подтверждена</span>
                    </span>
                  </td>
                  <td class="num">{{ date(u.created_at) }}</td>
                  <td>
                    <span class="pill-status" :class="{ succeeded: u.plan !== 'demo' }">{{ u.plan_title }}</span>
                    <span v-if="u.pro_until" class="muted num"> до {{ date(u.pro_until) }}</span>
                  </td>
                  <td class="r num">{{ num(u.runs_total) }}</td>
                  <td class="r num">{{ u.paid_total ? rub(u.paid_total) : '—' }}</td>
                  <td class="num muted">{{ u.last_active ? dateTime(u.last_active) : '—' }}</td>
                  <td class="r">
                    <button
                      class="btn icon ghost sm"
                      :aria-expanded="open === u.id"
                      :aria-label="`Подробности о покупателе #${u.id}`"
                      @click.stop="open = open === u.id ? null : u.id"
                    >
                      <ChevronDown :size="15" class="chev" />
                    </button>
                  </td>
                </tr>
                <tr v-if="open === u.id" class="details">
                  <td colspan="8">
                    <div class="dgrid">
                      <div class="dcard">
                        <h3 class="label">Аккаунт</h3>
                        <dl>
                          <dt>Вход</dt>
                          <dd>{{ u.providers.map((p) => PROVIDERS[p] ?? p).join(', ') || 'почта и пароль' }}</dd>
                          <dt>Почта</dt>
                          <dd>{{ u.email ? (u.verified ? 'подтверждена' : 'не подтверждена') : 'нет' }}</dd>
                          <dt>Согласие</dt>
                          <dd class="num">
                            {{ u.consent_at ? dateTime(u.consent_at) : '—' }}
                            <span v-if="u.legal_version" class="muted">· редакция {{ u.legal_version }}</span>
                          </dd>
                          <template v-if="u.period_start">
                            <dt>Период тарифа</dt>
                            <dd class="num">{{ date(u.period_start) }} — {{ date(u.pro_until!) }}</dd>
                          </template>
                          <dt>Обложек в библиотеке</dt>
                          <dd class="num">{{ num(u.covers) }}</dd>
                          <dt>Запросов к нейросетям</dt>
                          <dd class="num">{{ num(u.ai_calls) }}</dd>
                        </dl>
                        <p v-if="u.contested" class="warn-note">
                          На эту почту до подтверждения регистрировались повторно — пароль мог задать не владелец.
                        </p>
                      </div>

                      <div class="dcard">
                        <h3 class="label">Квоты и запуски</h3>
                        <table class="mini">
                          <thead>
                            <tr>
                              <th>Функция</th>
                              <th class="r">В периоде</th>
                              <th class="r">Всего</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="f in FEATURES" :key="f">
                              <td>{{ FEATURE_TITLES[f] }}</td>
                              <td class="r num">{{ quota(u, f) }}</td>
                              <td class="r num">{{ num(u.runs[f] ?? 0) }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      <div class="dcard">
                        <h3 class="label">Платежи</h3>
                        <p v-if="!u.payments.length" class="note">Не платил.</p>
                        <table v-else class="mini">
                          <tbody>
                            <tr v-for="(p, i) in u.payments" :key="i">
                              <td class="num">{{ dateTime(p.created_at) }}</td>
                              <td>{{ p.plan }}</td>
                              <td class="r num">{{ rub(p.amount) }}</td>
                              <td>
                                <span class="pill-status" :class="p.status">{{ STATUS[p.status] ?? p.status }}</span>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                        <h3 class="label promo-h">Промокоды</h3>
                        <p v-if="!u.promos.length" class="note">Не активировал.</p>
                        <ul v-else class="promos">
                          <li v-for="p in u.promos" :key="p.code">
                            <code>{{ p.code }}</code> <span class="muted num">{{ dateTime(p.at) }}</span>
                          </li>
                        </ul>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <div v-if="list.length" class="foot">
          <span class="note num">Показано {{ num(visible.length) }} из {{ num(list.length) }}</span>
          <button v-if="visible.length < list.length" class="btn ghost sm" @click="shown += PAGE">Показать ещё</button>
        </div>
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

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: none;
  color: var(--ink-2);
  font: inherit;
  font-size: 12.5px;
  cursor: pointer;
}

.chip.on {
  border-color: var(--ink);
  background: var(--ink);
  color: var(--panel);
}

.tools {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.sort {
  width: auto;
  height: 34px;
}

.row {
  cursor: pointer;
}

.row:hover td,
.row.open td {
  background: var(--panel-2);
}

.who {
  display: flex;
  align-items: center;
  gap: 6px;
}

.muted {
  color: var(--ink-3);
}

.tag {
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--panel-2);
  font-size: 11px;
  color: var(--ink-2);
}

.tag.vk {
  background: color-mix(in srgb, #0077ff 14%, transparent);
  color: #0a5ed7;
}

.tag.yandex {
  background: color-mix(in srgb, #fc3f1d 14%, transparent);
  color: #c9341a;
}

.tag.warn {
  background: color-mix(in srgb, var(--warn) 14%, transparent);
  color: var(--warn);
}

.chev {
  transition: transform 0.15s;
}

.row.open .chev {
  transform: rotate(180deg);
}

.details td {
  padding: 4px 0 16px;
  white-space: normal;
}

.dgrid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
}

.dcard {
  display: grid;
  align-content: start;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
}

.dcard h3 {
  margin: 0;
}

dl {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 6px 14px;
  margin: 0;
  font-size: 13px;
}

dt {
  color: var(--ink-3);
}

dd {
  margin: 0;
}

.mini th,
.mini td {
  padding: 5px 6px;
  font-size: 12.5px;
}

.mini td:first-child {
  white-space: normal;
}

.promo-h {
  margin-top: 6px !important;
}

.promos {
  display: grid;
  gap: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 13px;
}

.warn-note {
  margin: 0;
  font-size: 12.5px;
  color: var(--warn);
}

.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
</style>
