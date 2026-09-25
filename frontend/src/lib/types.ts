export type Key = 'A' | 'B' | 'C' | 'D'
export const KEYS: Key[] = ['A', 'B', 'C', 'D']

export interface Grid {
  w: number
  h: number
  data: string // base64 uint8
}

export interface Fixation {
  x: number
  y: number
  mass: number
}

export interface Note {
  level: 'good' | 'warn' | 'bad'
  title: string
  text: string
}

export interface Scores {
  focus: number
  ease: number
  contrast: number
  thumb: number
}

export interface Analysis {
  id: string
  width: number
  height: number
  grid: Grid
  fixations: Fixation[]
  palette: { hex: string; share: number }[]
  index: number
  scores: Scores
  raw: {
    area50: number
    hotspots: number
    elements: number
    colors: number
    rms_contrast: number
    thumb_ssim: number
  }
  notes: Note[]
}

export interface Aoi {
  id: string
  label: string
  x: number
  y: number
  w: number
  h: number
}

export interface ExpertScore {
  mean: number
  min: number
  max: number
}

export interface Opinion {
  model: string
  offer?: string
  verdict?: string
  strengths?: string[]
  issues?: { severity: 'high' | 'medium' | 'low'; problem: string; fix: string }[]
  texts?: { text: string; legible_on_thumb: boolean }[]
}

export interface Critique {
  models: string[]
  /** id моделей, которые не ответили: разбор собран из остальных; в интерфейсе — только их число, без имён */
  errors: string[]
  scores: Partial<Record<'clarity' | 'trust' | 'premium' | 'emotion' | 'readability', ExpertScore>>
  price_guess: number | null
  opinions: Opinion[]
}

export interface CompareResult {
  /** id моделей, которые не ответили; в интерфейсе — только их число */
  errors: string[]
  /** chance — вероятность выбора в процентах (целые, в сумме 100) */
  ranking: { key: Key; strength: number; chance: number; wins: number; played: number }[]
  records: { model: string; shown: [Key, Key]; winner: Key; confidence: number; reason: string }[]
}

export interface Mosaic {
  image: string
  width: number
  height: number
  grid: Grid
  rects: { x: number; y: number; w: number; h: number }[]
  target: number | null
  order: Key[] | null
}

export interface ShelfResult {
  mode: 'competitors' | 'variants'
  layout: Layout
  results: Record<string, { share: number; fair: number; runs: number; distinct: number; stop_power: number }>
  mosaics: Record<string, Mosaic>
  timing: number
}

export type Status = 'idle' | 'loading' | 'ready' | 'error'

export interface Variant {
  key: Key
  file: File
  url: string
  name: string
  status: Status
  error?: string
  analysis?: Analysis
  aois: Aoi[]
  critique?: Critique
  critiqueStatus: Status
  critiqueError?: string
  /** улучшенная обложка (data URL), которую нарисовала нейросеть по выводам разбора */
  improved?: string
  improveStatus: Status
  improveError?: string
  /** когда запустили генерацию — индикатор не начинается заново при переключении вариантов */
  improveStartedAt?: number
}

export interface Health {
  ok: boolean
  version: string
  /** работает ли нейросеть внимания; false — классический движок */
  neural: boolean
  expert: { enabled: boolean; models: string[] }
  /** какие платные функции доступны на сервере: выключенные интерфейс прячет */
  features?: { improve: boolean; competitors: boolean; billing: boolean }
}

// ------------------------------------------------------------ аккаунт и подписка

export type Feature = 'expert' | 'improve' | 'competitors'
export type FeatureLimits = Record<Feature, number>
export type Plan = 'free' | 'pro'

export interface User {
  email: string
  plan: Plan
  /** до какого момента действует Pro, unix-секунды */
  pro_until: number | null
  /** запуски за сегодня и дневные лимиты тарифа */
  usage: FeatureLimits
  limits: FeatureLimits
}

export interface Session {
  token: string
  user: User
}

/** Условия подписки: /api/billing/plan и раздел «Подписка» в админке. */
export interface BillingPlan {
  /** подключена ли оплата (ключи ЮKassa заданы на сервере) */
  enabled: boolean
  price_rub: number
  period_days: number
  limits: Record<Plan, FeatureLimits>
}

export interface CompetitorItem {
  id: string
  brand: string
  name: string
  /** картинка на нашем сервере — тот же адрес, без обращения к маркетплейсу из браузера */
  url: string
}

export interface CompetitorSearch {
  query: string
  items: CompetitorItem[]
}

export type OverlayMode = 'original' | 'heat' | 'fog' | 'contours' | 'gaze'
export type View = 'analyze' | 'compare' | 'shelf'
export type Layout = 'mobile' | 'desktop'

// ------------------------------------------------------------ сайт, примеры, админка

export type Design = 'editorial' | 'split' | 'feed'

export interface Landing {
  design: Design
  eyebrow: string
  title: string
  title_muted: string
  lead: string
  cta: string
  steps: { title: string; text: string }[]
}

export interface ExampleImage {
  id: string
  title: string
  width: number
  height: number
  /** адрес картинки — сервер отдаёт его и в публичных данных, и в админке */
  url: string
}

export interface ProductContext {
  query: string
  category: string
  price: string
  audience: string
}

export interface Example {
  id: string
  title: string
  description: string
  context: ProductContext
  published?: boolean
  hero?: string | null
  variants: ExampleImage[]
  competitors: ExampleImage[]
}

export interface Site {
  landing: Landing
  examples: Example[]
}

/** Заранее посчитанные результаты примера (backend/app/services/precompute.py). */
export type ExampleResults =
  | { ready: false }
  | {
      ready: true
      /** в какой слот открывается каждая обложка примера: A → id картинки */
      keys: Partial<Record<Key, string>>
      /** разбор каждой обложки по id картинки — с id загрузки, как у обычного анализа */
      variants: Record<string, Analysis>
      /** тест полки с конкурентами примера для каждой раскладки */
      shelf: Partial<Record<Layout, ShelfResult>>
    }

export interface Showcase {
  example: string
  card: {
    url: string
    title: string
    width: number
    height: number
    grid: Grid
    fixations: Fixation[]
    index: number
    scores: Scores
    area50: number
  }
  feed: {
    tiles: { url: string; x: number; y: number; w: number; h: number }[]
    width: number
    height: number
    grid: Grid
    target: number
    share: number
    fair: number
  }
}

export interface ExpertSettings {
  has_key: boolean
  key_hint: string
  key_source: '' | 'admin' | 'env'
  base_url: string
  models: string[]
}

export interface AdminSettings {
  landing: Landing
  examples: Example[]
  expert: ExpertSettings
  designs: Design[]
  billing: BillingPlan
}
