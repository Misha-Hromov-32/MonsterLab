import { computed, reactive, watch } from 'vue'
import { api, ApiError } from './api'
import { MAX_COMPETITORS, MAX_VARIANTS, TOAST_MS } from './lib/constants'
import { IMAGE_HINT, isImage } from './lib/files'
import { KEYS } from './lib/types'
import type {
  ExampleResults,
  Analysis,
  CompareResult,
  Example,
  Health,
  Key,
  Layout,
  OverlayMode,
  Showcase,
  ShelfResult,
  Site,
  Status,
  Variant,
  View,
} from './lib/types'

// ------------------------------------------------------------ настройки пользователя

function loadPrefs<T extends object>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback
  } catch {
    return fallback
  }
}

function savePrefs(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* приватный режим — настройки живут до перезагрузки */
  }
}

const prefs = loadPrefs('ml.prefs', {
  mode: 'heat' as OverlayMode,
  opacity: 0.8,
  context: { category: '', query: '', price: '', audience: '' },
  layout: 'mobile' as Layout,
})

export const state = reactive({
  health: null as Health | null,
  healthError: '',
  variants: [] as Variant[],
  selected: null as Key | null,
  view: 'analyze' as View,
  mode: prefs.mode,
  opacity: prefs.opacity,
  context: prefs.context,
  layout: prefs.layout,
  compare: null as CompareResult | null,
  compareStatus: 'idle' as Status,
  compareError: '',
  shelf: null as ShelfResult | null,
  shelfStatus: 'idle' as Status,
  shelfError: '',
  /** когда запустили тест полки — индикатор не начинается заново при возврате на вкладку */
  shelfStartedAt: 0,
  competitors: [] as { file: File; url: string }[],
  toast: '',
})

watch(
  () => ({ mode: state.mode, opacity: state.opacity, context: state.context, layout: state.layout }),
  (v) => savePrefs('ml.prefs', v),
  { deep: true },
)

export const current = computed(() => state.variants.find((v) => v.key === state.selected) ?? null)
export const ready = computed(() => state.variants.filter((v) => v.status === 'ready' && v.analysis))
// С результатом анализа — даже если прямо сейчас картинка перезагружается на сервер (image_expired):
// от этого числа зависит, остаётся ли открытой вкладка сравнения или полки.
const analyzed = computed(() => state.variants.filter((v) => v.analysis))
export const freeKeys = computed(() => KEYS.filter((k) => !state.variants.some((v) => v.key === k)))
export const expertEnabled = computed(() => !!state.health?.expert.enabled)

// Вкладка стала недоступной (удалили вариант, разбор ещё идёт) — возвращаем на «Разбор»,
// иначе экран остался бы открыт при выключенной кнопке. Условия те же, что у вкладок в TopBar.
watch(
  () => (state.view === 'compare' && analyzed.value.length < 2) || (state.view === 'shelf' && !analyzed.value.length),
  (unavailable) => {
    if (unavailable) state.view = 'analyze'
  },
)

const EXPERT_FAIL = 'Не удалось получить экспертный разбор. Попробуйте ещё раз через минуту.'

let toastTimer = 0
export function toast(msg: string) {
  state.toast = msg
  clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => (state.toast = ''), TOAST_MS)
}

// После перезапуска сервер ~10–20 секунд загружает нейросеть — тихо повторяем, прежде чем пугать ошибкой.
const HEALTH_RETRIES = 20
const HEALTH_RETRY_MS = 3000
const HEALTH_SILENT_RETRIES = 4

export async function loadHealth(attempt = 0): Promise<void> {
  try {
    state.health = await api.health()
    state.healthError = ''
    if (attempt > 0) loadSite()
  } catch (e) {
    if (attempt < HEALTH_RETRIES) {
      setTimeout(() => loadHealth(attempt + 1), HEALTH_RETRY_MS)
      if (attempt >= HEALTH_SILENT_RETRIES) state.healthError = (e as Error).message
    } else state.healthError = (e as Error).message
  }
}

// ------------------------------------------------------------ варианты

/** Отмена текущего анализа по варианту: при замене и удалении старый ответ уже не нужен. */
const inflight = new Map<Key, AbortController>()

function newVariant(key: Key, file: File): Variant {
  return reactive({
    key,
    file,
    url: URL.createObjectURL(file),
    name: file.name,
    status: 'idle',
    aois: [],
    critiqueStatus: 'idle',
  }) as Variant
}

/**
 * Добавляет обложки в свободные слоты. analyses — готовый разбор для каждой (у примеров он
 * посчитан заранее): тогда картинка на сервер не отправляется.
 */
export function addFiles(files: FileList | File[], target?: Key, analyses?: (Analysis | undefined)[]) {
  const list = Array.from(files).filter(isImage)
  if (!list.length) {
    toast(IMAGE_HINT)
    return
  }
  if (target) {
    replaceVariant(target, list[0])
    return
  }
  const keys = freeKeys.value
  if (!keys.length) {
    toast('Все четыре слота заняты — удалите вариант или замените его')
    return
  }
  if (list.length > keys.length) toast(`Добавлено ${keys.length} из ${list.length}: максимум ${MAX_VARIANTS} варианта`)
  list.slice(0, keys.length).forEach((file, i) => {
    const v = newVariant(keys[i], file)
    state.variants.push(v)
    if (!state.selected || i === 0) state.selected = v.key
    const ready = analyses?.[i]
    if (ready) Object.assign(v, { analysis: ready, status: 'ready' })
    else analyze(v)
  })
  state.variants.sort((a, b) => a.key.localeCompare(b.key))
  invalidateComparisons()
}

function replaceVariant(key: Key, file: File) {
  const v = state.variants.find((x) => x.key === key)
  if (!v) return addFiles([file])
  URL.revokeObjectURL(v.url)
  Object.assign(v, {
    file,
    url: URL.createObjectURL(file),
    name: file.name,
    analysis: undefined,
    critique: undefined,
    critiqueStatus: 'idle',
    critiqueError: undefined,
    aois: [],
  })
  analyze(v)
  invalidateComparisons()
}

export function removeVariant(key: Key) {
  const i = state.variants.findIndex((v) => v.key === key)
  if (i < 0) return
  inflight.get(key)?.abort()
  URL.revokeObjectURL(state.variants[i].url)
  state.variants.splice(i, 1)
  if (state.selected === key) state.selected = state.variants[0]?.key ?? null
  invalidateComparisons()
}

/** «Новый анализ»: сбрасывает варианты, конкурентов и результаты — возвращает на главную. */
export function resetAll() {
  inflight.forEach((c) => c.abort())
  state.variants.forEach((v) => URL.revokeObjectURL(v.url))
  state.competitors.forEach((c) => URL.revokeObjectURL(c.url))
  state.variants.splice(0)
  state.competitors.splice(0)
  state.selected = null
  state.view = 'analyze'
  invalidateComparisons()
}

// Поколения входных данных: сравнение и полка, запущенные до изменения, по возвращении
// видят другое поколение и свой устаревший результат не записывают. Счётчики раздельные:
// смена конкурентов или раскладки не должна «терять» идущее сравнение.
let compareGen = 0
let shelfGen = 0

function invalidateComparisons() {
  compareGen++
  state.compare = null
  state.compareStatus = 'idle'
  invalidateShelf()
}

/** Сообщение об ошибке разбора: понятную причину от сервера (например, слишком длинные данные) показываем как есть. */
function expertError(e: unknown) {
  return e instanceof ApiError && e.code === 'bad_request' ? e.message : EXPERT_FAIL
}

export async function analyze(v: Variant) {
  inflight.get(v.key)?.abort()
  const ctrl = new AbortController()
  inflight.set(v.key, ctrl)
  const file = v.file
  v.status = 'loading'
  v.error = undefined
  try {
    const analysis = await api.analyze(file, ctrl.signal)
    if (v.file !== file) return // пока считали, картинку заменили
    v.analysis = analysis
    v.status = 'ready'
  } catch (e) {
    if (ctrl.signal.aborted || v.file !== file) return
    v.status = 'error'
    v.error = (e as Error).message
  } finally {
    if (inflight.get(v.key) === ctrl) inflight.delete(v.key)
  }
}

/** Выполняет запрос с id картинок на сервере; если сервер их «забыл» (перезапуск) — загружает заново. */
async function withIds<T>(vs: Variant[], fn: (ids: Record<string, string>) => Promise<T>): Promise<T> {
  const ids = () => Object.fromEntries(vs.map((v) => [v.key, v.analysis?.id ?? '']))
  try {
    return await fn(ids())
  } catch (e) {
    if (!(e instanceof ApiError && e.code === 'image_expired')) throw e
    await Promise.all(vs.map((v) => analyze(v)))
    if (vs.some((v) => v.status !== 'ready')) throw e
    return fn(ids())
  }
}

// ------------------------------------------------------------ экспертный разбор и полка

export async function runCritique(v: Variant) {
  if (!v.analysis) return
  const file = v.file
  v.critiqueStatus = 'loading'
  v.critiqueError = undefined
  try {
    const critique = await withIds([v], (ids) => api.critique(ids[v.key], state.context))
    if (v.file !== file) return
    v.critique = critique
    v.critiqueStatus = 'ready'
  } catch (e) {
    if (v.file !== file) return
    v.critiqueStatus = 'error'
    v.critiqueError = expertError(e)
  }
}

export async function runCompare() {
  const vs = ready.value
  if (vs.length < 2) return
  const gen = compareGen
  state.compareStatus = 'loading'
  state.compareError = ''
  try {
    const result = await withIds(vs, (ids) => api.compare(ids, state.context))
    if (gen !== compareGen) return
    state.compare = result
    state.compareStatus = 'ready'
  } catch (e) {
    if (gen !== compareGen) return
    state.compareStatus = 'error'
    state.compareError = expertError(e)
  }
}

export async function runShelf() {
  const vs = ready.value
  if (!vs.length) return
  const gen = shelfGen
  const cached = exampleShelf?.gen === gen ? exampleShelf.results[state.layout] : undefined
  if (cached) {
    state.shelf = cached
    state.shelfStatus = 'ready'
    return
  }
  state.shelfStatus = 'loading'
  state.shelfError = ''
  state.shelfStartedAt = Date.now()
  try {
    const competitors = state.competitors.map((c) => c.file)
    const result = await withIds(vs, (ids) => api.shelf(ids, competitors, state.layout))
    if (gen !== shelfGen) return
    state.shelf = result
    state.shelfStatus = 'ready'
  } catch (e) {
    if (gen !== shelfGen) return
    state.shelfStatus = 'error'
    state.shelfError = (e as Error).message
  }
}

// Готовый тест полки для только что открытого примера: действует, пока набор вариантов,
// конкурентов и раскладок не менялся (поколение полки то же, что сразу после открытия).
let exampleShelf: { gen: number; results: Partial<Record<Layout, ShelfResult>> } | null = null

function invalidateShelf() {
  shelfGen++
  state.shelf = null
  state.shelfStatus = 'idle'
}

export function addCompetitors(files: FileList | File[]) {
  const list = Array.from(files).filter(isImage)
  if (!list.length) {
    toast(IMAGE_HINT)
    return
  }
  const room = MAX_COMPETITORS - state.competitors.length
  if (room <= 0) {
    toast(`Уже добавлено ${MAX_COMPETITORS} конкурентов — удалите лишних, чтобы добавить новых`)
    return
  }
  if (list.length > room) toast(`Добавлено ${room} из ${list.length}: максимум ${MAX_COMPETITORS} конкурентов`)
  list.slice(0, room).forEach((file) => state.competitors.push({ file, url: URL.createObjectURL(file) }))
  invalidateShelf()
}

export function removeCompetitor(i: number) {
  URL.revokeObjectURL(state.competitors[i].url)
  state.competitors.splice(i, 1)
  invalidateShelf()
}

// ------------------------------------------------------------ сайт и примеры

export const site = reactive({ data: null as Site | null, showcase: null as Showcase | null, loaded: false })

/** Пример, который показываем первым: тот же, что посчитан для витрины главной. */
export const featuredExample = computed<Example | null>(() => {
  const examples = site.data?.examples ?? []
  return examples.find((e) => e.id === site.showcase?.example) ?? examples[0] ?? null
})

export async function loadSite() {
  try {
    site.data = await api.site()
  } catch {
    /* главная покажет тексты по умолчанию */
  } finally {
    site.loaded = true
  }
  loadShowcase()
}

// Витрину сервер считает в фоне после старта; пока её нет — заглядываем ещё несколько раз.
const SHOWCASE_RETRIES = 10
const SHOWCASE_RETRY_MS = 20_000

function loadShowcase(attempt = 0) {
  api
    .showcase()
    .then((s) => {
      site.showcase = s
      if (!s && site.data?.examples.length && attempt < SHOWCASE_RETRIES)
        setTimeout(() => loadShowcase(attempt + 1), SHOWCASE_RETRY_MS)
    })
    .catch(() => {})
}

async function exampleFile(url: string, name: string) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(url)
  const blob = await res.blob()
  return new File([blob], name, { type: blob.type || 'image/jpeg' })
}

/** Пример уже загружается — повторные нажатия не дублируют варианты. */
let exampleBusy = false

/** Открывает опубликованный пример: варианты в свободные слоты, конкуренты и данные о товаре. */
export async function loadExample(ex: Example) {
  if (exampleBusy) return
  const slots = freeKeys.value.length
  if (!slots) {
    toast('Все четыре слота заняты — начните новый анализ, чтобы открыть пример')
    return
  }
  exampleBusy = true
  // на чистый экран пример открывается целиком — тогда пригодится и готовый тест полки
  const fresh = !state.variants.length && !state.competitors.length
  try {
    const [variants, comps, results] = await Promise.all([
      Promise.all(
        ex.variants.slice(0, slots).map((v, i) => exampleFile(v.url, `${v.title || `Вариант ${i + 1}`}.jpg`)),
      ),
      state.competitors.length
        ? Promise.resolve([])
        : Promise.all(ex.competitors.map((c, i) => exampleFile(c.url, `Конкурент ${i + 1}.jpg`))),
      // готовые результаты — приятный бонус: не пришли, значит посчитаем как обычную загрузку
      Promise.resolve()
        .then(() => api.exampleResults(ex.id))
        .catch((): ExampleResults => ({ ready: false })),
    ])
    // данные о товаре подставляем, только если пользователь ничего не заполнил сам
    if (!Object.values(state.context).some(Boolean)) Object.assign(state.context, ex.context)
    const analyses = results.ready ? ex.variants.slice(0, slots).map((v) => results.variants[v.id]) : undefined
    addFiles(variants, undefined, analyses)
    if (comps.length) addCompetitors(comps)
    exampleShelf = fresh && results.ready ? { gen: shelfGen, results: results.shelf } : null
  } catch {
    toast('Не удалось открыть пример')
  } finally {
    exampleBusy = false
  }
}
