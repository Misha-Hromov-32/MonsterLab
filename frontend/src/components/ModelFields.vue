<script setup lang="ts">
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
  <label class="field"
    >Модель<select v-model="model" class="input" :disabled="disabled || !models.length">
      <option v-if="!models.length" value="">Загрузка моделей…</option>
      <option v-for="m in models" :key="m.id" :value="m.id">{{ m.title }} · {{ m.cost }} имп.</option>
    </select></label
  >
  <label class="field"
    >Ваше задание
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
