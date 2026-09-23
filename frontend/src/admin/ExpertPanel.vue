<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, Loader2, Plug, Plus, X } from 'lucide-vue-next'
import { adminApi, type CheckResult } from './adminApi'
import { modelName } from '../lib/format'
import { MAX_EXPERT_MODELS } from '../lib/constants'
import type { AdminSettings } from '../lib/types'

const props = defineProps<{ data: AdminSettings }>()
const emit = defineEmits<{ notify: [msg: string]; changed: [] }>()

const exp = computed(() => props.data.expert)
const key = ref('')
const models = ref<string[]>([...exp.value.models])
const baseUrl = ref(exp.value.base_url)
const newModel = ref('')
const busy = ref('')
const error = ref('')
const results = ref<CheckResult[] | null>(null)

const SUGGEST = [
  'google/gemini-2.5-flash',
  'google/gemini-2.5-pro',
  'anthropic/claude-haiku-4-5',
  'anthropic/claude-sonnet-5',
  'openai/gpt-5.4',
  'qwen/qwen3.8-flash',
]
const suggestions = computed(() => SUGGEST.filter((m) => !models.value.includes(m)))

const dirty = computed(
  () =>
    !!key.value ||
    baseUrl.value !== exp.value.base_url ||
    JSON.stringify(models.value) !== JSON.stringify(exp.value.models),
)

function addModel(m = newModel.value) {
  m = m.trim()
  if (!m || models.value.includes(m) || models.value.length >= MAX_EXPERT_MODELS) return
  models.value.push(m)
  newModel.value = ''
}

async function save(clearKey = false) {
  busy.value = 'save'
  error.value = ''
  try {
    await adminApi.saveExpert({
      api_key: clearKey ? '' : key.value || null,
      base_url: baseUrl.value,
      models: models.value,
    })
    key.value = ''
    results.value = null
    emit('changed')
    emit('notify', clearKey ? 'Ключ удалён' : 'Настройки сохранены')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = ''
  }
}

async function check() {
  busy.value = 'check'
  error.value = ''
  results.value = null
  try {
    results.value = (await adminApi.checkExpert()).results
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <div class="panel">
    <header class="ph">
      <div>
        <h1>Экспертный разбор</h1>
        <p>
          Оценка обложки языковыми моделями через ProxyAPI: что поймёт покупатель, доверие, читаемость надписей и какой
          вариант скорее выберут. Пока ключ не задан, эти блоки на сайте скрыты.
        </p>
      </div>
      <span class="status" :class="exp.has_key ? 'on' : ''">
        <i class="dot" :class="exp.has_key ? 'good' : ''" />
        {{ exp.has_key ? 'Подключено' : 'Не подключено' }}
      </span>
    </header>
    <p v-if="error" class="err">{{ error }}</p>

    <section class="card block">
      <h2 class="label">Ключ ProxyAPI</h2>
      <div class="keyrow">
        <input
          v-model="key"
          class="input"
          type="password"
          autocomplete="new-password"
          aria-label="Ключ ProxyAPI"
          :placeholder="
            exp.has_key
              ? `Сохранён ${exp.key_hint} — введите новый, чтобы заменить`
              : 'Вставьте ключ из личного кабинета ProxyAPI'
          "
        />
        <button v-if="exp.key_source === 'admin'" class="btn ghost" :disabled="!!busy" @click="save(true)">
          Удалить ключ
        </button>
      </div>
      <p class="note">
        Ключ хранится на вашем сервере и не показывается после сохранения.
        <template v-if="exp.key_source === 'env'"> Сейчас используется ключ из файла .env.</template>
        Получить ключ: <a href="https://console.proxyapi.ru" target="_blank" rel="noopener">console.proxyapi.ru</a>
      </p>
    </section>

    <section class="card block">
      <h2 class="label">Модели · {{ models.length }}/{{ MAX_EXPERT_MODELS }}</h2>
      <p class="note">Каждая модель даёт отдельное мнение, оценки усредняются. Больше моделей — точнее, но дороже.</p>
      <ul class="models">
        <li v-for="(m, i) in models" :key="m">
          <span>{{ modelName(m) }}</span>
          <code>{{ m }}</code>
          <button
            class="btn ghost sm icon"
            title="Убрать"
            :aria-label="`Убрать модель ${modelName(m)}`"
            @click="models.splice(i, 1)"
          >
            <X :size="14" />
          </button>
        </li>
      </ul>
      <div class="add">
        <input
          v-model="newModel"
          class="input"
          placeholder="vendor/model, например google/gemini-2.5-flash"
          aria-label="Идентификатор модели"
          @keydown.enter="addModel()"
        />
        <button class="btn" :disabled="!newModel.trim() || models.length >= MAX_EXPERT_MODELS" @click="addModel()">
          <Plus :size="14" /> Добавить
        </button>
      </div>
      <div v-if="suggestions.length && models.length < MAX_EXPERT_MODELS" class="sugg">
        <button v-for="s in suggestions" :key="s" class="pill" @click="addModel(s)">+ {{ modelName(s) }}</button>
      </div>
      <details class="adv">
        <summary>Дополнительно</summary>
        <label class="field">
          <span class="flabel">Адрес API (OpenAI-совместимый)</span>
          <input v-model="baseUrl" class="input" placeholder="https://api.proxyapi.ru/v1" />
        </label>
      </details>
    </section>

    <div class="save-row">
      <button class="btn primary" :disabled="!dirty || !!busy || !models.length" @click="save()">
        <Loader2 v-if="busy === 'save'" :size="15" class="spin" /><Check v-else :size="15" /> Сохранить
      </button>
      <button
        class="btn"
        :disabled="!!busy || !exp.has_key || dirty"
        :title="dirty ? 'Сначала сохраните изменения' : ''"
        @click="check"
      >
        <Loader2 v-if="busy === 'check'" :size="15" class="spin" /><Plug v-else :size="15" /> Проверить подключение
      </button>
    </div>

    <ul v-if="results" class="results rise">
      <li v-for="r in results" :key="r.model" :class="r.ok ? 'ok' : 'bad'">
        <i class="dot" :class="r.ok ? 'good' : 'bad'" />
        <strong>{{ modelName(r.model) }}</strong>
        <span>{{ r.message }}</span>
      </li>
    </ul>
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

.keyrow,
.add {
  display: flex;
  gap: 8px;
}

.keyrow .input,
.add .input {
  flex: 1;
  height: 38px;
}

.note {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--ink-3);
}

.note a {
  color: var(--ink);
}

.models {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
}

.models li {
  display: grid;
  grid-template-columns: 180px 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 6px 6px 6px 12px;
  border-radius: 8px;
  background: var(--bg);
  border: 1px solid var(--line);
  font-size: 13.5px;
  font-weight: 500;
}

code {
  font-size: 11.5px;
  color: var(--ink-3);
}

.sugg {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pill {
  height: 28px;
  padding: 0 10px;
  border-radius: 99px;
  border: 1px dashed var(--line-strong);
  background: none;
  font-size: 12px;
  color: var(--ink-2);
}

.pill:hover {
  border-style: solid;
  color: var(--ink);
}

.adv summary {
  cursor: pointer;
  font-size: 12.5px;
  color: var(--ink-3);
}

.adv .field {
  margin-top: 10px;
}

.save-row {
  display: flex;
  gap: 10px;
}

.results {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
}

.results li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
}

.results li.ok {
  background: var(--good-soft);
}

.results li.bad {
  background: var(--bad-soft);
}

.results span {
  color: var(--ink-2);
}
</style>
