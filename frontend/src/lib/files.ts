// Какие картинки принимаем — те же форматы, что сервер (backend/app/core/imaging.py: FORMATS).
// HEIC браузеры не показывают, AVIF сервер не читает — поэтому их нет.

export const IMAGE_HINT = 'Нужны изображения: JPG, PNG или WebP'

/** Значение accept для системного диалога выбора файлов. */
export const IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp'

/** JPG, PNG или WebP — по типу файла или, если браузер его не знает, по расширению. */
export const isImage = (f: File) => /^image\/(jpeg|png|webp)$/.test(f.type) || /\.(jpe?g|png|webp)$/i.test(f.name)

/** data:image/jpeg;base64,… → File: улучшенную обложку добавляем как обычную загрузку. */
export function dataUrlToFile(dataUrl: string, name: string): File {
  const [head, body = ''] = dataUrl.split(',', 2)
  const type = /^data:([^;,]+)/.exec(head)?.[1] ?? 'image/jpeg'
  const bin = atob(body)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return new File([bytes], name, { type })
}
