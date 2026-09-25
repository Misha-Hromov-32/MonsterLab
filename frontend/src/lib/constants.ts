/** Лимиты — те же, что на сервере (backend/app/config.py). */
export const MAX_VARIANTS = 4
export const MAX_COMPETITORS = 12
export const MAX_EXPERT_MODELS = 6

/** Пороги оценок 0–100: от GOOD — хорошо, от WARN — терпимо, ниже — плохо. */
export const SCORE_GOOD = 65
export const SCORE_WARN = 40

/** Во сколько раз зона получает больше внимания, чем её доля площади: заметная / сильная. */
export const AOI_LIFT_OK = 1
export const AOI_LIFT_STRONG = 1.5

/** Подписи зон по умолчанию — в порядке, в котором их предлагаем. */
export const AOI_LABELS = ['Товар', 'Оффер', 'Цена', 'Бенефит', 'Логотип']

export const TOAST_MS = 4200

/** Платные функции — названия для покупателя (ключи — как на сервере: backend/app/services/accounts.py). */
export const FEATURE_TITLES = {
  expert: 'Экспертный разбор',
  improve: 'Улучшение обложки',
  competitors: 'Подбор конкурентов',
} as const

/** Сколько обычно рисуется улучшенная обложка — для полосы ожидания, секунды. */
export const IMPROVE_ETA_SEC = 40
/** Сколько замечаний экспертов передаём нейросети — столько принимает сервер. */
export const IMPROVE_MAX_ISSUES = 6

/** Сколько конкурентов берём из выдачи маркетплейса за один поиск. */
export const COMPETITOR_SEARCH_LIMIT = 8
