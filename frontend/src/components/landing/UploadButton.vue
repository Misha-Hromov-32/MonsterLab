<script setup lang="ts">
import { Upload } from 'lucide-vue-next'
import { addFiles } from '../../store'
import { useFilePicker } from '../../lib/useFilePicker'

defineProps<{ label: string; tone?: 'ink' | 'accent' }>()

const pick = useFilePicker((files) => addFiles(files))
</script>

<template>
  <div class="upload">
    <button type="button" class="big" :class="tone ?? 'ink'" @click="pick()">
      <Upload :size="18" aria-hidden="true" />
      {{ label }}
    </button>
    <span class="hint">или перетащите файлы в окно · JPG, PNG, WebP</span>
  </div>
</template>

<style scoped>
.upload {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.big {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 52px;
  padding: 0 24px;
  border: 0;
  border-radius: 8px;
  font-size: 15.5px;
  font-weight: 400;
  letter-spacing: -0.02em;
  transition:
    transform 0.12s,
    box-shadow 0.2s,
    background 0.2s;
}

.big.ink {
  background: var(--ink);
  color: var(--bg);
}

.big.accent {
  background: var(--lime);
  color: var(--on-tile);
}

.big:hover {
  transform: translateY(-1px);
}

.big:active {
  transform: translateY(1px);
}

.hint {
  font-size: 13px;
  color: var(--ink-3);
}
</style>
