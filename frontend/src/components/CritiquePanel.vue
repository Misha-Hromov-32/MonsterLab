<script setup lang="ts">
import { computed } from 'vue'
import { Check, Loader2, Sparkles, X } from 'lucide-vue-next'
import { expertEnabled, runCritique, state } from '../store'
import { VISUAL_MAX_RIVALS } from '../lib/constants'
import type { CritiqueScore, Variant } from '../lib/types'

// Визуальный разбор «как арт-директор»: целостная оценка стиля, позиционирования и смысла надписей —
// то, чего не видят метрики внимания. Ответ модели уже нормализован сервером (services/expert.py).
const props = defineProps<{ variant: Variant }>()
const c = computed(() => props.variant.critique)
const loading = computed(() => props.variant.critiqueStatus === 'loading')
const rivals = computed(() => Math.min(state.competitors.length, VISUAL_MAX_RIVALS))

const SCORE_TITLES: Record<CritiqueScore, string> = {
  aesthetics: 'Эстетика',
  offer: 'Ясность оффера',
  positioning: 'Позиционирование',
  standout: 'Выделяется в выдаче',
  trust: 'Доверие',
}
const scores = computed(() =>
  (Object.keys(SCORE_TITLES) as CritiqueScore[])
    .filter((k) => c.value?.scores[k] !== undefined)
    .map((k) => ({ k, title: SCORE_TITLES[k], v: c.value!.scores[k]! })),
)
const tone = (v: number) => (v >= 7 ? 'good' : v >= 5 ? 'warn' : 'bad')
const fmt = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1))

// подробности, которые читают по желанию — свёрнуты, чтобы главное (вердикт, сильное, что улучшить) было сверху
const details = computed(() =>
  [
    { title: 'Стиль и исполнение', text: c.value?.style },
    { title: 'Позиционирование', text: c.value?.positioning },
    { title: 'Порядок чтения', text: c.value?.reading_order },
    { title: 'Рядом с конкурентами', text: c.value?.shelf },
  ].filter((d) => d.text),
)
</script>

<template>
  <section v-if="expertEnabled" class="visual">
    <div class="sec-head">
      <span class="label">Визуальный разбор</span>
      <span class="label tag">как арт-директор</span>
    </div>

    <div v-if="variant.critiqueStatus !== 'ready' || !c" class="ask">
      <p class="pitch">
        Оценка визуала целиком: общее впечатление, стиль, какой сегмент и аудиторию считывает обложка, работает ли
        каждая надпись и как она смотрится рядом с конкурентами.
      </p>
      <p class="rivals">
        <template v-if="rivals"
          >Сравним с {{ rivals }} {{ rivals === 1 ? 'конкурентом' : 'конкурентами' }} с полки.</template
        >
        <template v-else>Добавьте конкурентов на вкладке «Полка» — разбор сравнит обложку с ними.</template>
      </p>
      <button class="btn primary" :disabled="loading" @click="runCritique(variant)">
        <Loader2 v-if="loading" :size="15" class="spin" />
        <Sparkles v-else :size="15" />
        {{ loading ? 'Арт-директор смотрит обложку… ~30 с' : 'Разобрать визуал' }}
      </button>
      <p v-if="variant.critiqueStatus === 'error'" class="err">{{ variant.critiqueError }}</p>
    </div>

    <div v-else class="result rise">
      <div class="top">
        <div v-if="c.overall !== null" class="overall" :class="tone(c.overall)">
          <span class="num">{{ fmt(c.overall) }}</span
          ><small class="num">/10</small>
        </div>
        <p class="verdict">{{ c.verdict || c.impression }}</p>
      </div>

      <div v-if="c.reads_as.segment || c.reads_as.mood" class="chips">
        <span v-if="c.reads_as.segment" class="chip lime">{{ c.reads_as.segment }}</span>
        <span v-if="c.reads_as.mood" class="chip lilac">{{ c.reads_as.mood }}</span>
      </div>
      <p v-if="c.reads_as.audience" class="audience"><b>Цепляет:</b> {{ c.reads_as.audience }}</p>

      <p v-if="c.verdict && c.impression" class="impression">{{ c.impression }}</p>

      <div v-if="scores.length" class="scores">
        <div v-for="s in scores" :key="s.k" class="score">
          <span class="st">{{ s.title }}</span>
          <div class="bar"><i :class="tone(s.v)" :style="{ width: `${(s.v / 10) * 100}%` }" /></div>
          <span class="sv num">{{ fmt(s.v) }}</span>
        </div>
      </div>

      <div v-if="c.strengths.length" class="block">
        <span class="label">Что сильного — не трогать</span>
        <ul class="strengths">
          <li v-for="(s, i) in c.strengths" :key="i"><Check :size="14" aria-hidden="true" />{{ s }}</li>
        </ul>
      </div>

      <div v-if="c.improvements.length" class="block">
        <span class="label">Что улучшить</span>
        <ol class="improvements">
          <li v-for="(it, i) in c.improvements" :key="i">
            <strong>{{ it.what }}</strong>
            <p v-if="it.why">{{ it.why }}</p>
            <p v-if="it.how" class="how"><b>Как:</b> {{ it.how }}</p>
          </li>
        </ol>
      </div>
      <p v-else class="nothing">Менять нечего — обложка сильная.</p>

      <details v-for="d in details" :key="d.title" class="more">
        <summary>{{ d.title }}</summary>
        <p>{{ d.text }}</p>
      </details>

      <details v-if="c.messages.length" class="more">
        <summary>Надписи на обложке · {{ c.messages.length }}</summary>
        <ul class="messages">
          <li v-for="(m, i) in c.messages" :key="i" :class="{ off: !m.works }">
            <span class="mt">
              <component
                :is="m.works ? Check : X"
                :size="13"
                class="mi"
                :aria-label="m.works ? 'работает' : 'не работает'"
              />
              «{{ m.text }}»
              <span class="role">{{ m.role }}</span>
            </span>
            <span v-if="m.comment" class="mc">{{ m.comment }}</span>
          </li>
        </ul>
      </details>

      <button class="btn sm ghost again" :disabled="loading" @click="runCritique(variant)">
        <Loader2 v-if="loading" :size="14" class="spin" />
        Разобрать ещё раз
      </button>
    </div>
  </section>
</template>

<style scoped>
.visual {
  padding-bottom: 22px;
  border-bottom: 1px solid var(--line);
}

.sec-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}

.tag {
  color: var(--accent);
}

.ask {
  display: grid;
  gap: 10px;
  justify-items: start;
}

.pitch {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.5;
}

.rivals {
  margin: 0;
  font-size: 12px;
  color: var(--ink-3);
}

.err {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: var(--bad);
}

.result {
  display: grid;
  gap: 16px;
}

.top {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  align-items: center;
}

.overall {
  display: flex;
  align-items: baseline;
  gap: 2px;
  padding: 10px 14px;
  border-radius: 14px;
  background: var(--lime);
  color: var(--on-tile);
}

.overall.warn {
  background: var(--sun);
}

.overall.bad {
  background: color-mix(in srgb, var(--bad) 22%, var(--panel));
  color: var(--ink);
}

.overall .num {
  font-size: 34px;
  line-height: 1;
  font-weight: 400;
  letter-spacing: -0.04em;
}

.overall small {
  font-size: 13px;
  opacity: 0.7;
}

.verdict {
  margin: 0;
  font-size: 14.5px;
  line-height: 1.45;
  font-weight: 500;
  letter-spacing: -0.01em;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: -8px;
}

.chip {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  color: var(--on-tile);
}

.chip.lime {
  background: var(--lime);
}

.chip.lilac {
  background: var(--lilac);
}

.audience,
.impression {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--ink-2);
}

.audience b {
  color: var(--ink);
  font-weight: 500;
}

.scores {
  display: grid;
  gap: 9px;
}

.score {
  display: grid;
  grid-template-columns: 132px 1fr 28px;
  gap: 10px;
  align-items: center;
}

.st {
  font-size: 12.5px;
  color: var(--ink-2);
}

.bar {
  height: 6px;
  border-radius: 3px;
  background: var(--panel-2);
  overflow: hidden;
}

.bar i {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: var(--ink);
}

.bar i.warn {
  background: var(--warn);
}

.bar i.bad {
  background: var(--bad);
}

.sv {
  font-size: 13px;
  font-weight: 600;
  text-align: right;
}

.block {
  display: grid;
  gap: 8px;
}

.strengths,
.improvements,
.messages {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

.strengths li {
  display: grid;
  grid-template-columns: 16px 1fr;
  gap: 8px;
  font-size: 13px;
  line-height: 1.5;
}

.strengths :deep(svg) {
  margin-top: 3px;
  color: var(--good);
}

.improvements {
  counter-reset: imp;
  gap: 10px;
}

.improvements li {
  counter-increment: imp;
  position: relative;
  padding: 12px 14px 12px 40px;
  border-radius: var(--radius);
  background: var(--panel-2);
}

.improvements li::before {
  content: counter(imp);
  position: absolute;
  left: 12px;
  top: 11px;
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--ink);
  color: var(--bg);
  font-size: 11.5px;
  font-weight: 600;
}

.improvements strong {
  display: block;
  font-size: 13.5px;
  font-weight: 600;
  line-height: 1.4;
}

.improvements p {
  margin: 4px 0 0;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--ink-2);
}

.improvements .how {
  color: var(--ink);
}

.improvements .how b {
  font-weight: 600;
}

.nothing {
  margin: 0;
  font-size: 13px;
  color: var(--good);
}

.more {
  border-top: 1px solid var(--line);
  padding-top: 10px;
}

.more summary {
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  list-style-position: outside;
}

.more p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--ink-2);
}

.messages {
  margin-top: 10px;
}

.messages li {
  display: grid;
  gap: 2px;
}

.mt {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
}

.mi {
  color: var(--good);
}

.messages li.off .mi {
  color: var(--bad);
}

.role {
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--panel-2);
  color: var(--ink-2);
  font-size: 11px;
  font-weight: 400;
}

.mc {
  padding-left: 19px;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--ink-2);
}

.again {
  justify-self: start;
  margin-left: -10px;
}
</style>
