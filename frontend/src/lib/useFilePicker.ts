import { IMAGE_ACCEPT } from './files'
import { goal } from './metrika'

/**
 * Системный диалог выбора файлов без скрытого <input> в разметке: у каждого вызова свой
 * input, поэтому нет лишних точек фокуса, а multiple выставляется до открытия диалога.
 *
 *   const pick = useFilePicker((files) => addFiles(files))
 *   pick()                 // несколько файлов
 *   pick({ multiple: false })
 */
export function useFilePicker(onFiles: (files: File[]) => void, accept = IMAGE_ACCEPT) {
  return ({ multiple = true }: { multiple?: boolean } = {}) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = accept
    input.multiple = multiple
    input.addEventListener('change', () => {
      if (input.files?.length) onFiles(Array.from(input.files))
    })
    goal('upload_click')
    input.click()
  }
}
