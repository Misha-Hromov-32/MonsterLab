<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Loader2, MessageSquareText } from 'lucide-vue-next'
import { expertEnabled, runCritique } from '../store'
import { silentExperts } from '../lib/format'
import type { ExpertScore, Variant } from '../lib/types'

const props = defineProps<{ variant: Variant }>()
const c = computed(() => props.variant.critique)
const tab = ref(0)
// новый разбор или другой вариант — начинаем с первого эксперта
watch(
  () => [props.variant.key, props.variant.critique],
  () => (tab.value = 0),
)

// ключи — из ответа моделей; не путать с метриками анализа (там ease — «Лёгкость восприятия»)
const SCORE_TITLES: Record<string, string> = {
  clarity: 'Понятность',
  trust: 'Доверие',
  premium: 'Премиальность',
  emotion: 'Эмоция',
  readability: 'Читаемость',
}
const SEV: Record<string, string> = { high: 'bad', medium: 'warn', low: '' }

// оценки экспертов — по шкале 1–10; пропускаем пустые, чтобы в разметке не было проверок на undefined
const scores = computed(() =>
  Object.entries(c.value?.scores ?? {}).filter((e): e is [string, ExpertScore] => e[1] !== undefined),
)
const toPct = (n: number) => `${((n - 1) / 9) * 100}%`

const opinion = computed(() => {
  const ops = c.value?.opinions ?? []
  return ops[Math.min(tab.value, ops.length - 1)]
})

const tabs = ref<HTMLButtonElement[]>([])
function onTabKey(e: KeyboardEvent, n: number) {
  const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
  if (!step) return
  e.preventDefault()
  tab.value = (tab.value + step + n) % n
  tabs.value[tab.value]?.focus()
}
</script>

<template>
  <section v-if="expertEnabled" class="expert">
    <div class="sec-head">
      <span class="label">Экспертный разбор</span>
    </div>

    <div v-if="variant.critiqueStatus !== 'ready' || !c" class="ask">
      <button class="btn primary" :disabled="variant.critiqueStatus === 'loading'" @click="runCritique(variant)">
        <Loader2 v-if="variant.critiqueStatus === 'loading'" :size="15" class="spin" />
        <MessageSquareText v-else :size="15" />
        {{ variant.critiqueStatus === 'loading' ? 'Эксперт изучает обложку…' : 'Получить экспертный разбор' }}
      </button>
      <span class="who"
        >Что поймёт покупатель, вызывает ли доверие, какие надписи не читаются и что конкретно исправить.</span
      >
      <p v-if="variant.critiqueStatus === 'error'" class="err">{{ variant.critiqueError }}</p>
    </div>

    <div v-else class="result rise">
      <blockquote v-if="c.opinions[0]?.offer" class="offer">
        «{{ c.opinions[0].offer }}»
        <cite class="num">так поймёт покупатель за 1 секунду</cite>
      </blockquote>

      <div class="scores">
        <div v-for="[k, s] in scores" :key="k" class="score">
          <span class="st">{{ SCORE_TITLES[k] ?? k }}</span>
          <div class="range">
            <i class="span" :style="{ left: toPct(s.min), width: `${((s.max - s.min) / 9) * 100}%` }" />
            <i class="pt" :style="{ left: toPct(s.mean) }" />
          </div>
          <span class="sv num">{{ s.mean.toFixed(1) }}</span>
        </div>
        <div v-if="c.price_guess" class="score price">
          <span class="st">Ожидаемая цена</span>
          <span class="sv num">≈ {{ c.price_guess.toLocaleString('ru-RU') }} ₽</span>
        </div>
      </div>

      <div v-if="c.opinions.length > 1" class="tabs" role="radiogroup" aria-label="Мнение эксперта">
        <button
          v-for="(o, i) in c.opinions"
          :key="o.model"
          ref="tabs"
          type="button"
          role="radio"
          :aria-checked="tab === i"
          :tabindex="tab === i ? 0 : -1"
          :class="{ on: tab === i }"
          @click="tab = i"
          @keydown="onTabKey($event, c.opinions.length)"
        >
          Эксперт {{ i + 1 }}
        </button>
      </div>

      <div v-if="opinion" class="opinion">
        <p v-if="opinion.verdict" class="verdict">{{ opinion.verdict }}</p>
        <ul v-if="opinion.issues?.length" class="issues">
          <li v-for="(it, i) in opinion.issues" :key="i">
            <i class="dot" :class="SEV[it.severity]" />
            <div>
              <strong>{{ it.problem }}</strong>
              <p>{{ it.fix }}</p>
            </div>
          </li>
        </ul>
        <div v-if="opinion.strengths?.length" class="strengths">
          <span class="label">Сильные стороны</span>
          <ul>
            <li v-for="(s, i) in opinion.strengths" :key="i">{{ s }}</li>
          </ul>
        </div>
        <div v-if="opinion.texts?.length" class="texts">
          <span class="label">Надписи на обложке</span>
          <ul>
            <li v-for="(t, i) in opinion.texts" :key="i" :class="{ bad: !t.legible_on_thumb }">
              <span>{{ t.text }}</span>
              <span class="num">{{ t.legible_on_thumb ? 'читается' : 'мелко' }}</span>
            </li>
          </ul>
        </div>
      </div>

      <p v-if="c.errors.length" class="failed">{{ silentExperts(c.errors.length) }}</p>

      <button class="btn sm ghost again" @click="runCritique(variant)">Спросить ещё раз</button>
    </div>
  </section>
</template>

<style scoped>
.expert {
  padding-top: 22px;
  border-top: 1px solid var(--line);
}

.sec-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.ask {
  display: grid;
  gap: 8px;
  justify-items: start;
}

.who {
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--ink-3);
}

.err {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: var(--bad);
}

.result {
  display: grid;
  gap: 18px;
}

.offer {
  margin: 0;
  padding: 14px 16px;
  border-radius: var(--radius);
  background: var(--panel);
  border: 1px solid var(--line);
  font-size: 15px;
  line-height: 1.45;
  font-weight: 500;
  letter-spacing: -0.01em;
}

.offer cite {
  display: block;
  margin-top: 8px;
  font-size: 10.5px;
  font-style: normal;
  font-weight: 400;
  color: var(--ink-3);
}

.scores {
  display: grid;
  gap: 10px;
}

.score {
  display: grid;
  grid-template-columns: 112px 1fr 34px;
  align-items: center;
  gap: 10px;
}

.score.price {
  grid-template-columns: 112px 1fr;
}

.score.price .sv {
  text-align: left;
}

.st {
  font-size: 13px;
  color: var(--ink-2);
}

.range {
  position: relative;
  height: 4px;
  border-radius: 2px;
  background: var(--panel-2);
}

.range .span {
  position: absolute;
  top: 0;
  bottom: 0;
  min-width: 2px;
  background: var(--line-strong);
  border-radius: 2px;
}

.range .pt {
  position: absolute;
  top: 50%;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--ink);
  border: 2px solid var(--bg);
  transform: translate(-50%, -50%);
}

.sv {
  font-size: 13px;
  font-weight: 600;
  text-align: right;
}

.tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--line);
}

.tabs button {
  position: relative;
  padding: 6px 8px;
  border: 0;
  background: none;
  font-size: 12.5px;
  color: var(--ink-3);
}

.tabs button.on {
  color: var(--ink);
}

.tabs button.on::after {
  content: '';
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: -1px;
  height: 2px;
  background: var(--ink);
}

.opinion {
  display: grid;
  gap: 16px;
}

.verdict {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.5;
}

.issues {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
}

.issues li {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
}

.issues .dot {
  margin-top: 6px;
}

.issues strong {
  font-size: 13px;
  font-weight: 600;
}

.issues p {
  margin: 2px 0 0;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--ink-2);
}

.strengths ul,
.texts ul {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  display: grid;
  gap: 5px;
  font-size: 12.5px;
  color: var(--ink-2);
}

.strengths li::before {
  content: '+ ';
  color: var(--good);
}

.texts li {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.texts li .num {
  font-size: 10.5px;
  color: var(--good);
  white-space: nowrap;
}

.texts li.bad .num {
  color: var(--bad);
}

.failed {
  margin: 0;
  font-size: 11px;
  color: var(--ink-3);
}

.again {
  justify-self: start;
  margin-left: -10px;
}
</style>
