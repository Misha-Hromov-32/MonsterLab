// Какие картинки принимаем — те же форматы, что сервер (backend/app/core/imaging.py: FORMATS).
// HEIC браузеры не показывают, AVIF сервер не читает — поэтому их нет.

export const IMAGE_HINT = 'Нужны изображения: JPG, PNG или WebP'

/** Значение accept для системного диалога выбора файлов. */
export const IMAGE_ACCEPT = 'image/jpeg,image/png,image/webp'

/** JPG, PNG или WebP — по типу файла или, если браузер его не знает, по расширению. */
export const isImage = (f: File) => /^image\/(jpeg|png|webp)$/.test(f.type) || /\.(jpe?g|png|webp)$/i.test(f.name)
