// Тема до загрузки CSS, чтобы страница не мигала: выбор пользователя или системная.
// Отдельным файлом, а не в index.html: политика безопасности (CSP) запрещает встроенные скрипты.
;(function () {
  var t = null
  try {
    t = localStorage.getItem('ml.theme')
  } catch (e) {}
  if (t !== 'light' && t !== 'dark') t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  document.documentElement.dataset.theme = t
  var m = document.querySelector('meta[name="theme-color"]')
  if (m) m.setAttribute('content', t === 'dark' ? '#121212' : '#ffffff')
})()
