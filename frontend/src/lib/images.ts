/**
 * Картинки примеров сервер отдаёт и уменьшенными — WebP нужной ширины (?w=, только из этого списка).
 * На главной они идут в srcset: браузер сам берёт ширину под размер на экране и плотность пикселей,
 * а не грузит оригинал 1086×1448 ради миниатюры. Чужие адреса (blob:, загрузки) остаются как есть.
 */
export const PREVIEW_WIDTHS = [160, 320, 480, 800] as const

const RESIZABLE = /^\/api\/public\/files\/[0-9a-f]+\/[0-9a-f]+\.jpg$/

export function srcset(url: string): string | undefined {
  return RESIZABLE.test(url) ? PREVIEW_WIDTHS.map((w) => `${url}?w=${w} ${w}w`).join(', ') : undefined
}
