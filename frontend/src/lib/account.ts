import { computed, reactive } from 'vue'
import { api, ApiError } from '../api'
import { session, setUserToken } from './session'
import { formatDate } from './format'
import type { BillingPlan, Session, User } from './types'

export type AccountDialog = '' | 'login' | 'account' | 'tariffs'
/** sent — «проверьте почту», forgot — запрос ссылки для нового пароля, reset — ввод нового пароля */
export type AuthMode = 'login' | 'register' | 'sent' | 'forgot' | 'reset'
export type LetterKind = 'verify' | 'reset'

/**
 * Аккаунт покупателя: кто вошёл, условия подписки и какой диалог открыт.
 * Store сюда обращается, а не наоборот — модуль ничего не знает о вариантах и тостах.
 */
export const account = reactive({
  user: null as User | null,
  plan: null as BillingPlan | null,
  dialog: '' as AccountDialog,
  authMode: 'login' as AuthMode,
  /** почему открыли диалог: «войдите, чтобы…», «исчерпан лимит…» */
  reason: '',
  /** куда ушло письмо и какое (режим sent) */
  pendingEmail: '',
  letter: 'verify' as LetterKind,
  /** токен из ссылки сброса пароля (режим reset) */
  resetToken: '',
})

export const signedIn = computed(() => !!session.token)
export const isPro = computed(() => account.user?.plan === 'pro')

/** Что сделать после входа — например, повторить разбор, ради которого покупатель входил. */
let afterLogin: (() => void) | null = null

export function openLogin(reason = '', then?: () => void, mode: AuthMode = 'login') {
  account.reason = reason
  account.authMode = mode
  afterLogin = then ?? null
  account.dialog = 'login'
}

export function openAccount() {
  account.reason = ''
  account.dialog = 'account'
  refreshMe()
  loadPlan()
}

export function openTariffs(reason = '') {
  account.reason = reason
  account.dialog = 'tariffs'
  loadPlan()
}

export function closeDialog() {
  account.dialog = ''
  account.reason = ''
  account.resetToken = ''
  afterLogin = null
}

function forget() {
  setUserToken('')
  account.user = null
}

export function logout() {
  forget()
  closeDialog()
}

/** Обновляет тариф и расход лимитов. Токен отозван или устарел — тихо выходим. */
export async function refreshMe() {
  if (!session.token) return
  try {
    account.user = await api.me()
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) forget()
  }
}

export async function loadPlan() {
  try {
    account.plan = await api.billingPlan()
  } catch {
    /* без условий кнопка оплаты просто не покажется */
  }
}

/** Вход состоялся: сохраняем токен и выполняем то, ради чего покупатель входил. */
function finishLogin(s: Session) {
  setUserToken(s.token)
  account.user = s.user
  const next = afterLogin
  closeDialog()
  next?.()
}

/** Окно переходит в «Проверьте почту». */
function showSent(email: string, letter: LetterKind, reason = '') {
  account.pendingEmail = email.trim().toLowerCase()
  account.letter = letter
  account.reason = reason
  account.authMode = 'sent'
}

/**
 * Вход или регистрация. Возвращает текст ошибки для формы или '' — тогда окно либо закрылось
 * (вошли), либо показывает «Проверьте почту» (зарегистрировались или почта ещё не подтверждена).
 */
export async function signIn(mode: 'login' | 'register', email: string, password: string): Promise<string> {
  try {
    if (mode === 'register') {
      showSent((await api.register(email, password)).email, 'verify')
      return ''
    }
    finishLogin(await api.login(email, password))
  } catch (e) {
    if (e instanceof ApiError && e.code === 'email_unverified') {
      showSent(email, 'verify', e.message)
      return ''
    }
    return (e as Error).message
  }
  return ''
}

/** «Отправить ещё раз» в окне «Проверьте почту». */
export async function resendLetter(): Promise<string> {
  try {
    if (account.letter === 'reset') await api.forgot(account.pendingEmail)
    else await api.resend(account.pendingEmail)
    return ''
  } catch (e) {
    return (e as Error).message
  }
}

/** «Забыли пароль?»: письмо со ссылкой. Сервер отвечает одинаково, есть такой аккаунт или нет. */
export async function requestReset(email: string): Promise<string> {
  try {
    await api.forgot(email.trim())
    showSent(email, 'reset')
    return ''
  } catch (e) {
    return (e as Error).message
  }
}

/** Новый пароль по ссылке из письма — и сразу вход. */
export async function setNewPassword(password: string): Promise<string> {
  try {
    finishLogin(await api.resetPassword(account.resetToken, password))
    return ''
  } catch (e) {
    return (e as Error).message
  }
}

/**
 * Переход по ссылке из письма: ?verify=… подтверждает почту и сразу входит,
 * ?reset=… открывает окно нового пароля. Возвращает true, если в адресе была такая ссылка.
 */
export async function handleEmailLink(notify: (msg: string) => void): Promise<boolean> {
  const url = new URL(location.href)
  const verify = url.searchParams.get('verify')
  const reset = url.searchParams.get('reset')
  if (!verify && !reset) return false
  // одноразовый токен не должен оставаться в адресной строке и истории браузера
  url.searchParams.delete('verify')
  url.searchParams.delete('reset')
  history.replaceState(history.state, '', url.pathname + url.search + url.hash)
  if (reset) {
    openLogin('', undefined, 'reset')
    account.resetToken = reset
    return true
  }
  try {
    const s = await api.verify(verify!)
    setUserToken(s.token)
    account.user = s.user
    notify(`Почта подтверждена — добро пожаловать, ${s.user.email}`)
  } catch (e) {
    openLogin((e as Error).message)
  }
  return true
}

/**
 * Функция сервиса без входа: сразу предлагаем войти, не дёргая сервер.
 * then — что повторить после входа. Возвращает true, если можно продолжать.
 */
export function requireLogin(reason: string, then?: () => void) {
  if (session.token) return true
  openLogin(reason, then)
  return false
}

/**
 * Ошибка доступа к платной функции: вход устарел — просим войти снова, исчерпан лимит —
 * показываем тарифы. Возвращает текст для места ошибки или null, если ошибка не про доступ.
 */
export function paidError(e: unknown, retry?: () => void): string | null {
  if (!(e instanceof ApiError)) return null
  if (e.code === 'login_required') {
    forget()
    openLogin(e.message, retry)
    return e.message
  }
  if (e.code === 'limit_reached') {
    openTariffs(e.message)
    refreshMe()
    return e.message
  }
  return null
}

/** Переход на страницу оплаты ЮKassa. Возвращает текст ошибки, если оплата сейчас невозможна. */
export async function checkout(): Promise<string> {
  if (!requireLogin('Войдите, чтобы оформить подписку', () => openTariffs())) return ''
  try {
    const { url } = await api.checkout()
    location.href = url
    return ''
  } catch (e) {
    return paidError(e, () => openTariffs()) ?? (e as Error).message
  }
}

const PAYMENT_POLLS = 10
const PAYMENT_POLL_MS = 3000

/**
 * Возврат со страницы оплаты (/?payment=return): ЮKassa присылает подтверждение серверу
 * не мгновенно — несколько раз перечитываем тариф, пока он не станет Pro (до ~30 секунд).
 */
export async function checkPaymentReturn(
  notify: (msg: string) => void,
  wait = (ms: number) => new Promise((r) => setTimeout(r, ms)),
) {
  const url = new URL(location.href)
  if (url.searchParams.get('payment') !== 'return') return
  try {
    if (!session.token) return
    for (let i = 0; i < PAYMENT_POLLS; i++) {
      await refreshMe()
      const u = account.user
      if (u?.plan === 'pro') {
        notify(u.pro_until ? `Подписка активна до ${formatDate(u.pro_until)}` : 'Подписка активна')
        return
      }
      if (i < PAYMENT_POLLS - 1) await wait(PAYMENT_POLL_MS)
    }
    notify('Оплата обрабатывается — обновите страницу через минуту')
  } finally {
    // обновление страницы не должно снова запускать ожидание оплаты
    url.searchParams.delete('payment')
    history.replaceState(history.state, '', url.pathname + url.search + url.hash)
  }
}
