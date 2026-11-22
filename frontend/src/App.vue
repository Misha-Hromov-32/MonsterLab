<script setup lang="ts">
import { loadPlans } from './lib/account'
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import TopBar from './components/TopBar.vue'
import VariantRail from './components/VariantRail.vue'
import Landing from './components/landing/Landing.vue'
import AnalyzeView from './components/AnalyzeView.vue'
import CompareView from './components/CompareView.vue'
import ShelfView from './components/ShelfView.vue'
import ToastMessage from './components/ToastMessage.vue'
import QueueBadge from './components/QueueBadge.vue'
import CookieBanner from './components/CookieBanner.vue'
import LoginDialog from './components/LoginDialog.vue'
import { defineAsyncComponent } from 'vue'
import { cabinetTab, syncCabinet } from './lib/cabinet'
const AccountDashboard = defineAsyncComponent(() => import('./components/AccountDashboard.vue'))
import TariffsDialog from './components/TariffsDialog.vue'
import LeadDialog from './components/LeadDialog.vue'
import { addFiles, loadHealth, loadSite, resetAll, state, toast } from './store'
import { session } from './lib/session'
import { account, checkPaymentReturn, handleEmailLink, handleOAuthCallback, openLogin, refreshMe } from './lib/account'
import { consent } from './lib/consent'
import { hit, initMetrika } from './lib/metrika'

// ?preview=1 — главная внутри iframe админки: только витрина, без опроса сервиса
// и без перехвата перетаскивания файлов (иначе он мешал бы самой админке).
const preview = new URLSearchParams(location.search).get('preview') === '1'

// Рабочий экран тоже принадлежит аккаунту: смена пользователя очищает чужие работы.
watch(
  () => session.token,
  (_token, previous) => {
    if (previous) resetAll()
  },
  { flush: 'sync' },
)

const workspaceVisited = ref(!cabinetTab.value)
let workspaceScroll = 0
let lastView = state.view
watch(
  cabinetTab,
  (next, prev) => {
    if (next && !prev) {
      workspaceScroll = window.scrollY
      lastView = state.view
      void nextTick(() => window.scrollTo(0, 0))
    } else if (!next) {
      workspaceVisited.value = true
      void nextTick(() => window.scrollTo(0, state.view === lastView ? workspaceScroll : 0))
    }
  },
  { flush: 'sync' },
)
const dragging = ref(false)
// dragenter/dragleave срабатывают на каждом вложенном элементе — считаем глубину
let depth = 0

const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes('Files')

function onEnter(e: DragEvent) {
  if (cabinetTab.value || (e.target as HTMLElement)?.closest?.('[data-own-drop]') || !hasFiles(e)) return
  depth++
  dragging.value = true
}
function onLeave(e: DragEvent) {
  if (!hasFiles(e)) return
  depth = Math.max(0, depth - 1)
  if (!depth) dragging.value = false
}
function onOver(e: DragEvent) {
  if (hasFiles(e)) e.preventDefault()
}
function onDrop(e: DragEvent) {
  if (!hasFiles(e)) return
  e.preventDefault()
  depth = 0
  dragging.value = false
  // зоны с собственной обработкой (конкуренты) помечены data-own-drop
  if ((e.target as HTMLElement)?.closest?.('[data-own-drop]')) return
  if (!cabinetTab.value && e.dataTransfer?.files.length) addFiles(e.dataTransfer.files)
}

// Яндекс Метрика: только с согласия на аналитические cookie и если на сервере задан номер счётчика
watch(
  () => [state.health?.features?.metrika, consent.choice] as const,
  ([id]) => initMetrika(id),
  { immediate: true },
)
// одностраничное приложение: разбор, сравнение и полка — отдельные «страницы» в отчётах Метрики
watch(
  () => (state.variants.length ? state.view : 'landing'),
  (view, prev) => {
    if (prev === undefined) return
    hit(view === 'landing' ? '/' : `/#${view}`)
    // новая «страница» — с самого верха: на телефоне прокручивается весь документ, и пример из галереи
    // открывался бы на той высоте, где была галерея на главной
    window.scrollTo({ top: 0 })
  },
  { flush: 'post' },
)

onMounted(() => {
  void loadPlans()
  loadSite(preview)
  if (preview) return
  loadHealth()
  // вернулись со страницы оплаты — дождёмся подтверждения; пришли по ссылке из письма — подтвердим
  // почту или откроем окно нового пароля; иначе просто обновим тариф и лимиты
  if (['return', 'fail'].includes(new URLSearchParams(location.search).get('payment') ?? '')) checkPaymentReturn(toast)
  else
    // вернулись от VK ID / Яндекс ID — завершаем вход; иначе — ссылка из письма или просто обновление тарифа
    handleOAuthCallback(toast)
      .then((handled) => handled || handleEmailLink(toast))
      .then((handled) => {
        if (!handled) {
          void refreshMe()
          const target = new URLSearchParams(location.search).get('studio') || ''
          if (['partner', 'wb', 'rules'].includes(target)) {
            const enter = () => location.assign('/studio#' + target)
            if (session.token) enter()
            else openLogin('Войдите, чтобы открыть инструменты продавца', enter)
          } else if (new URLSearchParams(location.search).has('ref') && !session.token) {
            openLogin('Создайте аккаунт по приглашению партнёра', undefined, 'register')
          }
        }
      })
  window.addEventListener('popstate', syncCabinet)
  window.addEventListener('hashchange', syncCabinet)
  window.addEventListener('dragenter', onEnter)
  window.addEventListener('dragleave', onLeave)
  window.addEventListener('dragover', onOver)
  window.addEventListener('drop', onDrop)
})
onUnmounted(() => {
  window.removeEventListener('popstate', syncCabinet)
  window.removeEventListener('hashchange', syncCabinet)
  window.removeEventListener('dragenter', onEnter)
  window.removeEventListener('dragleave', onLeave)
  window.removeEventListener('dragover', onOver)
  window.removeEventListener('drop', onDrop)
})
</script>

<template>
  <div class="app" :class="{ 'in-cabinet': cabinetTab }">
    <TopBar />
    <AccountDashboard v-if="cabinetTab" />
    <div
      v-if="workspaceVisited"
      v-show="!cabinetTab"
      :inert="!!cabinetTab"
      class="body"
      :class="{ bare: !state.variants.length }"
    >
      <VariantRail v-if="state.variants.length" />
      <main class="main">
        <Landing v-if="!state.variants.length" />
        <AnalyzeView v-else-if="state.view === 'analyze'" />
        <CompareView v-else-if="state.view === 'compare'" />
        <ShelfView v-else />
      </main>
    </div>

    <Transition name="fade">
      <div v-if="dragging" class="dropveil">
        <div class="dropveil-inner">
          <span class="label">Отпустите файлы</span>
          <strong>Добавить как варианты</strong>
        </div>
      </div>
    </Transition>

    <LoginDialog v-if="account.dialog === 'login'" />
    <TariffsDialog v-else-if="account.dialog === 'tariffs'" />

    <LeadDialog v-if="state.leadOpen" />

    <ToastMessage :message="state.toast" />
    <QueueBadge />
    <CookieBanner />
  </div>
</template>

<style scoped>
.app {
  display: grid;
  grid-template-rows: auto 1fr;
  height: 100vh;
  height: 100dvh;
}

.body {
  display: grid;
  grid-template-columns: var(--rail-w) minmax(0, 1fr);
  min-height: 0;
}

.body.bare {
  grid-template-columns: minmax(0, 1fr);
}

.main {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.dropveil {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--bg) 70%, transparent);
  backdrop-filter: blur(3px);
  pointer-events: none;
}

.dropveil-inner {
  display: grid;
  gap: 8px;
  justify-items: center;
  padding: 44px 64px;
  border: 1.5px dashed var(--ink);
  border-radius: 16px;
  background: var(--panel);
}

.dropveil-inner strong {
  font-size: 22px;
  letter-spacing: -0.02em;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 900px) {
  .app {
    height: auto;
    min-height: 100dvh;
  }
  .body {
    grid-template-columns: minmax(0, 1fr);
  }
}
.app.in-cabinet {
  height: 100dvh;
  min-height: 0;
  grid-template-rows: auto minmax(0, 1fr);
  overflow: hidden;
}
</style>
