<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { Sparkles, Download } from 'lucide-vue-next'
import ModelFields from './ModelFields.vue'
import { api } from '../api'
import { account, paidError, refreshMe, requireLogin } from '../lib/account'
const file = ref<File>(),
  source = ref(''),
  image = ref(''),
  model = ref(''),
  prompt = ref(''),
  busy = ref(false),
  error = ref('')
const price = computed(() => account.billing?.image_models?.find((m) => m.id === model.value)?.cost)
function pick(e: Event) {
  const next = (e.target as HTMLInputElement).files?.[0]
  if (source.value) URL.revokeObjectURL(source.value)
  file.value = next
  source.value = next ? URL.createObjectURL(next) : ''
  image.value = ''
  error.value = ''
}
onUnmounted(() => {
  if (source.value) URL.revokeObjectURL(source.value)
})
async function generate() {
  if (!file.value || !model.value || busy.value) return
  if (!requireLogin('Войдите, чтобы сохранить новую обложку в своём кабинете', generate)) return
  busy.value = true
  error.value = ''
  try {
    image.value = (await api.generatePhoto(file.value, model.value, prompt.value)).image
    await refreshMe()
  } catch (e) {
    error.value = paidError(e, generate) ?? (e as Error).message
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <section id="generator" class="generator">
    <div class="gen-copy">
      <h2>Генератор обложек</h2>
      <p>Загрузите фото товара, выберите модель и опишите, какую обложку хотите получить.</p>
      <figure v-if="image || source">
        <img :src="image || source" :alt="image ? 'Новая обложка' : 'Фото товара'" />
        <figcaption>{{ image ? 'Новая обложка' : 'Исходное фото' }}</figcaption>
      </figure>
      <a v-if="image" :href="image" download="monstorelab-cover.jpg" class="btn pill"
        ><Download :size="16" /> Скачать обложку</a
      >
    </div>
    <form @submit.prevent="generate">
      <label class="field"
        >Фото товара<input
          class="input"
          type="file"
          required
          accept="image/jpeg,image/png,image/webp"
          :disabled="busy"
          @change="pick"
      /></label>
      <ModelFields v-model:model="model" v-model:prompt="prompt" :disabled="busy" />
      <button class="btn primary" :disabled="!file || !model || busy">
        <Sparkles :size="16" />{{ busy ? 'Генерируем…' : 'Сгенерировать обложку'
        }}<template v-if="price"> · {{ price }} имп.</template>
      </button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="busy" role="status">Готовая обложка сохранится в кабинете.</p>
    </form>
  </section>
</template>
<style scoped>
.generator {
  max-width: 1150px;
  margin: clamp(24px, 5vw, 64px) auto;
  padding: clamp(24px, 4vw, 52px);
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 24px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(24px, 5vw, 72px);
  scroll-margin: 20px;
}
h2 {
  font-size: clamp(32px, 4vw, 56px);
  letter-spacing: -0.05em;
  line-height: 1.02;
  margin: 0 0 12px;
}
.gen-copy p {
  max-width: 38ch;
  line-height: 1.55;
}
form {
  display: grid;
  align-content: start;
  gap: 14px;
}
form button {
  justify-self: start;
}
figure {
  margin: 18px 0 12px;
}
img {
  display: block;
  max-width: 100%;
  max-height: 320px;
  border-radius: 12px;
}
figcaption {
  font-size: 12px;
  color: var(--ink-2);
  margin-top: 6px;
}
@media (max-width: 720px) {
  .generator {
    grid-template-columns: 1fr;
    margin: 18px 10px;
  }
}
</style>
