<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { Loader2, MailCheck } from 'lucide-vue-next'
import ModalDialog from './ModalDialog.vue'
import Segmented from './Segmented.vue'
import {
  account,
  closeDialog,
  OAUTH_TITLES,
  requestReset,
  resendLetter,
  setNewPassword,
  signIn,
  startOAuth,
  type AuthMode,
} from '../lib/account'
import { oauthProviders, toast } from '../store'
import type { OAuthProvider } from '../lib/types'

const MIN_PASSWORD = 8
const RESEND_SECONDS = 60

const tabs: { id: AuthMode; title: string }[] = [
  { id: 'login', title: 'Вход' },
  { id: 'register', title: 'Регистрация' },
]

const TITLES: Record<AuthMode, string> = {
  login: 'Вход',
  register: 'Регистрация',
  sent: 'Проверьте почту',
  forgot: 'Восстановление пароля',
  reset: 'Новый пароль',
}

const email = ref('')
const password = ref('')
// две отдельные галочки: согласие на обработку персональных данных по закону — отдельный документ
const acceptTerms = ref(false)
const acceptData = ref(false)
const error = ref('')
const busy = ref(false)

const mode = computed(() => account.authMode)
const withTabs = computed(() => mode.value === 'login' || mode.value === 'register')
const needsEmail = computed(() => withTabs.value || mode.value === 'forgot')
const needsPassword = computed(() => withTabs.value || mode.value === 'reset')
const newPassword = computed(() => mode.value === 'register' || mode.value === 'reset')

const canSubmit = computed(
  () =>
    !busy.value &&
    (!needsEmail.value || email.value.trim().length > 2) &&
    (!needsPassword.value || password.value.length >= (newPassword.value ? MIN_PASSWORD : 1)) &&
    (mode.value !== 'register' || (acceptTerms.value && acceptData.value)),
)

const submitTitle = computed(
  () =>
    ({ login: 'Войти', register: 'Создать аккаунт', forgot: 'Отправить ссылку', reset: 'Сохранить и войти' })[
      mode.value as Exclude<AuthMode, 'sent'>
    ],
)

function go(next: AuthMode) {
  error.value = ''
  account.reason = ''
  account.authMode = next
}

// «Отправить ещё раз» — не чаще раза в минуту: так же ограничивает и сервер
const cooldown = ref(0)
let timer: ReturnType<typeof setInterval> | undefined

function startCooldown() {
  cooldown.value = RESEND_SECONDS
  clearInterval(timer)
  timer = setInterval(() => {
    if (--cooldown.value <= 0) clearInterval(timer)
  }, 1000)
}
onUnmounted(() => clearInterval(timer))

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  error.value = ''
  const current = mode.value
  const who = email.value.trim()
  if (current === 'forgot') error.value = await requestReset(who)
  else if (current === 'reset') error.value = await setNewPassword(password.value)
  else
    error.value = await signIn(current as 'login' | 'register', who, password.value, {
      terms: acceptTerms.value,
      personalData: acceptData.value,
    })
  busy.value = false
  if (error.value) return
  password.value = ''
  if (account.authMode === 'sent') startCooldown()
  else if (current === 'reset') toast('Пароль изменён — вы вошли')
  else if (current === 'login') toast(`Вы вошли как ${who}`)
}

// вход через VK ID / Яндекс ID: при регистрации — только с отмеченными согласиями, как и по почте
const consentGiven = computed(() => acceptTerms.value && acceptData.value)
const oauthBusy = ref(false)

async function viaProvider(provider: OAuthProvider) {
  if (oauthBusy.value || (mode.value === 'register' && !consentGiven.value)) return
  oauthBusy.value = true
  error.value = await startOAuth(provider, { terms: acceptTerms.value, personalData: acceptData.value })
  if (error.value) oauthBusy.value = false // при успехе браузер уже уходит на страницу провайдера
}

async function resend() {
  if (busy.value || cooldown.value) return
  busy.value = true
  error.value = await resendLetter()
  busy.value = false
  if (!error.value) {
    startCooldown()
    toast('Письмо отправлено ещё раз')
  }
}
</script>

<template>
  <ModalDialog :title="TITLES[mode]" @close="closeDialog">
    <p v-if="account.reason" class="reason">{{ account.reason }}</p>

    <!-- письмо отправлено -->
    <div v-if="mode === 'sent'" class="sent">
      <span class="sent-icon" aria-hidden="true"><MailCheck :size="22" /></span>
      <p class="sent-text ym-hide-content">
        <template v-if="account.letter === 'verify'">
          Мы отправили ссылку на <strong>{{ account.pendingEmail }}</strong
          >. Нажмите «Подтвердить почту» в письме.
        </template>
        <template v-else>
          Если аккаунт с адресом <strong>{{ account.pendingEmail }}</strong> есть, ссылка для нового пароля уже в почте.
          Она действует час.
        </template>
      </p>
      <p class="hint-line">Письма нет? Проверьте «Спам» или отправьте ещё раз.</p>
      <p v-if="error" class="err" role="alert">{{ error }}</p>
      <button class="btn pill wide" type="button" :disabled="busy || cooldown > 0" @click="resend">
        <Loader2 v-if="busy" :size="15" class="spin" />
        {{ cooldown ? `Отправить ещё раз через ${cooldown} с` : 'Отправить ещё раз' }}
      </button>
      <button class="linkbtn" type="button" @click="go(account.letter === 'verify' ? 'register' : 'forgot')">
        Указать другой адрес
      </button>
    </div>

    <template v-else>
      <div v-if="withTabs" class="modes">
        <Segmented
          v-model="account.authMode"
          :options="tabs"
          label="Вход или регистрация"
          @update:model-value="error = ''"
        />
      </div>
      <p v-else-if="mode === 'forgot'" class="lead">Отправим ссылку для смены пароля.</p>
      <p v-else class="lead">Введите новый пароль.</p>

      <form class="form" novalidate @submit.prevent="submit">
        <label v-if="needsEmail" class="field">
          <span class="flabel">Email</span>
          <input
            v-model="email"
            class="input ym-disable-keys"
            type="email"
            name="email"
            autocomplete="email"
            inputmode="email"
            required
            data-autofocus
          />
        </label>
        <label v-if="needsPassword" class="field">
          <span class="flabel">{{ mode === 'reset' ? 'Новый пароль' : 'Пароль' }}</span>
          <input
            v-model="password"
            class="input"
            type="password"
            name="password"
            :autocomplete="newPassword ? 'new-password' : 'current-password'"
            :minlength="newPassword ? MIN_PASSWORD : undefined"
            required
            aria-describedby="pw-hint"
            :data-autofocus="mode === 'reset' ? '' : undefined"
          />
          <span id="pw-hint" class="hint">{{ newPassword ? `Не короче ${MIN_PASSWORD} символов` : '' }}</span>
        </label>

        <div v-if="mode === 'register'" class="consents">
          <label class="check">
            <input v-model="acceptTerms" type="checkbox" required />
            <span>
              Принимаю
              <a href="/legal#terms" target="_blank" rel="noopener">пользовательское соглашение</a>
              и
              <a href="/legal#privacy" target="_blank" rel="noopener">политику обработки персональных данных</a>
            </span>
          </label>
          <label class="check">
            <input v-model="acceptData" type="checkbox" required />
            <span>
              Даю
              <a href="/legal#consent" target="_blank" rel="noopener">согласие на обработку персональных данных</a>
            </span>
          </label>
        </div>

        <p v-if="error" class="err" role="alert">{{ error }}</p>

        <button class="btn primary wide" type="submit" :disabled="!canSubmit">
          <Loader2 v-if="busy" :size="15" class="spin" />
          {{ submitTitle }}
        </button>
      </form>

      <div v-if="withTabs && oauthProviders.length" class="oauth">
        <span class="or">или</span>
        <button
          v-for="p in oauthProviders"
          :key="p"
          type="button"
          class="btn wide oauth-btn"
          :class="p"
          :disabled="oauthBusy || (mode === 'register' && !consentGiven)"
          @click="viaProvider(p)"
        >
          <span class="oauth-logo" aria-hidden="true">{{ p === 'vk' ? 'VK' : 'Я' }}</span>
          {{ mode === 'register' ? 'Зарегистрироваться' : 'Войти' }} с {{ OAUTH_TITLES[p] }}
        </button>
        <p v-if="mode === 'register' && !consentGiven" class="hint-line">
          Отметьте согласия выше — без них аккаунт не создаётся.
        </p>
      </div>

      <button v-if="mode === 'login'" class="linkbtn" type="button" @click="go('forgot')">Забыли пароль?</button>
      <button v-else-if="mode === 'forgot'" class="linkbtn" type="button" @click="go('login')">
        Вспомнили пароль? Войти
      </button>

      <p v-if="withTabs" class="foot">
        Для работы нужен аккаунт. Регистрация бесплатная.
        <a href="/legal" target="_blank" rel="noopener">Правила сервиса</a>
      </p>
    </template>
  </ModalDialog>
</template>

<style scoped>
.reason {
  margin: -6px 0 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--lime-soft);
  font-size: 13px;
  line-height: 1.45;
}

.lead {
  margin: -4px 0 0;
  font-size: 13.5px;
  line-height: 1.5;
  color: var(--ink-2);
}

.form {
  display: grid;
  gap: 12px;
}

.flabel {
  font-size: 12px;
  color: var(--ink-2);
}

.input {
  height: 40px;
  /* 16px — иначе iOS приближает страницу при фокусе на поле */
  font-size: 16px;
}

.hint {
  min-height: 1em;
  font-size: 11px;
  color: var(--ink-3);
}

.hint:empty {
  display: none;
}

.err {
  margin: 0;
  color: var(--bad);
  font-size: 13px;
}

.wide {
  justify-content: center;
  height: 42px;
  font-size: 14.5px;
}

.linkbtn {
  justify-self: center;
  padding: 2px 4px;
  border: 0;
  background: none;
  color: var(--ink-2);
  font-size: 13px;
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-color: var(--line-strong);
  cursor: pointer;
}

.linkbtn:hover {
  color: var(--ink);
  text-decoration-color: currentColor;
}

.sent {
  display: grid;
  gap: 12px;
}

.sent-icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: var(--lime);
  color: var(--on-tile);
}

.sent-text {
  margin: 0;
  font-size: 14.5px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.hint-line {
  margin: 0;
  font-size: 12.5px;
  color: var(--ink-3);
}

.oauth {
  display: grid;
  gap: 8px;
}

.or {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--ink-3);
}

.or::before,
.or::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--line);
}

.oauth-btn {
  gap: 10px;
  border: 0;
  color: #fff;
  font-weight: 500;
}

.oauth-btn:disabled {
  opacity: 0.45;
}

/* цвета кнопок — из гайдлайнов VK ID и Яндекс ID */
.oauth-btn.vk {
  background: #0077ff;
}

.oauth-btn.vk:hover:not(:disabled) {
  background: #0069e0;
}

.oauth-btn.yandex {
  background: #000;
}

.oauth-btn.yandex:hover:not(:disabled) {
  background: #222;
}

.oauth-logo {
  display: grid;
  place-items: center;
  min-width: 26px;
  height: 22px;
  padding: 0 4px;
  border-radius: 6px;
  background: #fff;
  color: #0077ff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.yandex .oauth-logo {
  min-width: 22px;
  border-radius: 50%;
  background: #fc3f1d;
  color: #fff;
  font-size: 13px;
}

.consents {
  display: grid;
  gap: 8px;
  margin-top: 2px;
}

.check {
  display: grid;
  grid-template-columns: 18px 1fr;
  gap: 10px;
  align-items: start;
  font-size: 13px;
  line-height: 1.45;
  color: var(--ink-2);
  cursor: pointer;
}

.check input {
  width: 18px;
  height: 18px;
  margin: 0;
  accent-color: var(--ink);
  cursor: pointer;
}

.check a,
.foot a {
  color: var(--ink);
  text-underline-offset: 2px;
  text-decoration-color: var(--line-strong);
}

.check a:hover,
.foot a:hover {
  text-decoration-color: currentColor;
}

.foot {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--ink-3);
}

/* вкладки «Вход / Регистрация» — на всю ширину окна */
.modes :deep(.seg) {
  display: flex;
}

.modes :deep(.seg button) {
  flex: 1;
}
</style>
