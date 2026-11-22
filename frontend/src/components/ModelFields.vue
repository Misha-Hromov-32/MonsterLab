<script setup lang="ts">
import { ChevronDown } from 'lucide-vue-next'
import { computed, watch } from 'vue'
import { account } from '../lib/account'
const model = defineModel<string>('model', { required: true })
const prompt = defineModel<string>('prompt', { required: true })
defineProps<{ disabled?: boolean }>()
const models = computed(() => account.billing?.image_models ?? [])
watch(
  models,
  (list) => {
    if (list.length && !list.some((m) => m.id === model.value))
      model.value = account.billing?.default_image_model ?? list[0].id
  },
  { immediate: true },
)
</script>
<template>
  <label class="lab-field"
    >Модель генерации<span class="model-select"
      ><select v-model="model" class="input" :disabled="disabled || !models.length">
        <option v-if="!models.length" value="">Загрузка моделей…</option>
        <option v-for="m in models" :key="m.id" :value="m.id">{{ m.title }} · {{ m.cost }} имп.</option></select
      ><ChevronDown :size="16" aria-hidden="true" /></span
  ></label>
  <label class="lab-field"
    >Задание для модели
    <textarea
      v-model="prompt"
      class="input"
      :disabled="disabled"
      maxlength="1800"
      rows="3"
      placeholder="Например, поставьте флакон на светлый камень, сохраните этикетку и добавьте мягкую тень"
    ></textarea>
  </label>
</template>
<style scoped>
.model-select {
  position: relative;
  display: block;
}
.model-select select {
  appearance: none;
  padding-right: 32px;
}
.model-select svg {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
}
.lab-field textarea {
  min-height: 94px;
}
</style>
