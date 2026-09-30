import { createApp } from 'vue'
import '@fontsource-variable/onest'
import './styles/base.css'
import App from './App.vue'
import { watchSystemTheme } from './lib/theme'

watchSystemTheme()

// /admin и /legal — отдельные страницы, грузятся лениво и не утяжеляют основной сайт
const path = location.pathname.replace(/\/+$/, '')
if (path === '/admin') {
  import('./admin/AdminApp.vue').then(({ default: AdminApp }) => createApp(AdminApp).mount('#app'))
} else if (path === '/legal') {
  import('./legal/LegalPage.vue').then(({ default: LegalPage }) => createApp(LegalPage).mount('#app'))
} else {
  createApp(App).mount('#app')
}
