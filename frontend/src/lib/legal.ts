import { computed, reactive } from 'vue'
import { api } from '../api'
import type { Legal } from './types'

/** Реквизиты исполнителя и оператора данных (LEGAL_* в .env) — для подвала сайта и страницы /legal. */
export const legal = reactive<{ data: Legal | null }>({ data: null })

let loading: Promise<void> | null = null

export function loadLegal(): Promise<void> {
  // один запрос на страницу; при ошибке следующий вызов попробует снова
  loading ??= api
    .legal()
    .then((d) => {
      legal.data = d
    })
    .catch(() => {
      loading = null
    })
  return loading
}

/** «ОГРНИП» у индивидуального предпринимателя, «ОГРН» — у организации. */
export const ogrnLabel = computed(() => (legal.data?.name?.startsWith('ИП') ? 'ОГРНИП' : 'ОГРН'))
