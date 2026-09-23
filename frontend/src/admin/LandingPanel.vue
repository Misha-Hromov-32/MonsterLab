<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, toRaw } from 'vue'
import { Check, ExternalLink, Loader2 } from 'lucide-vue-next'
import { adminApi } from './adminApi'
import type { AdminSettings, Design, Landing } from '../lib/types'

const props = defineProps<{ data: AdminSettings }>()
const emit = defineEmits<{ saved: [msg: string] }>()

// structuredClone не умеет Proxy — копируем исходный объект за реактивной обёрткой
const form = ref<Landing>(structuredClone(toRaw(props.data.landing)))
const saved = ref(JSON.stringify(props.data.landing))
const dirty = computed(() => JSON.stringify(form.value) !== saved.value)
const busy = ref(false)
const error = ref('')

// список вариантов присылает сервер, здесь — только подписи к ним
const DESIGN_INFO: Record<Design, { title: string; text: string }> = {
  split: { title: 'До / после', text: 'Справа обложка со шторкой: потяните — проявится карта внимания.' },
  feed: { title: 'Лента', text: 'Тёмная выдача на весь экран, туман и «фонарик» за курсором.' },
  editorial: { title: 'Редакция', text: 'Крупная типографика, ничего лишнего. Спокойно и строго.' },
}
const designs = computed(() =>
  props.data.designs.map((id) => ({ id, ...(DESIGN_INFO[id] ?? { title: id, text: '' }) })),
)

// в порядке обхода Tab участвует только выбранная карточка (если выбора нет — первая)
const focusIndex = computed(() =>
  Math.max(
    0,
    designs.value.findIndex((d) => d.id === form.value.design),
  ),
)
// ref-массив в v-for не гарантирует порядок — раскладываем по индексу сами
const radios: HTMLElement[] = []

function onRadioKey(e: KeyboardEvent, i: number) {
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key]
  if (step) {
    e.preventDefault()
    const n = designs.value.length
    const j = (i + step + n) % n
    form.value.design = designs.value[j].id
    radios[j]?.focus()
  } else if (e.key === ' ' || e.key === 'Enter') {
    e.preventDefault()
    form.value.design = designs.value[i].id
  }
}

// миниатюра — настоящий сайт в iframe 1440×900, уменьшенный под ширину карточки;
// preview=1 отключает на нём опрос состояния сервиса и перехват перетаскивания файлов
const previews = ref<HTMLElement[]>([])
const previewRev = ref(0)
const previewUrl = (id: Design) => `/?design=${id}&preview=1`
let ro: ResizeObserver | undefined
onMounted(() => {
  ro = new ResizeObserver((entries) => {
    for (const e of entries) (e.target as HTMLElement).style.setProperty('--k', String(e.contentRect.width / 1440))
  })
  previews.value.forEach((el) => ro!.observe(el))
})
onUnmounted(() => ro?.disconnect())

async function save() {
  busy.value = true
  error.value = ''
  try {
    await adminApi.saveLanding(form.value)
    saved.value = JSON.stringify(form.value)
    previewRev.value++ // пересоздаём iframe, чтобы миниатюры подхватили новые тексты
    emit('saved', 'Главная сохранена')
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
        <h1>Главная страница</h1>
        <p>Выберите вариант дизайна и отредактируйте тексты. Примеры и витрина берутся из раздела «Примеры».</p>
      </div>
      <div class="actions">
        <span v-if="dirty" class="dirty num">есть несохранённые изменения</span>
        <button class="btn primary" :disabled="!dirty || busy" @click="save">
          <Loader2 v-if="busy" :size="15" class="spin" /><Check v-else :size="15" /> Сохранить
        </button>
      </div>
    </header>
    <p v-if="error" class="err">{{ error }}</p>

    <section>
      <h2 id="design-label" class="label">Вариант дизайна</h2>
      <div class="designs" role="radiogroup" aria-labelledby="design-label">
        <div v-for="(d, i) in designs" :key="d.id" class="design" :class="{ on: form.design === d.id }">
          <div
            :ref="(el) => (radios[i] = el as HTMLElement)"
            class="opt"
            role="radio"
            :aria-checked="form.design === d.id"
            :aria-label="d.title"
            :tabindex="i === focusIndex ? 0 : -1"
            @click="form.design = d.id"
            @keydown="onRadioKey($event, i)"
          >
            <div ref="previews" class="preview">
              <iframe
                :key="`${d.id}-${previewRev}`"
                :src="previewUrl(d.id)"
                tabindex="-1"
                loading="lazy"
                :title="`Миниатюра: ${d.title}`"
                aria-hidden="true"
              />
            </div>
            <div class="dmeta">
              <span class="radio"><i /></span>
              <div>
                <strong>{{ d.title }}</strong>
                <p>{{ d.text }}</p>
              </div>
            </div>
          </div>
          <!-- ссылка вне role="radio": интерактивный элемент внутри радиокнопки недоступен с клавиатуры -->
          <a
            :href="`/?design=${d.id}`"
            target="_blank"
            class="open btn ghost sm icon"
            title="Открыть во весь экран"
            :aria-label="`Открыть «${d.title}» во весь экран`"
          >
            <ExternalLink :size="14" />
          </a>
        </div>
      </div>
      <p class="note num">Миниатюры показывают сохранённые тексты и обновляются после сохранения.</p>
    </section>

    <section class="texts">
      <h2 class="label">Тексты</h2>
      <div class="grid2">
        <label class="field">
          <span class="flabel">Надзаголовок</span>
          <input v-model="form.eyebrow" class="input" maxlength="80" />
        </label>
        <label class="field">
          <span class="flabel">Кнопка загрузки</span>
          <input v-model="form.cta" class="input" maxlength="40" />
        </label>
      </div>
      <label class="field">
        <span class="flabel">Заголовок</span>
        <input v-model="form.title" class="input big" maxlength="120" />
      </label>
      <label class="field">
        <span class="flabel">Продолжение заголовка (серым)</span>
        <input v-model="form.title_muted" class="input big" maxlength="160" />
      </label>
      <label class="field">
        <span class="flabel">Подзаголовок</span>
        <textarea v-model="form.lead" class="input area" rows="3" maxlength="600" />
      </label>

      <h2 class="label steps-label">Три шага</h2>
      <div class="steps">
        <div v-for="(s, i) in form.steps" :key="i" class="step">
          <span class="n num">0{{ i + 1 }}</span>
          <input
            v-model="s.title"
            class="input"
            maxlength="80"
            placeholder="Заголовок"
            :aria-label="`Шаг ${i + 1}: заголовок`"
          />
          <textarea
            v-model="s.text"
            class="input area"
            rows="4"
            maxlength="400"
            placeholder="Текст"
            :aria-label="`Шаг ${i + 1}: текст`"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
@import './panel.css';

.designs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

/* карточка — сетка из двух строк (миниатюра, подпись); радиокнопка занимает её целиком через subgrid,
   а ссылка ложится поверх во вторую строку справа */
.design {
  display: grid;
  grid-template-rows: auto auto;
  border: 1.5px solid var(--line);
  border-radius: 14px;
  overflow: hidden;
  background: var(--panel);
  transition:
    border-color 0.15s,
    box-shadow 0.2s;
}

.design:hover {
  border-color: var(--line-strong);
}

.design.on {
  border-color: var(--ink);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.opt {
  grid-row: 1 / 3;
  grid-column: 1;
  display: grid;
  grid-template-rows: subgrid;
  cursor: pointer;
  border-radius: 12px;
}

.opt:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.open {
  grid-row: 2;
  grid-column: 1;
  justify-self: end;
  align-self: start;
  margin: 14px 14px 0 0;
}

.preview {
  position: relative;
  aspect-ratio: 1440 / 900;
  overflow: hidden;
  background: var(--sunken);
  border-bottom: 1px solid var(--line);
}

.preview iframe {
  position: absolute;
  left: 0;
  top: 0;
  width: 1440px;
  height: 900px;
  border: 0;
  transform: scale(var(--k, 0.25));
  transform-origin: 0 0;
  pointer-events: none;
}

.dmeta {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 12px;
  align-items: start;
  /* справа место под ссылку «открыть во весь экран» (28px + отступ) */
  padding: 14px 54px 14px 14px;
}

.dmeta strong {
  font-size: 14px;
  font-weight: 600;
}

.dmeta p {
  margin: 2px 0 0;
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--ink-3);
}

.radio {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  margin-top: 1px;
  border-radius: 50%;
  border: 1.5px solid var(--line-strong);
}

.design.on .radio {
  border-color: var(--ink);
}

.design.on .radio i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
}

.note {
  margin: 10px 0 0;
  font-size: 11px;
  color: var(--ink-3);
}

.texts {
  display: grid;
  gap: 14px;
  max-width: 900px;
}

.steps-label {
  margin-top: 12px;
}

.big {
  height: 40px;
  font-size: 15px;
}

.steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.step {
  display: grid;
  gap: 8px;
  align-content: start;
}

.n {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
}

@media (max-width: 1100px) {
  .designs,
  .steps {
    grid-template-columns: 1fr;
  }
}
</style>
