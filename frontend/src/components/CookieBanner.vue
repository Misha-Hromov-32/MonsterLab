<script setup lang="ts">
import { ref } from 'vue'
import { Cookie } from 'lucide-vue-next'

// Плашка о cookie и хранилище браузера. Рекламы и аналитики на сайте нет, поэтому выбирать нечего —
// пользователь только подтверждает, что ознакомлен; отметка хранится в localStorage.
const KEY = 'ml.cookies'

function seen(): boolean {
  try {
    return !!localStorage.getItem(KEY)
  } catch {
    return false
  }
}

const open = ref(!seen())

function accept() {
  open.value = false
  try {
    localStorage.setItem(KEY, new Date().toISOString())
  } catch {
    /* приватный режим — плашка появится снова при следующем визите */
  }
}
</script>

<template>
  <Transition name="cookie">
    <section v-if="open" class="cookie" role="region" aria-label="Использование cookie">
      <span class="ic" aria-hidden="true"><Cookie :size="18" /></span>
      <p>
        Мы используем cookie и хранилище браузера только для работы сайта: вход в аккаунт и настройки. Рекламных и
        аналитических cookie нет.
        <a href="/legal#cookies">Подробнее</a>
      </p>
      <button type="button" class="btn primary sm" @click="accept">Понятно</button>
    </section>
  </Transition>
</template>

<style scoped>
.cookie {
  position: fixed;
  left: 16px;
  bottom: 16px;
  z-index: 60;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  max-width: 520px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--panel);
  box-shadow: var(--shadow);
  font-size: 13px;
  line-height: 1.45;
  color: var(--ink-2);
}

.ic {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--brand) 12%, transparent);
  color: var(--brand);
}

p {
  margin: 0;
}

a {
  color: var(--ink);
  text-underline-offset: 3px;
}

.cookie-enter-active,
.cookie-leave-active {
  transition:
    opacity 0.2s,
    transform 0.2s;
}

.cookie-enter-from,
.cookie-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 560px) {
  .cookie {
    left: 8px;
    right: 8px;
    bottom: 8px;
    grid-template-columns: 1fr auto;
  }
  .ic {
    display: none;
  }
}
</style>
