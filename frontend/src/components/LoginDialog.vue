<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { Loader2, MailCheck } from 'lucide-vue-next'
import ModalDialog from './ModalDialog.vue'
import Segmented from './Segmented.vue'
import { account, closeDialog, requestReset, resendLetter, setNewPassword, signIn, type AuthMode } from '../lib/account'
import { toast } from '../store'

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
    (!needsPassword.value || password.value.length >= (newPassword.value ? MIN_PASSWORD : 1)),
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
  else error.value = await signIn(current as 'login' | 'register', who, password.value)
  busy.value = false
  if (error.value) return
  password.value = ''
  if (account.authMode === 'sent') startCooldown()
  else if (current === 'reset') toast('Пароль изменён — вы вошли')
  else if (current === 'login') toast(`Вы вошли как ${who}`)
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
      <p class="sent-text">
        <template v-if="account.letter === 'verify'">
          Мы отправили ссылку на <strong>{{ account.pendingEmail }}</strong
          >. Откройте письмо и нажмите «Подтвердить почту» — вход произойдёт сам.
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
      <p v-else-if="mode === 'forgot'" class="lead">Пришлём ссылку, по которой можно задать новый пароль.</p>
      <p v-else class="lead">Придумайте новый пароль — после сохранения вы сразу войдёте.</p>

      <form class="form" novalidate @submit.prevent="submit">
        <label v-if="needsEmail" class="field">
          <span class="flabel">Email</span>
          <input
            v-model="email"
            class="input"
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

        <p v-if="error" class="err" role="alert">{{ error }}</p>

        <button class="btn primary wide" type="submit" :disabled="!canSubmit">
          <Loader2 v-if="busy" :size="15" class="spin" />
          {{ submitTitle }}
        </button>
      </form>

      <button v-if="mode === 'login'" class="linkbtn" type="button" @click="go('forgot')">Забыли пароль?</button>
      <button v-else-if="mode === 'forgot'" class="linkbtn" type="button" @click="go('login')">
        Вспомнили пароль? Войти
      </button>

      <p v-if="withTabs" class="foot">
        Проверка обложек, тест полки и примеры доступны после входа. Регистрация бесплатная — нужен только email, его мы
        подтвердим письмом.
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
