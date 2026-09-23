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
