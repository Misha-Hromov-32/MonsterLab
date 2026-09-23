import { createApp } from 'vue'
import '@fontsource-variable/onest'
import './styles/base.css'
import App from './App.vue'
import { watchSystemTheme } from './lib/theme'

watchSystemTheme()

// /admin — отдельное приложение, грузится лениво и не утяжеляет основной сайт
if (location.pathname.replace(/\/+$/, '') === '/admin') {
  import('./admin/AdminApp.vue').then(({ default: AdminApp }) => createApp(AdminApp).mount('#app'))
} else {
  createApp(App).mount('#app')
}
