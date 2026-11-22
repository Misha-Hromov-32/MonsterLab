const key = 'ml.referral'
const incoming = new URLSearchParams(location.search).get('ref') || ''
const valid = /^[A-Za-z0-9_-]{12,64}$/
try {
  if (valid.test(incoming)) sessionStorage.setItem(key, incoming)
} catch {
  /* Ссылка действует и при отключённом хранилище. */
}

export function referralCode() {
  try {
    return sessionStorage.getItem(key) || (valid.test(incoming) ? incoming : '')
  } catch {
    return valid.test(incoming) ? incoming : ''
  }
}
