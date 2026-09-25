<script setup lang="ts" generic="T extends string">
import { ref } from 'vue'

const props = defineProps<{
  options: { id: T; title: string; hint?: string }[]
  modelValue: T
  size?: 'sm'
  label?: string
}>()
const emit = defineEmits<{ 'update:modelValue': [v: T] }>()

const root = ref<HTMLDivElement>()

// Стрелки двигают выбор, как в нативной группе радиокнопок; в Tab-порядке только выбранная кнопка.
function onKey(e: KeyboardEvent) {
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key]
  const n = props.options.length
  let i = props.options.findIndex((o) => o.id === props.modelValue)
  if (step) i = (i + step + n) % n
  else if (e.key === 'Home') i = 0
  else if (e.key === 'End') i = n - 1
  else return
  e.preventDefault()
  emit('update:modelValue', props.options[i].id)
  root.value?.querySelectorAll('button')[i]?.focus()
}
</script>

<template>
  <div ref="root" class="seg" :class="size" role="radiogroup" :aria-label="label" @keydown="onKey">
    <button
      v-for="o in options"
      :key="o.id"
      type="button"
      role="radio"
      :aria-checked="modelValue === o.id"
      :tabindex="modelValue === o.id ? 0 : -1"
      :class="{ on: modelValue === o.id }"
      :title="o.hint"
      @click="emit('update:modelValue', o.id)"
    >
      {{ o.title }}
    </button>
  </div>
</template>

<style scoped>
.seg {
  display: inline-flex;
  padding: 3px;
  gap: 2px;
  border-radius: 9px;
  background: var(--panel-2);
  border: 1px solid var(--line);
}

button {
  height: 28px;
  padding: 0 12px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-2);
  font-size: 12.5px;
  font-weight: 500;
  white-space: nowrap;
  transition:
    background 0.12s,
    color 0.12s;
}

button:hover {
  color: var(--ink);
}

button.on {
  background: var(--panel);
  color: var(--ink);
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.08),
    0 0 0 1px var(--line);
}

.sm button {
  height: 24px;
  padding: 0 9px;
  font-size: 12px;
}

/* узкий телефон: все пять режимов помещаются без прокрутки */
@media (max-width: 420px) {
  button,
  .sm button {
    padding: 0 7px;
    font-size: 11.5px;
  }
}
</style>
