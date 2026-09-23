import type { OverlayMode } from './types'

export interface OverlayOption {
  id: OverlayMode
  title: string
  hint: string
}

/** Режимы наложения в порядке клавиш 1–5. */
export const OVERLAY_MODES: OverlayOption[] = [
  { id: 'original', title: 'Оригинал', hint: 'Без наложений' },
  { id: 'heat', title: 'Тепло', hint: 'Где задерживается взгляд' },
  { id: 'fog', title: 'Туман', hint: 'Видно только то, что заметят' },
  { id: 'contours', title: 'Изолинии', hint: 'Зоны, где лежит 25 / 50 / 75% внимания' },
  { id: 'gaze', title: 'Взгляд', hint: 'В каком порядке покупатель рассматривает обложку' },
]

/** На полке порядок взгляда по одной карточке не считается — без режима «Взгляд». */
export const SHELF_OVERLAY_MODES = OVERLAY_MODES.filter((m) => m.id !== 'gaze')

/** Режимы, у которых есть ползунок плотности. */
export const hasOpacity = (m: OverlayMode): m is 'heat' | 'fog' => m === 'heat' || m === 'fog'
