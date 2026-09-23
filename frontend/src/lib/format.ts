import { SCORE_GOOD, SCORE_WARN } from './constants'

export type Tone = 'good' | 'warn' | 'bad'

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
