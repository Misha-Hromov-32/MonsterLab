<script setup lang="ts">
import { MARK } from '../lib/brand'

// Знак MonStoreLab — «O с рожками». В живом виде (animated) покачивает головой и «дышит»:
// так выглядит ожидание анализа. Цвет — var(--brand), в тёмной теме он светлее.
withDefaults(defineProps<{ size?: number; animated?: boolean }>(), { size: 32, animated: false })
</script>

<template>
  <svg
    class="mark"
    :class="{ animated }"
    :viewBox="MARK.viewBox"
    :height="size"
    :style="{ width: 'auto' }"
    aria-hidden="true"
  >
    <path :d="MARK.d" fill-rule="evenodd" />
  </svg>
</template>

<style scoped>
.mark {
  flex: none;
  display: block;
  fill: var(--brand);
  transform-origin: 50% 70%;
}

.animated {
  animation: nod 2.4s ease-in-out infinite;
}

@keyframes nod {
  0%,
  100% {
    transform: rotate(0deg) scale(1);
  }
  20% {
    transform: rotate(-9deg) scale(1.04);
  }
  45% {
    transform: rotate(7deg) scale(0.98);
  }
  70% {
    transform: rotate(-3deg) scale(1.02);
  }
}

@media (prefers-reduced-motion: reduce) {
  .animated {
    animation: none;
  }
}
</style>
