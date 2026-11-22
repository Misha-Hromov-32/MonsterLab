<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { ArrowRight, Download, ImagePlus, Loader2, RefreshCw, Replace, Sparkles } from 'lucide-vue-next'
import { addImproved, critiqueIssues, freeKeys, improvedFile, runImprove, state } from '../store'
import ModalDialog from './ModalDialog.vue'
import { openTariffs } from '../lib/account'
import { useModelPrice } from '../lib/modelPrice'
import ModelFields from './ModelFields.vue'
import { IMPROVE_ETA_SEC } from '../lib/constants'
import type { Variant } from '../lib/types'

const props = defineProps<{ variant: Variant }>()
const v = computed(() => props.variant)
const model = computed({
  get: () => v.value.improveModel ?? '',
  set: (value: string) => {
    v.value.improveModel = value
  },
})
const prompt = computed({
  get: () => v.value.improvePrompt ?? '',
  set: (value: string) => {
    v.value.improvePrompt = value
  },
})

// выводы экспертов усиливают перерисовку — говорим об этом, чтобы было ясно, зачем их запрашивать
const editor = ref(false)
const { price, balance, shortfall, affordable } = useModelPrice(model)
function generate() {
  if (!model.value || shortfall.value || v.value.improveStatus === 'loading') return
  editor.value = false
  void runImprove(v.value, model.value, prompt.value)
}
function plans() {
  editor.value = false
  openTariffs()
}
const withCritique = computed(() => critiqueIssues(v.value).length > 0)

// Секундомер ожидания: начало — в варианте, поэтому при переключении вариантов полоса не сбрасывается.
const elapsed = ref(0)
let timer = 0
watch(
  () => [v.value.improveStatus, v.value.improveStartedAt] as const,
  ([s, t]) => {
    clearInterval(timer)
    if (s !== 'loading' || !t) return
    const tick = () => (elapsed.value = Math.round((Date.now() - t) / 1000))
    tick()
    timer = window.setInterval(tick, 500)
  },
  { immediate: true },
)
onUnmounted(() => clearInterval(timer))

// полоса не доходит до конца, пока ответа нет: генерация иногда дольше обычного
const progress = computed(() => Math.min(95, (elapsed.value / IMPROVE_ETA_SEC) * 100))
const waitText = computed(() =>
  elapsed.value < IMPROVE_ETA_SEC ? `ещё около ${IMPROVE_ETA_SEC - elapsed.value} с` : 'ожидаем результат…',
)

// нет свободного слота — предлагаем заменить один из вариантов
const replaceKeys = computed(() => (freeKeys.value.length ? [] : state.variants.map((x) => x.key)))

function download() {
  const file = improvedFile(v.value)
  if (!file || !v.value.improved) return
  const a = document.createElement('a')
  a.href = v.value.improved
  a.download = file.name
  a.click()
}
</script>

<template>
  <section class="improve">
    <header class="tool-heading">
      <span class="tool-symbol"><Sparkles :size="20" /></span>
      <h3>Генератор обложек</h3>
    </header>
    <div v-if="v.improveStatus === 'loading'" class="wait" role="status">
      <span class="wait-title"><Loader2 :size="15" class="spin" /> Перерисовываем обложку…</span>
      <span class="prog"><i :style="{ width: `${progress}%` }" /></span>
      <span class="hint num">Обычно это занимает около {{ IMPROVE_ETA_SEC }} секунд · {{ waitText }}</span>
    </div>

    <div v-else-if="v.improveStatus === 'ready' && v.improved" class="result rise">
      <div class="pair">
        <figure>
          <img :src="v.url" alt="Исходная обложка" />
          <figcaption class="label">Было</figcaption>
        </figure>
        <figure>
          <img :src="v.improved" alt="Улучшенная обложка" />
          <figcaption class="label now">Стало</figcaption>
        </figure>
      </div>
      <p class="hint">Добавьте вариант для сравнения с исходной обложкой.</p>
      <div class="acts">
        <button v-if="!replaceKeys.length" class="btn primary" @click="addImproved(v)">
          <ImagePlus :size="15" /> Добавить как вариант
        </button>
        <div v-else class="replace" role="group" aria-label="Заменить вариант">
          <span class="hint"><Replace :size="13" /> Заменить вариант:</span>
          <button
            v-for="k in replaceKeys"
            :key="k"
            class="btn sm key num"
            :title="`Заменить вариант ${k}`"
            :aria-label="`Заменить вариант ${k}`"
            @click="addImproved(v, k)"
          >
            {{ k }}
          </button>
        </div>
        <button class="btn" @click="download"><Download :size="14" /> Скачать</button>
      </div>
      <button class="lab-secondary" @click="editor = true"><RefreshCw :size="15" /> Ещё один вариант</button>
    </div>
    <div v-else class="ask">
      <p class="hint">Создайте новую версию этого изображения. Модель и задание можно выбрать перед запуском.</p>
      <button class="open-editor" @click="editor = true">Открыть генератор <ArrowRight :size="16" /></button>
      <p v-if="v.improveStatus === 'error'" class="err" role="alert">{{ v.improveError }}</p>
    </div>
    <ModalDialog v-if="editor" title="Новая версия обложки" roomy @close="editor = false">
      <div class="variant-editor">
        <figure class="editor-source">
          <img :src="v.url" alt="Исходная обложка" />
          <figcaption>Вариант {{ v.key }} · Исходное изображение</figcaption>
        </figure>
        <form class="editor-form" @submit.prevent="generate">
          <ModelFields v-model:model="model" v-model:prompt="prompt" />
          <p v-if="withCritique" class="hint">В задание войдут рекомендации из визуального разбора.</p>
          <div class="editor-price">
            <span>Стоимость генерации</span><strong>{{ price === undefined ? '…' : price + ' имп.' }}</strong
            ><template v-if="balance !== undefined"
              ><span>Ваш баланс</span><b>{{ balance }} имп.</b></template
            >
          </div>
          <p v-if="shortfall" class="available">
            Для выбранной модели не хватает импульсов.
            <button v-if="affordable" type="button" class="model-link" @click="model = affordable.id">
              Выбрать {{ affordable.title }} за {{ affordable.cost }} имп.
            </button>
            <button v-else type="button" class="model-link" @click="plans">Выбрать тариф</button>
          </p>
          <button class="lab-primary" :disabled="!model || price === undefined || shortfall">
            <Sparkles :size="16" /> Сгенерировать обложку
          </button>
        </form>
      </div>
    </ModalDialog>
  </section>
</template>

<style scoped>
.improve {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 17px;
  background: var(--panel);
  border: 1px solid color-mix(in srgb, var(--brand) 30%, var(--line));
  border-radius: 15px;
}
.tool-heading {
  display: flex;
  align-items: center;
  gap: 10px;
}
.tool-heading h3 {
  margin: 0;
  font: 700 18px/1.25 var(--font-sans);
  letter-spacing: -0.035em;
}
.tool-symbol {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  color: var(--brand);
  background: color-mix(in srgb, var(--brand) 10%, var(--panel));
}
.ask {
  display: grid;
  gap: 12px;
}
.hint {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ink-2);
}
.open-editor {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 9px;
  min-height: 42px;
  padding: 10px 14px;
  background: var(--panel-2);
  color: var(--ink);
  border: 1px solid var(--line-strong);
  border-radius: 9px;
  font-weight: 650;
}
.open-editor:hover {
  border-color: var(--brand);
}
.variant-editor {
  display: grid;
  grid-template-columns: minmax(0, 0.85fr) minmax(0, 1fr);
  gap: clamp(16px, 2vw, 28px);
  align-items: start;
}
.variant-editor .editor-source {
  padding: 14px;
  border-radius: 12px;
  background: #2b1729;
  gap: 12px;
}
.editor-source img {
  width: 100%;
  height: clamp(180px, 30vh, 320px);
  object-fit: contain;
  background: transparent;
  box-shadow: none;
}
.editor-source figcaption {
  font-size: 13px;
  color: #f6e8f3;
}
.editor-form {
  display: grid;
  gap: 14px;
}
.editor-price {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 5px 12px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
  font-size: 14px;
  color: var(--ink-2);
}
.editor-price strong,
.editor-price b {
  color: var(--ink);
  text-align: right;
}
.available {
  border-radius: 8px;
  background: var(--panel-2);
  padding: 10px;
  margin: 0;
  font-size: 13px;
}
.model-link {
  display: block;
  background: none;
  border: 0;
  text-decoration: underline;
  text-underline-offset: 3px;
  color: var(--ink);
  padding: 5px 0;
  text-align: left;
  font-weight: 650;
}
@media (max-width: 600px) {
  .variant-editor {
    grid-template-columns: minmax(0, 1fr);
  }
  .variant-editor .editor-source {
    grid-template-columns: 56px 1fr;
    align-items: center;
    padding: 9px 12px;
  }
  .editor-source img {
    height: 64px;
  }
  .editor-form {
    gap: 12px;
  }
}
.err {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: var(--bad);
}

.wait {
  display: grid;
  gap: 8px;
}

.wait-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}

.prog {
  display: block;
  height: 4px;
  border-radius: 2px;
  background: color-mix(in srgb, var(--ink) 10%, transparent);
  overflow: hidden;
}

.prog i {
  display: block;
  height: 100%;
  background: var(--accent);
  transition: width 0.5s linear;
}

.result {
  display: grid;
  gap: 12px;
}

.pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

figure {
  margin: 0;
  display: grid;
  gap: 6px;
}

figure img {
  width: 100%;
  aspect-ratio: 3 / 4;
  /* обложки бывают разных пропорций — показываем целиком, без обрезки */
  object-fit: contain;
  border-radius: 8px;
  background: var(--sunken);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--ink) 10%, transparent);
}

.label.now {
  color: var(--ink);
}

.replace {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  flex-basis: 100%;
}

.replace .hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-right: 2px;
}

.key {
  width: 30px;
  padding: 0;
  justify-content: center;
  font-weight: 600;
}

.acts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.again {
  justify-self: start;
  margin-left: -10px;
}

/* телефон: та же карточка, что у соседних разделов, но цветная; кнопка — во всю ширину */
@media (max-width: 900px) {
  .improve {
    margin: 0;
    padding: 20px 18px;
    border-radius: 22px;
  }
  .ask {
    gap: 10px;
    justify-items: stretch;
  }
  .hint,
  .err {
    font-size: 14px;
  }
  .acts .btn {
    height: 44px;
    border-radius: 12px;
    font-size: 14.5px;
  }
  .key {
    width: 44px;
  }
  .again {
    margin-left: 0;
    height: 40px;
    font-size: 14px;
  }
}
</style>
