// Тема: index.html ставит data-theme до загрузки CSS (из localStorage или системной настройки),
// поэтому в CSS тёмная палитра описана один раз — для :root[data-theme='dark'] (и :root.feed-dark для тёмной ленты).

const THEME_KEY = 'ml.theme'
const systemDark = window.matchMedia('(prefers-color-scheme: dark)')

function storedTheme() {
  try {
    return localStorage.getItem(THEME_KEY)
  } catch {
    return null
  }
}

/** Ставит тему и цвет панели браузера (meta theme-color) — цвета совпадают с --bg в base.css. */
function applyTheme(theme: 'light' | 'dark') {
  document.documentElement.dataset.theme = theme
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#121212' : '#ffffff')
}

/** Пока пользователь не выбрал тему сам, она следует за системной. */
export function watchSystemTheme() {
  systemDark.addEventListener('change', (e) => {
    if (!storedTheme()) applyTheme(e.matches ? 'dark' : 'light')
  })
}

export function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'
  applyTheme(next)
  try {
    localStorage.setItem(THEME_KEY, next)
  } catch {
    /* тема живёт до перезагрузки */
  }
}
