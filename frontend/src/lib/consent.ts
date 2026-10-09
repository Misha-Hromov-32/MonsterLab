import { reactive } from 'vue'

/**
 * Согласие на cookie. «all» — необходимые и аналитические (Яндекс Метрика), «necessary» — только необходимые
 * для работы сайта (вход, настройки). Пусто — выбор ещё не сделан: показываем плашку, аналитику не грузим.
 * Хранится в localStorage; прежняя отметка «ознакомлен» (до появления аналитики) выбором не считается.
 */
export type ConsentChoice = '' | 'all' | 'necessary'

const KEY = 'ml.cookies'

function read(): ConsentChoice {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? 'null')
    return raw && (raw.choice === 'all' || raw.choice === 'necessary') ? raw.choice : ''
  } catch {
    return ''
  }
}

export const consent = reactive({ choice: read() as ConsentChoice, open: false })
consent.open = !consent.choice

export function setConsent(choice: Exclude<ConsentChoice, ''>) {
  const changedToNecessary = consent.choice === 'all' && choice === 'necessary'
  consent.choice = choice
  consent.open = false
  try {
    localStorage.setItem(KEY, JSON.stringify({ choice, at: new Date().toISOString() }))
  } catch {
    /* приватный режим — выбор действует до закрытия вкладки */
  }
  // отзыв согласия: скрипт Метрики уже в странице — перезагрузка выгрузит его, а без согласия он не загрузится
  if (changedToNecessary) location.reload()
}

/** «Настройки cookie» в подвале: показать плашку снова, чтобы изменить выбор. */
export function reopenConsent() {
  consent.open = true
}
