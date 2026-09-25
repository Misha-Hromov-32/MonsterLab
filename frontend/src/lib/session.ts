import { reactive } from 'vue'

// Токен покупателя — отдельно от админского (ml.admin.token): у них разные права и срок жизни.
// Живёт в своём модуле, чтобы api.ts мог подставлять заголовок, не завися от логики аккаунта.
export const USER_TOKEN_KEY = 'ml.user.token'

function readToken() {
  try {
    return localStorage.getItem(USER_TOKEN_KEY) ?? ''
  } catch {
    return ''
  }
}

export const session = reactive({ token: readToken() })

export function setUserToken(token: string) {
  session.token = token
  try {
    if (token) localStorage.setItem(USER_TOKEN_KEY, token)
    else localStorage.removeItem(USER_TOKEN_KEY)
  } catch {
    /* приватный режим — вход живёт до перезагрузки */
  }
}

/** Заголовок входа для запросов покупателя; без входа — пустой: бесплатные функции работают и так. */
export function authHeader(): Record<string, string> {
  return session.token ? { Authorization: `Bearer ${session.token}` } : {}
}
