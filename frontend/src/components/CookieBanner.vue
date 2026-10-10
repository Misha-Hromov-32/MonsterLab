<script setup lang="ts">
import { Cookie } from 'lucide-vue-next'
import { consent, setConsent } from '../lib/consent'

// Плашка о cookie: необходимые работают всегда (вход, настройки), аналитические (Яндекс Метрика) — только
// после «Принять». Выбор можно изменить ссылкой «Настройки cookie» в подвале.
</script>

<template>
  <Transition name="cookie">
    <section v-if="consent.open" class="cookie" role="region" aria-label="Настройки cookie">
      <span class="ic" aria-hidden="true"><Cookie :size="18" /></span>
      <p>
        Мы используем необходимые cookie для работы сайта.
        <a href="/legal#cookies">Подробнее</a>
      </p>
      <div class="btns">
        <button type="button" class="btn ghost sm" @click="setConsent('necessary')">Только необходимые</button>
        <button type="button" class="btn primary sm" @click="setConsent('all')">Принять</button>
      </div>
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
  grid-template-columns: auto 1fr;
  gap: 10px 12px;
  max-width: 460px;
  padding: 14px 16px;
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

.btns {
  grid-column: 2;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
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
    grid-template-columns: 1fr;
  }
  .ic {
    display: none;
  }
  .btns {
    grid-column: 1;
  }
  .btns .btn {
    flex: 1;
    justify-content: center;
  }
}
</style>
