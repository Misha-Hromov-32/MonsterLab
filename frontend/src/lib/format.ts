import { SCORE_GOOD, SCORE_WARN, type FEATURE_TITLES } from './constants'

export type Tone = 'good' | 'warn' | 'bad'

/** «Инфографика.jpg» → «Инфографика»: расширение на экране только отнимает место. */
export const baseName = (name: string) => name.replace(/\.(jpe?g|png|webp)$/i, '')

export const pct = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`

export function tone(v: number): Tone {
  return v >= SCORE_GOOD ? 'good' : v >= SCORE_WARN ? 'warn' : 'bad'
}

/** plural(5, ['вариант', 'варианта', 'вариантов']) → «вариантов» */
export function plural(n: number, forms: [string, string, string]) {
  const n10 = n % 10
  const n100 = n % 100
  if (n10 === 1 && n100 !== 11) return forms[0]
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return forms[1]
  return forms[2]
}

/** «2 эксперта не ответили» — сколько экспертов промолчало, без имён */
export function silentExperts(n: number) {
  return `${n} ${plural(n, ['эксперт', 'эксперта', 'экспертов'])} ${plural(n, ['не ответил', 'не ответили', 'не ответили'])}`
}

const BRANDS: Record<string, string> = {
  gpt: 'GPT',
  gemini: 'Gemini',
  claude: 'Claude',
  qwen: 'Qwen',
  deepseek: 'DeepSeek',
  llama: 'Llama',
  grok: 'Grok',
}

/** google/gemini-2.5-flash → Gemini 2.5 Flash; anthropic/claude-haiku-4-5 → Claude Haiku 4.5 */
export function modelName(id: string) {
  const name = (id.split('/').pop() ?? id).replace(/(\d)-(\d)/g, '$1.$2')
  return name
    .split('-')
    .map((w) => BRANDS[w.toLowerCase()] ?? (/^\d/.test(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(' ')
    .replace(/^GPT (\d)/, 'GPT-$1')
}

/** unix-секунды → «25 октября 2026» */
export function formatDate(sec: number) {
  // «г.» в конце браузер добавляет сам — в строке «до 25 октября 2026» он лишний
  return new Date(sec * 1000)
    .toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
    .replace(/\s*г\.$/, '')
}

/** «990 ₽ / 30 дней» */
export function priceLabel(rub: number, days: number) {
  return `${rub.toLocaleString('ru-RU')} ₽ / ${days} ${plural(days, ['день', 'дня', 'дней'])}`
}

/** «30 визуальных разборов» — формы для 1, 2–4 и 5+ */
const FEATURE_FORMS: Record<keyof typeof FEATURE_TITLES, [string, string, string]> = {
  analyze: ['проверка обложки', 'проверки обложек', 'проверок обложек'],
  shelf: ['тест полки', 'теста полки', 'тестов полки'],
  expert: ['визуальный разбор', 'визуальных разбора', 'визуальных разборов'],
  choice: ['выбор покупателя', 'выбора покупателя', 'выборов покупателя'],
  improve: ['улучшенная обложка', 'улучшенные обложки', 'улучшенных обложек'],
  competitors: ['подбор конкурентов', 'подбора конкурентов', 'подборов конкурентов'],
}

export function quotaLabel(f: keyof typeof FEATURE_TITLES, n: number) {
  return `${n.toLocaleString('ru-RU')} ${plural(n, FEATURE_FORMS[f])}`
}

/** Что даёт промокод, по строкам: «+10 проверок обложек», «−2 теста полки», «тариф «Старт» на 7 дней». */
export function promoSummary(
  p: { bonus: Partial<Record<keyof typeof FEATURE_TITLES, number>>; plan_id: string | null; plan_days: number },
  planTitle: (id: string) => string = (id) => id,
): string[] {
  const out = (Object.keys(FEATURE_FORMS) as (keyof typeof FEATURE_TITLES)[])
    .filter((f) => p.bonus[f])
    .map((f) => `${p.bonus[f]! > 0 ? '+' : '−'}${quotaLabel(f, Math.abs(p.bonus[f]!))}`)
  if (p.plan_id && p.plan_days)
    out.push(`тариф «${planTitle(p.plan_id)}» на ${p.plan_days} ${plural(p.plan_days, ['день', 'дня', 'дней'])}`)
  return out
}
