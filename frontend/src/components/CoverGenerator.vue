<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { Sparkles, Download, Upload, ImagePlus, Replace, Loader2 } from 'lucide-vue-next'
import { site } from '../store'
import ModelFields from './ModelFields.vue'
import { api } from '../api'
import { account, openTariffs, paidError, refreshMe, requireLogin } from '../lib/account'
const file = ref<File>(),
  source = ref(''),
  image = ref(''),
  model = ref(''),
  prompt = ref(''),
  busy = ref(false),
  error = ref('')
const price = computed(() => account.billing?.image_models?.find((m) => m.id === model.value)?.cost)
const balance = computed(() => account.user?.wallet?.remaining)
const shortfall = computed(
  () => balance.value !== undefined && price.value !== undefined && price.value > balance.value,
)
const affordable = computed(
  () => account.billing?.image_models?.filter((m) => m.cost <= (balance.value ?? 0)).sort((a, b) => b.cost - a.cost)[0],
)
const input = ref<HTMLInputElement>()
const over = ref(false)
const sample = computed(
  () => site.data?.examples.find((e) => e.variants.length)?.variants[0].url ?? site.showcase?.card.url,
)
function pick(next?: File) {
  over.value = false
  if (!next || busy.value) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(next.type) || next.size > 25 * 1024 * 1024) {
    error.value = 'Выберите изображение JPG, PNG или WebP до 25 МБ.'
    return
  }
  if (source.value) URL.revokeObjectURL(source.value)
  file.value = next
  source.value = URL.createObjectURL(next)
  image.value = ''
  error.value = ''
}
onUnmounted(() => {
  if (source.value) URL.revokeObjectURL(source.value)
})
async function generate() {
  if (!file.value || !model.value || busy.value || shortfall.value) return
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
  <section
    id="generator"
    class="lab-section generator"
    data-own-drop
    @dragenter.stop.prevent="over = true"
    @dragover.stop.prevent
    @dragleave.stop.prevent="over = false"
    @drop.stop.prevent="pick($event.dataTransfer?.files[0])"
  >
    <h2 class="lab-title">Генератор обложек</h2>
    <div class="gen-grid">
      <div class="workbench" :class="{ over }">
        <div class="art">
          <div class="frame" v-if="image || source || sample">
            <img
              :src="image || source || sample"
              :alt="image ? 'Сгенерированная обложка' : source ? 'Загруженное фото товара' : 'Пример товарной обложки'"
              :class="{ example: !source }"
            />
          </div>
          <ImagePlus v-else :size="64" /><span class="caption">{{
            image ? 'Новая обложка' : source ? 'Исходное фото' : 'Пример обложки'
          }}</span>
        </div>
        <div class="upload-bar">
          <div>
            <strong>{{ file?.name ?? 'Фото вашего товара' }}</strong
            ><small>JPG, PNG, WebP · до 25 МБ</small>
          </div>
          <button class="lab-secondary" :disabled="busy" @click="input?.click()">
            <component :is="file ? Replace : Upload" :size="16" />{{ file ? 'Заменить' : 'Загрузить фото' }}
          </button>
        </div>
        <input
          ref="input"
          type="file"
          hidden
          accept="image/jpeg,image/png,image/webp"
          @change="
            pick(($event.target as HTMLInputElement).files?.[0])
            ;($event.target as HTMLInputElement).value = ''
          "
        />
      </div>
      <form class="gen-form" @submit.prevent="generate">
        <h3>Настройки обложки</h3>
        <ModelFields v-model:model="model" v-model:prompt="prompt" :disabled="busy" />
        <div class="submit-area">
          <p v-if="price" class="cost">
            Стоимость генерации <strong>{{ price }} имп.</strong>
          </p>
          <p v-if="balance !== undefined" class="cost">
            На вашем балансе <strong>{{ balance }} имп.</strong>
          </p>
          <div v-if="shortfall" class="shortfall">
            <span>Для этой модели не хватает {{ (price ?? 0) - (balance ?? 0) }} имп.</span>
            <button v-if="affordable" type="button" @click="model = affordable.id">
              Выбрать {{ affordable.title }} за {{ affordable.cost }} имп.
            </button>
            <button v-else type="button" @click="openTariffs()">Выбрать тариф</button>
          </div>
          <button class="lab-primary" :disabled="!file || !model || busy || shortfall">
            <component :is="busy ? Loader2 : Sparkles" :size="18" :class="{ spin: busy }" />{{
              busy ? 'Генерируем…' : 'Сгенерировать обложку'
            }}
          </button>
          <p v-if="error" class="lab-error" role="alert">{{ error }}</p>
          <p v-if="busy" role="status">Готовая обложка сохранится в кабинете.</p>
          <a v-if="image" :href="image" download="monstorelab-cover.jpg" class="lab-secondary"
            ><Download :size="16" /> Скачать результат</a
          >
        </div>
      </form>
    </div>
  </section>
</template>
<style scoped>
.gen-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: clamp(14px, 2vw, 28px);
  margin-top: clamp(20px, 3vw, 38px);
}
.workbench,
.gen-form {
  border-radius: 20px;
  min-width: 0;
  overflow: hidden;
}
.workbench {
  display: grid;
  grid-template-rows: minmax(220px, 1fr) auto;
  background: #2b1128;
}
.workbench.over {
  outline: 3px solid var(--brand);
  outline-offset: 3px;
}
.art {
  min-height: 255px;
  display: grid;
  align-items: center;
  justify-items: center;
  position: relative;
  overflow: hidden;
  padding: 23px;
  color: #f496e6;
  background:
    radial-gradient(ellipse at 65% 12%, #713263 0%, transparent 65%),
    repeating-linear-gradient(0deg, transparent 0 26px, #ffffff09 27px 28px),
    repeating-linear-gradient(90deg, transparent 0 26px, #ffffff09 27px 28px), #2b1128;
}
.frame {
  position: relative;
  z-index: 1;
  max-width: 78%;
  filter: drop-shadow(0 13px 15px #19081288);
}
.frame img {
  display: block;
  max-width: 100%;
  height: clamp(200px, 19vw, 285px);
  object-fit: contain;
  border-radius: 8px;
}
.frame img.example {
  transform: rotate(-5deg);
  border: 3px solid #f6c8f0;
}
.caption {
  position: absolute;
  bottom: 12px;
  left: 14px;
  background: #220d20;
  color: #fcddf7;
  border: 1px solid #825175;
  padding: 5px 10px;
  font-size: 12px;
  border-radius: 20px;
  z-index: 2;
}
.upload-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 17px 20px;
  color: #fff;
  background: #251023;
}
.upload-bar > div {
  min-width: 0;
  flex: 1 1 140px;
}
.upload-bar strong,
.upload-bar small {
  display: block;
  overflow-wrap: anywhere;
}
.upload-bar small {
  color: #d7bfd3;
  margin-top: 4px;
}
.upload-bar .lab-secondary {
  background: #fff;
  color: #33112d;
  border-color: white;
}
.gen-form {
  border: 1px solid var(--line);
  padding: clamp(18px, 2.4vw, 32px);
  background: var(--panel);
  display: grid;
  align-content: start;
  gap: 17px;
}
.gen-form h3 {
  font-size: clamp(19px, 2vw, 26px);
  letter-spacing: -0.04em;
  margin: 0;
}
.submit-area {
  display: grid;
  gap: 10px;
}
.shortfall {
  display: grid;
  gap: 6px;
  justify-items: start;
  padding: 10px 12px;
  background: var(--panel-2);
  border-radius: 9px;
  font-size: 13px;
}
.shortfall button {
  padding: 0;
  background: none;
  border: 0;
  text-decoration: underline;
  text-underline-offset: 3px;
  color: var(--ink);
  font-weight: 600;
  text-align: left;
}
.submit-area p {
  margin: 0;
}
.cost {
  display: flex;
  justify-content: space-between;
  color: var(--ink-2);
  font-size: 14px;
}
.cost strong {
  color: var(--ink);
}
.submit-area .lab-primary {
  min-height: 46px;
}
@media (max-width: 740px) {
  .gen-grid {
    grid-template-columns: 1fr;
  }
  .art {
    min-height: 205px;
  }
  .frame img {
    height: 180px;
  }
  .upload-bar {
    padding: 14px;
  }
  .gen-form {
    gap: 14px;
  }
}
</style>
