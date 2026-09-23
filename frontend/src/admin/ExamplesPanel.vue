<script setup lang="ts">
import { computed, ref, toRaw, watch } from 'vue'
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Check,
  ImagePlus,
  Loader2,
  Plus,
  Star,
  Trash2,
} from 'lucide-vue-next'
import { adminApi } from './adminApi'
import { MAX_COMPETITORS, MAX_VARIANTS } from '../lib/constants'
import { useFilePicker } from '../lib/useFilePicker'
import { IMAGE_HINT, isImage } from '../lib/files'
import type { AdminSettings, Example, ExampleImage } from '../lib/types'

const props = defineProps<{ data: AdminSettings }>()
const emit = defineEmits<{ changed: []; notify: [msg: string] }>()

type Role = 'variants' | 'competitors'
const ROLES: Role[] = ['variants', 'competitors']
const LIMIT: Record<Role, number> = { variants: MAX_VARIANTS, competitors: MAX_COMPETITORS }

const examples = computed(() => props.data.examples)
const selectedId = ref<string | null>(examples.value[0]?.id ?? null)
const current = computed(() => examples.value.find((e) => e.id === selectedId.value) ?? null)

// новый пример попадает в список только после перезагрузки данных — выбираем его, когда он придёт,
// иначе редактор на мгновение опустеет
let pendingId: string | null = null
watch(examples, (list) => {
  if (pendingId && list.some((e) => e.id === pendingId)) {
    selectedId.value = pendingId
    pendingId = null
  }
})

// форма метаданных — отдельная копия, чтобы видеть несохранённые изменения;
// картинки и обложка витрины сохраняются сразу и в сравнение не входят
const form = ref<Example | null>(null)
const snapshot = ref('')
const meta = (e: Example | null) =>
  e && { title: e.title, description: e.description, context: e.context, published: e.published }
const dirty = computed(() => !!form.value && JSON.stringify(meta(form.value)) !== snapshot.value)

function reset() {
  // structuredClone не умеет Proxy — копируем исходный объект за реактивной обёрткой
  form.value = current.value ? structuredClone(toRaw(current.value)) : null
  snapshot.value = JSON.stringify(meta(form.value))
}

watch(
  current,
  (c, old) => {
    // при перезагрузке данных не затираем несохранённые правки текущего примера
    if (!old || c?.id !== old.id || !dirty.value) reset()
    else if (form.value && c) {
      form.value.variants = c.variants
      form.value.competitors = c.competitors
    }
  },
  { immediate: true },
)

const busy = ref('')
const error = ref('')

/** Одна операция за раз: параллельные переименования и перестановки гонялись бы за порядком. */
async function run(label: string, fn: () => Promise<unknown>, done?: string): Promise<boolean> {
  if (busy.value) return false
  busy.value = label
  error.value = ''
  try {
    await fn()
    emit('changed')
    if (done) emit('notify', done)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = ''
  }
  return true
}

function create() {
  run(
    'create',
    async () => {
      pendingId = (await adminApi.createExample('Новый пример')).id
    },
    'Пример создан',
  )
}

function saveMeta() {
  const ex = form.value
  const saved = current.value
  if (!ex || !saved) return
  // обложку витрины берём с сервера: её меняют отдельно, без кнопки «Сохранить»
  run(
    'save',
    async () => {
      await adminApi.saveExample({ ...ex, hero: saved.hero ?? null })
      snapshot.value = JSON.stringify(meta(ex))
    },
    'Пример сохранён',
  )
}

function remove() {
  const ex = current.value
  if (!ex || !confirm(`Удалить пример «${ex.title || 'Без названия'}» со всеми картинками? Это нельзя отменить.`))
    return
  run(
    'delete',
    async () => {
      await adminApi.deleteExample(ex.id)
      selectedId.value = examples.value.find((e) => e.id !== ex.id)?.id ?? null
    },
    'Пример удалён',
  )
}

function move(i: number, d: number) {
  const ids = examples.value.map((e) => e.id)
  const j = i + d
  if (j < 0 || j >= ids.length) return
  ;[ids[i], ids[j]] = [ids[j], ids[i]]
  run('order', () => adminApi.orderExamples(ids))
}

// ------------------------------------------------------------ картинки
const over = ref<Role | ''>('')
const pickers: Record<Role, ReturnType<typeof useFilePicker>> = {
  variants: useFilePicker((files) => upload('variants', files)),
  competitors: useFilePicker((files) => upload('competitors', files)),
}

function upload(role: Role, files: File[]) {
  const ex = current.value
  if (!ex || !files.length) return
  const list = files.filter(isImage)
  if (list.length < files.length) emit('notify', IMAGE_HINT)
  if (!list.length) return
  const room = LIMIT[role] - ex[role].length
  if (room <= 0) {
    emit('notify', `Максимум ${LIMIT[role]} ${role === 'variants' ? 'варианта' : 'конкурентов'}`)
    return
  }
  run(`up-${role}`, () => adminApi.upload(ex.id, role, list.slice(0, room)), 'Картинки загружены')
}

function onDrop(role: Role, e: DragEvent) {
  over.value = ''
  upload(role, Array.from(e.dataTransfer?.files ?? []))
}

async function rename(img: ExampleImage, e: Event) {
  const input = e.target as HTMLInputElement
  const ex = current.value
  if (!ex) return
  const started = await run('rename', () => adminApi.renameImage(ex.id, img.id, input.value))
  if (!started) {
    input.value = img.title
    emit('notify', 'Подпись не сохранена: дождитесь окончания предыдущей операции')
  }
}

function delImage(img: ExampleImage) {
  const ex = current.value
  if (!ex || !confirm(`Удалить картинку${img.title ? ` «${img.title}»` : ''}? Это нельзя отменить.`)) return
  run('delimg', () => adminApi.deleteImage(ex.id, img.id), 'Картинка удалена')
}

function shift(role: Role, i: number, d: number) {
  const ex = current.value
  if (!ex) return
  const ids = ex[role].map((x) => x.id)
  const j = i + d
  if (j < 0 || j >= ids.length) return
  ;[ids[i], ids[j]] = [ids[j], ids[i]]
  run('imgorder', () => adminApi.orderImages(ex.id, role, ids))
}

// Обложка витрины сохраняется сразу, как и остальные операции с картинками.
// hero = null — сервер показывает в витрине первый вариант, поэтому звезда горит на нём.
const isHero = (ex: Example, img: ExampleImage, i: number) => ex.hero === img.id || (!ex.hero && i === 0)

function setHero(img: ExampleImage) {
  const ex = current.value
  if (!ex) return
  const hero = ex.hero === img.id ? null : img.id
  run('hero', () => adminApi.saveExample({ ...ex, hero }), 'Обложка для витрины выбрана')
}

const isFirstPublished = computed(
  () => examples.value.find((e) => e.published && e.variants.length)?.id === current.value?.id,
)
</script>

<template>
  <div class="panel">
    <header class="ph">
      <div>
        <h1>Примеры</h1>
        <p>
          Наборы обложек, которые посетитель открывает одним кликом на главной. Первый опубликованный пример
          показывается в витрине главной страницы.
        </p>
      </div>
      <button class="btn primary" :disabled="!!busy" @click="create"><Plus :size="15" /> Новый пример</button>
    </header>
    <p v-if="error" class="err">{{ error }}</p>

    <div class="layout">
      <ul class="list">
        <li v-for="(ex, i) in examples" :key="ex.id" :class="{ on: ex.id === selectedId }">
          <button class="pick" :aria-current="ex.id === selectedId ? 'true' : undefined" @click="selectedId = ex.id">
            <span class="cover">
              <img v-if="ex.variants[0]" :src="ex.variants[0].url" alt="" />
            </span>
            <span class="li-meta">
              <strong>{{ ex.title || 'Без названия' }}</strong>
              <span class="num">
                <i class="dot" :class="ex.published ? 'good' : ''" />
                {{ ex.published ? 'на сайте' : 'скрыт' }} · {{ ex.variants.length }}+{{ ex.competitors.length }}
              </span>
            </span>
          </button>
          <div class="updown">
            <button
              class="btn ghost sm icon"
              :disabled="i === 0 || !!busy"
              title="Выше"
              aria-label="Переместить пример выше"
              @click="move(i, -1)"
            >
              <ArrowUp :size="13" />
            </button>
            <button
              class="btn ghost sm icon"
              :disabled="i === examples.length - 1 || !!busy"
              title="Ниже"
              aria-label="Переместить пример ниже"
              @click="move(i, 1)"
            >
              <ArrowDown :size="13" />
            </button>
          </div>
        </li>
        <li v-if="!examples.length" class="empty">Примеров пока нет — создайте первый.</li>
      </ul>

      <section v-if="form && current" class="editor card">
        <div class="ed-head">
          <input
            v-model="form.title"
            class="title-input"
            maxlength="80"
            placeholder="Название примера"
            aria-label="Название примера"
          />
          <label class="switch">
            <input v-model="form.published" type="checkbox" />
            <span class="track"><i /></span>
            {{ form.published ? 'Показывать на сайте' : 'Скрыт' }}
          </label>
        </div>

        <label class="field">
          <span class="flabel">Описание</span>
          <textarea v-model="form.description" class="input area" rows="2" maxlength="300" />
        </label>

        <div class="ctx">
          <label class="field">
            <span class="flabel">Поисковый запрос</span
            ><input v-model="form.context.query" class="input" maxlength="120" />
          </label>
          <label class="field">
            <span class="flabel">Категория</span><input v-model="form.context.category" class="input" maxlength="80" />
          </label>
          <label class="field">
            <span class="flabel">Цена, ₽</span><input v-model="form.context.price" class="input" maxlength="20" />
          </label>
          <label class="field">
            <span class="flabel">Аудитория</span><input v-model="form.context.audience" class="input" maxlength="80" />
          </label>
        </div>

        <div class="save-row">
          <button class="btn primary" :disabled="!dirty || !!busy" @click="saveMeta">
            <Loader2 v-if="busy === 'save'" :size="15" class="spin" /><Check v-else :size="15" /> Сохранить
          </button>
          <span v-if="dirty" class="dirty num">есть несохранённые изменения</span>
          <button class="btn ghost danger" :disabled="!!busy" @click="remove">
            <Trash2 :size="15" /> Удалить пример
          </button>
        </div>

        <template v-for="role in ROLES" :key="role">
          <div class="imgs-head">
            <h2 class="label">
              {{ role === 'variants' ? 'Варианты обложки' : 'Конкуренты в выдаче' }}
              · {{ current[role].length }}/{{ LIMIT[role] }}
            </h2>
            <span v-if="role === 'variants' && isFirstPublished" class="hint num">
              <Star :size="12" /> — карточка для витрины на главной
            </span>
          </div>
          <div
            class="imgs"
            :class="{ over: over === role, small: role === 'competitors' }"
            @dragover.prevent="over = role"
            @dragleave="over = ''"
            @drop.prevent="onDrop(role, $event)"
          >
            <figure v-for="(img, i) in current[role]" :key="img.id" class="img">
              <div class="thumb">
                <img :src="img.url" alt="" loading="lazy" />
                <button
                  v-if="role === 'variants'"
                  class="star"
                  :class="{ on: isHero(current, img, i) }"
                  :disabled="!!busy"
                  title="Показывать в витрине главной"
                  aria-label="Показывать в витрине главной"
                  :aria-pressed="isHero(current, img, i)"
                  @click="setHero(img)"
                >
                  <Star :size="13" />
                </button>
                <div class="tools">
                  <button
                    title="Левее"
                    aria-label="Сдвинуть левее"
                    :disabled="i === 0 || !!busy"
                    @click="shift(role, i, -1)"
                  >
                    <ArrowLeft :size="13" />
                  </button>
                  <button
                    title="Правее"
                    aria-label="Сдвинуть правее"
                    :disabled="i === current[role].length - 1 || !!busy"
                    @click="shift(role, i, 1)"
                  >
                    <ArrowRight :size="13" />
                  </button>
                  <button title="Удалить" aria-label="Удалить картинку" :disabled="!!busy" @click="delImage(img)">
                    <Trash2 :size="13" />
                  </button>
                </div>
              </div>
              <input
                v-if="role === 'variants'"
                :value="img.title"
                class="cap"
                maxlength="60"
                placeholder="Подпись"
                :aria-label="`Подпись варианта ${i + 1}`"
                @change="rename(img, $event)"
              />
            </figure>
            <button
              v-if="current[role].length < LIMIT[role]"
              class="add"
              :disabled="busy === `up-${role}`"
              @click="pickers[role]()"
            >
              <Loader2 v-if="busy === `up-${role}`" :size="18" class="spin" />
              <ImagePlus v-else :size="18" />
              <span>{{ busy === `up-${role}` ? 'Загружаю…' : 'Добавить' }}</span>
              <small>или перетащите сюда</small>
            </button>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
@import './panel.css';

.layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
}

.list li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding-right: 7px;
  border-radius: 10px;
  border: 1px solid transparent;
}

.list li:hover {
  background: var(--panel-2);
}

.list li.on {
  background: var(--panel);
  border-color: var(--line-strong);
}

.list li.empty {
  display: block;
  padding: 7px;
  font-size: 13px;
  color: var(--ink-3);
}

/* кнопка выбора занимает всю строку, кроме стрелок */
.pick {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 7px 0 7px 7px;
  border: 0;
  border-radius: 10px;
  background: none;
  text-align: left;
}

.pick:focus-visible {
  outline-offset: -2px;
}

.cover {
  display: block;
  width: 40px;
  height: 52px;
  border-radius: 6px;
  overflow: hidden;
  background: var(--sunken);
}

.cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.li-meta {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.li-meta strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13.5px;
  font-weight: 600;
}

.li-meta span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 10.5px;
  color: var(--ink-3);
}

.updown {
  display: grid;
  opacity: 0;
  transition: opacity 0.15s;
}

.list li:hover .updown,
.list li:focus-within .updown {
  opacity: 1;
}

.editor {
  display: grid;
  gap: 16px;
  padding: 22px;
}

.ed-head {
  display: flex;
  align-items: center;
  gap: 16px;
}

.title-input {
  flex: 1;
  min-width: 0;
  height: 44px;
  padding: 0 10px;
  margin-left: -10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  font-size: 22px;
  font-weight: 300;
  letter-spacing: -0.02em;
}

.title-input:hover,
.title-input:focus {
  border-color: var(--line);
  background: var(--bg);
  outline: none;
}

.switch {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--ink-2);
  cursor: pointer;
  white-space: nowrap;
}

.switch input {
  position: absolute;
  opacity: 0;
}

.track {
  position: relative;
  width: 36px;
  height: 20px;
  border-radius: 10px;
  background: var(--line-strong);
  transition: background 0.15s;
}

.track i {
  position: absolute;
  left: 2px;
  top: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.15s;
}

.switch input:checked + .track {
  background: var(--good);
}

.switch input:checked + .track i {
  transform: translateX(16px);
}

.switch input:focus-visible + .track {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.ctx {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.save-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line);
}

.danger {
  margin-left: auto;
  color: var(--bad);
}

.imgs-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-top: 8px;
}

.imgs-head h2 {
  margin: 0;
}

.hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--ink-3);
}

.imgs {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  padding: 10px;
  margin: -10px;
  border-radius: 12px;
  border: 1.5px dashed transparent;
  transition:
    border-color 0.15s,
    background 0.15s;
}

.imgs.small {
  grid-template-columns: repeat(auto-fill, minmax(104px, 1fr));
}

.imgs.over {
  border-color: var(--ink);
  background: var(--panel-2);
}

.img {
  margin: 0;
  display: grid;
  gap: 6px;
}

.thumb {
  position: relative;
  aspect-ratio: 3 / 4;
  border-radius: 8px;
  overflow: hidden;
  background: var(--sunken);
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.star {
  position: absolute;
  left: 6px;
  top: 6px;
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
}

.star.on {
  background: var(--accent);
}

.tools {
  position: absolute;
  left: 6px;
  right: 6px;
  bottom: 6px;
  display: flex;
  justify-content: space-between;
  padding: 3px;
  border-radius: 8px;
  background: rgba(14, 14, 12, 0.72);
  backdrop-filter: blur(6px);
  opacity: 0;
  transition: opacity 0.15s;
}

.thumb:hover .tools,
.thumb:focus-within .tools {
  opacity: 1;
}

.tools button {
  display: grid;
  place-items: center;
  width: 28px;
  height: 26px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: none;
  color: #fff;
}

.tools button:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.15);
}

.tools button:disabled {
  opacity: 0.3;
}

.cap {
  height: 30px;
  padding: 0 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  font-size: 12.5px;
}

.cap:hover,
.cap:focus {
  border-color: var(--line);
  background: var(--bg);
  outline: none;
}

.add {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 6px;
  aspect-ratio: 3 / 4;
  border: 1.5px dashed var(--line-strong);
  border-radius: 8px;
  background: transparent;
  color: var(--ink-2);
  font-size: 13px;
}

.add small {
  font-size: 10.5px;
  color: var(--ink-3);
}

.add:hover {
  border-color: var(--ink-3);
  color: var(--ink);
  background: var(--bg);
}

@media (max-width: 1000px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .ctx {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
