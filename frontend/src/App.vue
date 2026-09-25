<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import TopBar from './components/TopBar.vue'
import VariantRail from './components/VariantRail.vue'
import Landing from './components/landing/Landing.vue'
import AnalyzeView from './components/AnalyzeView.vue'
import CompareView from './components/CompareView.vue'
import ShelfView from './components/ShelfView.vue'
import ToastMessage from './components/ToastMessage.vue'
import LoginDialog from './components/LoginDialog.vue'
import AccountDialog from './components/AccountDialog.vue'
import TariffsDialog from './components/TariffsDialog.vue'
import { addFiles, loadHealth, loadSite, state, toast } from './store'
import { account, checkPaymentReturn, refreshMe } from './lib/account'

// ?preview=1 — главная внутри iframe админки: только витрина, без опроса сервиса
// и без перехвата перетаскивания файлов (иначе он мешал бы самой админке).
const preview = new URLSearchParams(location.search).get('preview') === '1'

const dragging = ref(false)
// dragenter/dragleave срабатывают на каждом вложенном элементе — считаем глубину
let depth = 0

const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes('Files')

function onEnter(e: DragEvent) {
  if (!hasFiles(e)) return
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
  if (e.dataTransfer?.files.length) addFiles(e.dataTransfer.files)
}

onMounted(() => {
  loadSite()
  if (preview) return
  loadHealth()
  // вернулись со страницы оплаты — дождёмся подтверждения; иначе просто обновим тариф и лимиты
  if (new URLSearchParams(location.search).get('payment') === 'return') checkPaymentReturn(toast)
  else refreshMe()
  window.addEventListener('dragenter', onEnter)
  window.addEventListener('dragleave', onLeave)
  window.addEventListener('dragover', onOver)
  window.addEventListener('drop', onDrop)
})
onUnmounted(() => {
  window.removeEventListener('dragenter', onEnter)
  window.removeEventListener('dragleave', onLeave)
  window.removeEventListener('dragover', onOver)
  window.removeEventListener('drop', onDrop)
})
</script>

<template>
  <div class="app">
    <TopBar />
    <div class="body" :class="{ bare: !state.variants.length }">
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
    <AccountDialog v-else-if="account.dialog === 'account'" />
    <TariffsDialog v-else-if="account.dialog === 'tariffs'" />

    <ToastMessage :message="state.toast" />
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
</style>
