<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, useId } from 'vue'
import { X } from 'lucide-vue-next'

// Общая оболочка модальных окон аккаунта: фокус внутри окна, Esc и клик по фону закрывают,
// после закрытия фокус возвращается туда, откуда окно открыли.
defineProps<{ title: string; wide?: boolean }>()
const emit = defineEmits<{ close: [] }>()

const titleId = useId()
const box = ref<HTMLDivElement>()
let opener: HTMLElement | null = null

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'

function focusables() {
  return Array.from(box.value?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []).filter((el) => el.offsetParent !== null)
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.stopPropagation()
    emit('close')
    return
  }
  if (e.key !== 'Tab') return
  // «ловушка» фокуса: Tab с последнего элемента уходит на первый, Shift+Tab — наоборот
  const els = focusables()
  if (!els.length) return
  const first = els[0]
  const last = els[els.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
}

onMounted(async () => {
  opener = document.activeElement as HTMLElement | null
  await nextTick()
  // сначала поле ввода (форма входа), иначе первая кнопка после «закрыть»
  const els = focusables()
  const target =
    box.value?.querySelector<HTMLElement>('[data-autofocus]') ??
    els.find((el) => el.tagName === 'INPUT') ??
    els[1] ??
    els[0]
  target?.focus()
})
onUnmounted(() => opener?.focus?.())
</script>

<template>
  <Teleport to="body">
    <div class="veil" @mousedown.self="emit('close')">
      <div
        ref="box"
        class="dialog rise"
        :class="{ wide }"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="titleId"
        @keydown="onKey"
      >
        <header class="dh">
          <h2 :id="titleId">{{ title }}</h2>
          <button type="button" class="btn ghost sm icon" aria-label="Закрыть" @click="emit('close')">
            <X :size="16" />
          </button>
        </header>
        <slot />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.veil {
  position: fixed;
  inset: 0;
  /* над шапкой и слоем перетаскивания файлов, но под тостом — подтверждения видны поверх окна */
  z-index: 55;
  display: grid;
  place-items: center;
  padding: 16px;
  overflow-y: auto;
  background: color-mix(in srgb, var(--ink) 28%, transparent);
  backdrop-filter: blur(2px);
}

.dialog {
  display: grid;
  gap: 18px;
  width: min(100%, 420px);
  padding: 20px 22px 22px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--panel);
  color: var(--ink);
  box-shadow: var(--shadow);
}

.dialog.wide {
  width: min(100%, 640px);
}

.dh {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dh h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 300;
  letter-spacing: -0.03em;
}

.dh .btn {
  margin-right: -6px;
}

@media (max-width: 480px) {
  .dialog {
    padding: 16px;
  }
}
</style>
