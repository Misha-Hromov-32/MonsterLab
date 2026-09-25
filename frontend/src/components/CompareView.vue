<script setup lang="ts">
import { computed, ref } from 'vue'
import { Loader2, Scale } from 'lucide-vue-next'
import HeatImage from './HeatImage.vue'
import KeyBadge from './KeyBadge.vue'
import Segmented from './Segmented.vue'
import { expertEnabled, ready, runCompare, state } from '../store'
import { aoiStat } from '../lib/heat'
import { baseName, pct, plural, silentExperts } from '../lib/format'
import { OVERLAY_MODES } from '../lib/overlay'
import type { Analysis, Variant } from '../lib/types'

type Analyzed = Variant & { analysis: Analysis }

// ready уже отфильтрован по analysis; сужаем тип, чтобы ниже не писать проверки
const variants = computed(() => ready.value.filter((v): v is Analyzed => !!v.analysis))

type Row = {
  title: string
  hint?: string
  get: (v: Analyzed) => number | null
  fmt: (n: number) => string
  better: 'high' | 'low'
}

const BASE_ROWS: Row[] = [
  { title: 'Индекс заметности', get: (v) => v.analysis.index, fmt: String, better: 'high' },
  { title: 'Фокус', get: (v) => v.analysis.scores.focus, fmt: String, better: 'high' },
  { title: 'Лёгкость восприятия', get: (v) => v.analysis.scores.ease, fmt: String, better: 'high' },
  { title: 'Читаемость на превью', get: (v) => v.analysis.scores.thumb, fmt: String, better: 'high' },
  { title: 'Контраст', get: (v) => v.analysis.scores.contrast, fmt: String, better: 'high' },
  {
    title: 'Половина внимания на площади',
    hint: 'меньше — лучше',
    get: (v) => v.analysis.raw.area50,
    fmt: (n) => pct(n),
    better: 'low',
  },
  {
    title: 'Центров внимания',
    hint: 'меньше — лучше',
    get: (v) => v.analysis.raw.hotspots,
    fmt: String,
    better: 'low',
  },
]

const aoiLabels = computed(() => [...new Set(variants.value.flatMap((v) => v.aois.map((x) => x.label)))])

const rows = computed<Row[]>(() => [
  ...BASE_ROWS,
  ...aoiLabels.value.map<Row>((label) => ({
    title: `Внимание: ${label}`,
    get: (v) => {
      const z = v.aois.find((x) => x.label === label)
      return z ? aoiStat(v.analysis.grid, z).share : null
    },
    fmt: (n) => pct(n),
    better: 'high',
  })),
])

// Лучшее значение в строке; если все равны или сравнивать не с чем — не подсвечиваем.
function best(vals: (number | null)[], better: Row['better']) {
  const nums = vals.filter((x): x is number => x !== null)
  if (nums.length < 2) return null
  const b = better === 'high' ? Math.max(...nums) : Math.min(...nums)
  return nums.every((x) => x === b) ? null : b
}

// Значения считаются один раз на строку, а не в каждой ячейке шаблона.
const table = computed(() =>
  rows.value.map((r) => {
    const vals = variants.value.map(r.get)
    const top = best(vals, r.better)
    return {
      row: r,
      cells: vals.map((x) => ({ text: x === null ? '—' : r.fmt(x), best: x !== null && x === top })),
    }
  }),
)

const leader = computed(() => {
  const [first, second] = [...variants.value].sort((a, b) => b.analysis.index - a.analysis.index)
  if (!first || !second) return null
  return { v: first, gap: first.analysis.index - second.analysis.index }
})

const expertLeader = computed(() => state.compare?.ranking[0] ?? null)
const records = ref(false)

const pairs = computed(() => {
  const map = new Map<string, { a: string; b: string; wins: Record<string, number>; reasons: string[] }>()
  for (const r of state.compare?.records ?? []) {
    const [a, b] = [...r.shown].sort()
    const k = a + b
    let p = map.get(k)
    if (!p) {
      p = { a, b, wins: { [a]: 0, [b]: 0 }, reasons: [] }
      map.set(k, p)
    }
    p.wins[r.winner]++
    if (r.reason) p.reasons.push(`За ${r.winner}: ${r.reason}`)
  }
  return [...map.values()]
})
</script>

<template>
  <div class="compare scroll-y">
    <header class="head">
      <div>
        <span class="label">
          Сравнение · {{ variants.length }} {{ plural(variants.length, ['вариант', 'варианта', 'вариантов']) }}
        </span>
        <h2 v-if="leader">
          По вниманию лидирует <span class="k">{{ leader.v.key }}</span>
          <small v-if="leader.gap > 0" class="num">+{{ leader.gap }} к индексу</small>
          <small v-else class="num">— ничья по индексу</small>
        </h2>
        <p v-if="expertLeader" class="choice">
          Покупатель скорее выберет <b>{{ expertLeader.key }}</b> — вероятность {{ expertLeader.chance }}%
          <template v-if="leader && expertLeader.key === leader.v.key">
            — и по вниманию, и по выбору лидирует один вариант. Уверенный кандидат в запуск.</template
          >
          <template v-else>
            — заметнее не значит кликабельнее. Проверьте, сколько внимания получает товар и почему покупатель выбирает
            другой вариант.</template
          >
        </p>
      </div>
      <Segmented v-model="state.mode" :options="OVERLAY_MODES" size="sm" label="Режим наложения" />
    </header>

    <div class="cols" :style="{ '--n': variants.length }">
      <figure v-for="v in variants" :key="v.key" class="col">
        <HeatImage
          :src="v.url"
          :width="v.analysis.width"
          :height="v.analysis.height"
          :grid="v.analysis.grid"
          :fixations="v.analysis.fixations"
          :mode="state.mode"
          :opacity="state.opacity"
          :aois="v.aois"
          compact
        />
        <figcaption>
          <KeyBadge :k="v.key" :win="leader?.v.key === v.key && leader.gap > 0" />
          <span class="idx num">{{ v.analysis.index }}</span>
          <span class="num cap-name" :title="v.name">{{ baseName(v.name) }}</span>
        </figcaption>
      </figure>
    </div>

    <!-- на телефоне таблица прокручивается сама, а не растягивает страницу -->
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th class="label">Метрика</th>
            <th v-for="v in variants" :key="v.key" class="label">{{ v.key }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="{ row, cells } in table" :key="row.title">
            <td>
              {{ row.title }}<span v-if="row.hint" class="hint num">{{ row.hint }}</span>
            </td>
            <td v-for="(cell, i) in cells" :key="variants[i].key" class="num" :class="{ best: cell.best }">
              {{ cell.text }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="!aoiLabels.length" class="note num">
      Совет: обведите на каждом варианте зону «Товар» — появится строка с долей внимания на товаре.
    </p>

    <section v-if="expertEnabled" class="expert card">
      <div class="expert-head">
        <div>
          <span class="label">Выбор покупателя</span>
          <h3>На какой вариант скорее нажмут?</h3>
          <p>
            Если показать варианты рядом, покупатель выберет этот с такой вероятностью — по попарным сравнениям
            нескольких экспертов.
          </p>
        </div>
        <div class="ask">
          <button class="btn primary" :disabled="state.compareStatus === 'loading'" @click="runCompare">
            <Loader2 v-if="state.compareStatus === 'loading'" :size="15" class="spin" />
            <Scale v-else :size="15" />
            {{ state.compareStatus === 'loading' ? 'Сравниваем…' : state.compare ? 'Сравнить заново' : 'Сравнить' }}
          </button>
        </div>
      </div>

      <p v-if="state.compareStatus === 'error'" class="err">{{ state.compareError }}</p>

      <div v-if="state.compare" class="rank rise">
        <div v-for="(r, i) in state.compare.ranking" :key="r.key" class="rrow" :class="{ lead: i === 0 }">
          <KeyBadge :k="r.key" :win="i === 0" />
          <div class="rmain">
            <span class="rt"
              >Вероятность выбора <b class="num">{{ r.chance }}%</b></span
            >
            <div class="rbar"><i :style="{ width: `${r.chance}%` }" :class="{ win: i === 0 }" /></div>
          </div>
          <span class="num rw">выбран {{ r.wins }} из {{ r.played }}</span>
        </div>
        <p v-if="state.compare.errors.length" class="failed">
          {{ silentExperts(state.compare.errors.length) }}
        </p>
        <button class="btn sm ghost" :aria-expanded="records" @click="records = !records">
          {{ records ? 'Скрыть причины' : 'Почему так' }}
        </button>
        <div v-if="records" class="pairs">
          <div v-for="p in pairs" :key="p.a + p.b" class="pair">
            <span class="num pt">{{ p.a }} против {{ p.b }} · {{ p.wins[p.a] }}:{{ p.wins[p.b] }}</span>
            <ul>
              <li v-for="(r, i) in p.reasons" :key="i">{{ r }}</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.compare {
  flex: 1;
  padding: 26px clamp(20px, 3vw, 40px) 48px;
  display: grid;
  align-content: start;
  gap: 28px;
  min-height: 0;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 20px;
  flex-wrap: wrap;
}

h2 {
  margin: 8px 0 0;
  font-size: 30px;
  font-weight: 300;
  letter-spacing: -0.03em;
  line-height: 1.1;
}

h2 .k {
  display: inline-grid;
  place-items: center;
  min-width: 42px;
  height: 42px;
  padding: 0 8px;
  border-radius: 9px;
  background: var(--lime);
  color: var(--on-tile);
  font-size: 26px;
  font-weight: 400;
  vertical-align: -4px;
}

h2 small {
  margin-left: 10px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0;
  color: var(--ink-3);
}

.choice {
  margin: 10px 0 0;
  max-width: 720px;
  color: var(--ink-2);
  font-size: 14px;
}

.cols {
  display: grid;
  grid-template-columns: repeat(var(--n), minmax(0, 1fr));
  gap: 18px;
  align-items: end;
}

.col {
  margin: 0;
  display: grid;
  gap: 10px;
}

figcaption {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.idx {
  font-size: 22px;
  font-weight: 300;
  letter-spacing: -0.03em;
}

.cap-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: var(--ink-3);
}

.table-wrap {
  overflow-x: auto;
}

.table {
  width: 100%;
  min-width: 480px;
  border-collapse: collapse;
  font-size: 13.5px;
}

.table th {
  text-align: right;
  padding: 0 12px 10px;
  border-bottom: 1px solid var(--line-strong);
}

.table th:first-child,
.table td:first-child {
  text-align: left;
  padding-left: 0;
}

.table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  text-align: right;
}

.table td.best {
  font-weight: 600;
  background: var(--lime-soft);
  box-shadow: inset 0 -2px 0 var(--lime);
}

.table td.num {
  color: var(--ink-2);
}

/* лучшее значение в строке: после .num и с той же специфичностью, чтобы цвет не перебивался */
.table td.num.best {
  color: var(--ink);
}

.hint {
  margin-left: 10px;
  font-size: 10.5px;
  color: var(--ink-3);
}

.note {
  margin: -16px 0 0;
  font-size: 11px;
  color: var(--ink-3);
}

.expert {
  padding: 22px 24px;
  display: grid;
  gap: 18px;
}

.expert-head {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}

.expert-head h3 {
  margin: 6px 0 6px;
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.expert-head p {
  margin: 0;
  max-width: 560px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ink-2);
}

.ask {
  display: grid;
  justify-items: end;
  gap: 8px;
  align-content: start;
}

.err {
  margin: 0;
  color: var(--bad);
  font-size: 13px;
}

.rank {
  display: grid;
  gap: 10px;
}

.rrow {
  display: grid;
  grid-template-columns: 24px 1fr 90px;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  margin: 0 -12px;
  border-radius: 10px;
}

/* лидер — лаймовая подложка, как лучшая ячейка в таблице */
.rrow.lead {
  background: var(--lime-soft);
}

.rmain {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.rt {
  font-size: 13px;
  color: var(--ink-2);
}

.rt b {
  margin-left: 4px;
  font-size: 22px;
  font-weight: 300;
  letter-spacing: -0.03em;
  color: var(--ink);
}

.rbar {
  height: 10px;
  border-radius: 5px;
  background: var(--panel-2);
  overflow: hidden;
}

.rbar i {
  display: block;
  height: 100%;
  background: var(--ink-3);
  border-radius: 5px;
  transition: width 0.6s cubic-bezier(0.2, 0.7, 0.2, 1);
}

.rbar i.win {
  background: var(--ink);
}

.rw {
  text-align: right;
}

.rw,
.failed {
  font-size: 11px;
  color: var(--ink-3);
}

.failed {
  margin: 0;
}

.pairs {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.pair .pt {
  font-size: 11.5px;
  font-weight: 600;
}

.pair ul {
  margin: 6px 0 0;
  padding-left: 16px;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--ink-2);
}

@media (max-width: 900px) {
  .cols {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* на телефоне все четыре колонки помещаются в экран: подсказка уходит под название метрики */
@media (max-width: 600px) {
  .table {
    min-width: 0;
    font-size: 13px;
  }
  .table th,
  .table td {
    padding-left: 6px;
    padding-right: 6px;
  }
  .hint {
    display: block;
    margin: 2px 0 0;
  }
  .rrow {
    grid-template-columns: 24px 1fr;
  }
  .rw {
    grid-column: 2;
    text-align: left;
  }
}
</style>
