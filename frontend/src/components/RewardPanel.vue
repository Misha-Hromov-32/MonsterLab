<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Check, Copy, Send } from 'lucide-vue-next'
import { request, jsonBody, withAuth } from '../api'
import { refreshMe } from '../lib/account'
import { toast } from '../store'
type Rewards = {
  signup: number
  email: number
  verified: boolean
  legacy: boolean
  social: number
  link: string
  claim: null | { status: string; url: string; amount: number }
}
const info = ref<Rewards>(),
  url = ref(''),
  error = ref(''),
  busy = ref(false)
async function load() {
  error.value = ''
  try {
    info.value = await request('/api/rewards', withAuth())
  } catch (e) {
    error.value = (e as Error).message
  }
}
async function submit() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    info.value = await request('/api/rewards/share', withAuth(jsonBody('POST', { url: url.value.trim() })))
    url.value = ''
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
async function copy() {
  try {
    await navigator.clipboard.writeText(info.value!.link)
    toast('Ссылка скопирована')
  } catch {
    toast('Выделите ссылку и скопируйте её')
  }
}
const email = ref(''),
  code = ref(''),
  sent = ref(false)
async function linkEmail(confirm: boolean) {
  busy.value = true
  error.value = ''
  try {
    if (confirm) {
      info.value = await request(
        '/api/rewards/email/confirm',
        withAuth(jsonBody('POST', { email: email.value, code: code.value })),
      )
      await refreshMe()
      toast('Почта подтверждена')
    } else {
      await request('/api/rewards/email', withAuth(jsonBody('POST', { email: email.value })))
      sent.value = true
      code.value = ''
    }
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
<template>
  <div class="reward-stack">
    <p v-if="!info && !error" role="status">Загружаем бонусы…</p>
    <template v-if="info">
      <div class="reward-row">
        <div>
          <h3>Регистрация</h3>
          <small><Check :size="14" /> {{ info.legacy ? 'Учтено в стартовом балансе' : 'Начислено' }}</small>
        </div>
        <b>+{{ info.signup }}</b>
      </div>
      <div class="reward-row">
        <div>
          <h3>Подтверждение почты</h3>
          <small
            ><Check v-if="info.verified" :size="14" />{{
              info.verified
                ? info.legacy
                  ? 'Учтено в стартовом балансе'
                  : 'Начислено'
                : 'Требуется подтверждённый адрес'
            }}</small
          >
        </div>
        <b>+{{ info.email }}</b>
      </div>
      <form v-if="!info.verified" class="social-reward" @submit.prevent="linkEmail(sent)">
        <label class="lab-field"
          >Ваша почта<input
            v-model="email"
            required
            type="email"
            autocomplete="email"
            maxlength="254"
            @input="sent = false" /></label
        ><template v-if="sent"
          ><p>Если адрес свободен, на него отправлен код. Он действует 10 минут.</p>
          <label class="lab-field"
            >Код из письма<input
              v-model="code"
              required
              inputmode="numeric"
              autocomplete="one-time-code"
              pattern="[0-9]{8}"
              maxlength="8" /></label></template
        ><button class="lab-secondary" :disabled="busy">{{ sent ? 'Подтвердить почту' : 'Получить код' }}</button
        ><button v-if="sent" type="button" class="lab-secondary" :disabled="busy" @click="linkEmail(false)">
          Отправить ещё раз
        </button>
      </form>
      <section class="social-reward">
        <header class="reward-row">
          <div>
            <h3>Публикация в соцсетях</h3>
            <small>Один раз за публичный пост</small>
          </div>
          <b>+{{ info.claim?.amount ?? info.social }}</b>
        </header>
        <p v-if="info.claim?.status === 'approved'" role="status">Публикация подтверждена. Импульсы на балансе.</p>
        <p v-else-if="info.claim?.status === 'pending'" role="status">
          Публикация на проверке. После одобрения импульсы появятся на балансе.
          <a :href="info.claim.url" target="_blank" rel="noopener noreferrer">Открыть пост ↗</a>
        </p>
        <template v-else
          ><p v-if="info.claim" role="status">Пост отклонён. Проверьте, что он общедоступен и содержит вашу ссылку.</p>
          <p>
            Опубликуйте свою ссылку на стене VK или в публичном Telegram-канале. Затем пришлите адрес записи на
            проверку.
          </p>
          <label class="lab-field"
            >Ваша ссылка<span class="copy-row"
              ><input :value="info.link" readonly @focus="($event.target as HTMLInputElement).select()" /><button
                type="button"
                aria-label="Скопировать ссылку"
                class="lab-secondary"
                @click="copy"
              >
                <Copy :size="18" /></button></span
          ></label>
          <div class="share-links">
            <a
              :href="'https://vk.com/share.php?url=' + encodeURIComponent(info.link)"
              target="_blank"
              rel="noopener noreferrer"
              >Поделиться в VK ↗</a
            ><a
              :href="'https://t.me/share/url?url=' + encodeURIComponent(info.link)"
              target="_blank"
              rel="noopener noreferrer"
              >В Telegram ↗</a
            >
          </div>
          <form @submit.prevent="submit">
            <label class="lab-field"
              >Ссылка на опубликованный пост<input
                v-model="url"
                type="url"
                required
                maxlength="500"
                placeholder="https://…" /></label
            ><button class="lab-primary" :disabled="busy || !url.trim()">
              <Send :size="16" /> {{ busy ? 'Отправляем…' : 'Отправить на проверку' }}
            </button>
          </form></template
        >
      </section>
    </template>
    <p v-if="error" class="lab-error" role="alert">
      {{ error }} <button v-if="!info" class="lab-secondary" @click="load">Повторить</button>
    </p>
  </div>
</template>
<style scoped>
.reward-stack {
  display: grid;
  gap: 12px;
}
.reward-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 24px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 16px;
}
.reward-row b {
  font: 800 26px var(--display-font);
  color: var(--brand);
}
h3 {
  font-size: 18px;
  margin: 0 0 4px;
}
small {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--ink-2);
}
.social-reward {
  padding: 24px;
  background: var(--panel);
  border-radius: 16px;
  border: 1px solid var(--line);
}
.social-reward header {
  border: 0;
  padding: 0;
}
.social-reward p {
  line-height: 1.55;
}
.copy-row {
  display: flex;
  gap: 6px;
}
.share-links {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin: 12px 0 22px;
}
.share-links a,
.social-reward a {
  color: var(--ink);
  text-underline-offset: 4px;
}
form {
  display: grid;
  gap: 12px;
  justify-items: start;
}
form label {
  width: 100%;
}
</style>
