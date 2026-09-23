<script setup lang="ts">
defineProps<{ message: string }>()
</script>

<template>
  <!-- живая область всегда в DOM: иначе экранный диктор может пропустить первое сообщение -->
  <div class="toast-live" role="status" aria-live="polite">
    <Transition name="toast">
      <div v-if="message" class="toast">{{ message }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.toast {
  position: fixed;
  left: 50%;
  bottom: 24px;
  z-index: 60;
  max-width: calc(100vw - 32px);
  transform: translateX(-50%);
  padding: 10px 16px;
  border-radius: 10px;
  background: var(--ink);
  color: var(--bg);
  font-size: 13px;
  box-shadow: var(--shadow);
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 0.2s,
    transform 0.2s;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, 8px);
}
</style>
