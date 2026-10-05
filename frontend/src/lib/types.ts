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
  generated_baseline?: number | null
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

export type CritiqueScore = 'aesthetics' | 'offer' | 'positioning' | 'standout' | 'trust'
export type MessageRole = 'оффер' | 'факт' | 'статус' | 'бренд' | 'призыв' | 'шум'

/** Визуальный разбор «как арт-директор» (POST /api/expert/critique), оценки — 1–10. */
export interface Critique {
  model: string
  /** модели, которые не ответили до той, что дала разбор; в интерфейсе не показываются */
  errors: string[]
  /** сколько конкурентов модель видела рядом с обложкой */
  rivals: number
  overall: number | null
  verdict: string
  impression: string
  reads_as: { segment: string; audience: string; mood: string }
  positioning: string
  style: string
  messages: { text: string; role: MessageRole; works: boolean; comment: string }[]
  reading_order: string
  shelf: string
  strengths: string[]
  improvements: { priority: number; what: string; why: string; how: string }[]
  scores: Partial<Record<CritiqueScore, number>>
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
  /** Искусственный бонус для сгенерированного варианта; реальная оценка хранится отдельно. */
  generatedBaseline?: number
  measuredIndex?: number
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

export interface SavedCover {
  id: string
  name: string
  kind: string
  preview: string
  created_at: number
}

export interface SavedCoverDetail {
  id: string
  name: string
  image: string
  analysis: Analysis | null
  generated_baseline: number | null
}

export interface Health {
  ok: boolean
  version: string
  /** работает ли нейросеть внимания; false — классический движок */
  neural: boolean
  expert: { enabled: boolean; models: string[] }
  /** какие платные функции доступны на сервере: выключенные интерфейс прячет */
  features?: { improve: boolean; competitors: boolean; billing: boolean; oauth?: OAuthProvider[] }
}

/** Вход через внешний аккаунт: VK ID или Яндекс ID */
export type OAuthProvider = 'vk' | 'yandex'

// ------------------------------------------------------------ аккаунт и подписка

export type Feature = 'analyze' | 'shelf' | 'expert' | 'choice' | 'improve' | 'competitors'
export type FeatureLimits = Record<Feature, number>

/** Платный тариф: /api/billing/plans и раздел «Тарифы» в админке. */
export interface PlanInfo {
  id: string
  title: string
  price_rub: number
  period_days: number
  note: string
  featured: boolean
  /** квоты на период оплаты */
  limits: FeatureLimits
}

export interface User {
  email: string
  /** 'demo' или id оплаченного тарифа */
  plan: string
  plan_title: string
  /** до какого момента действует оплаченный тариф, unix-секунды; у демо — null */
  pro_until: number | null
  /** расход и квоты: у демо — на всё время, у тарифа — на период оплаты */
  usage: FeatureLimits
  limits: FeatureLimits
}

export interface Session {
  token: string
  user: User
}

/** Почта подтверждена, но пароль нужно задать заново: на неё регистрировались несколько раз. */
export interface SetPassword {
  status: 'set_password'
  email: string
  reset: string
}

/** Галочки при регистрации: соглашение с политикой и отдельное согласие на обработку данных. */
export interface Consent {
  terms: boolean
  personalData: boolean
}

/** Реквизиты оператора и редакция правил для страницы /legal. */
export interface Legal {
  operator: string
  email: string
  /** дата редакции, YYYY-MM-DD */
  version: string
}

/** Регистрация: аккаунт создан, письмо со ссылкой отправлено — войти можно после подтверждения. */
export interface Registered {
  status: 'verify'
  email: string
}

/** Тарифы: /api/billing/plans. demo — разовые квоты после подтверждения почты. */
export interface Billing {
  /** подключена ли оплата (ключи платёжного сервиса заданы на сервере) */
  enabled: boolean
  /** через кого принимается оплата */
  provider?: 'tochka' | 'yookassa' | null
  demo: FeatureLimits
  plans: PlanInfo[]
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

export type Design = 'brand' | 'editorial' | 'split' | 'feed'

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
  /** бренд и позиционирование: «средний+, для города» — визуальный разбор сверяет с ним обложку */
  positioning?: string
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
  billing: Billing
}

/** Статистика для админки: GET /api/admin/stats (services/stats.py). Суммы — в рублях, даты — unix-секунды. */
export interface AdminStats {
  generated_at: number
  users: {
    total: number
    verified: number
    new_7: number
    new_30: number
    paying: number
    by_plan: { id: string; title: string; count: number }[]
  }
  revenue: { total: number; last_30: number; payments_30: number; ai_cost_30: number }
  funnel_30: { visits: number; registered: number; verified: number; active: number; paid: number }
  features: { feature: string; today: number; week: number; month: number; total: number; cost_30: number }[]
  daily: { day: string; visits: number; registered: number; runs: number; revenue: number }[]
  payments: { created_at: number; email: string; plan: string; amount: number; status: string }[]
  latest_users: {
    email: string
    created_at: number
    verified: boolean
    plan: string
    pro_until: number | null
    runs: number
  }[]
}

/** Задача очереди (services/jobs.py): тяжёлые ручки отвечают 202 {job}, клиент опрашивает /api/jobs/{id}. */
export interface Job {
  id: string
  lane: 'neural' | 'ai' | 'image' | 'browser'
  title: string
  status: 'queued' | 'running' | 'done' | 'error' | 'cancelled'
  /** место в очереди: 1 — следующая; 0 — уже не ждёт */
  position: number
  eta_s: number
  waited_s: number
  result?: unknown
  error?: { status: number; code: string; message: string }
}

/** Очередь для админки: GET /api/admin/queue. */
export interface AdminQueue {
  lanes: {
    id: string
    title: string
    workers: number
    running: number
    waiting: number
    done_1h: number
    failed_1h: number
    avg_wait_s: number
    avg_run_s: number
  }[]
  jobs: {
    lane: string
    title: string
    status: string
    email: string
    plan: string
    position: number
    waited_s: number
    running_s: number
  }[]
}
