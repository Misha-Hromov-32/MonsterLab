<script setup lang="ts">
import { ArrowRight, Check, Copy, Link2, Users, Wallet } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
import { request, jsonBody, withAuth } from '../api'
type Dashboard = {
  sbp: boolean
  code: string
  percent: number
  available: number
  buyers: number
  payouts: { id: number; kopecks: number; status: string; reference: string }[]
}
const data = ref<Dashboard>(),
  details = ref(''),
  error = ref(''),
  busy = ref(false)
const method = ref('manual'),
  phone = ref(''),
  bank = ref(''),
  banks = ref<{ bank_id: string; name: string }[]>([])
async function loadBanks() {
  if (method.value !== 'sbp' || banks.value.length) return
  try {
    banks.value = await request('/api/partner/banks', withAuth())
  } catch (e) {
    error.value = (e as Error).message
    method.value = 'manual'
  }
}
const money = (k: number) => (k / 100).toLocaleString('ru-RU', { style: 'currency', currency: 'RUB' })
const labels: Record<string, string> = {
  sending: 'Обрабатывается банком',
  pending: 'Ожидает перевода',
  paid: 'Выплачено',
  declined: 'Отклонено',
}
const origin = location.origin
const copied = ref(false),
  linkInput = ref<HTMLInputElement>()
async function copyLink() {
  if (!data.value?.code) return
  try {
    await navigator.clipboard.writeText(origin + '/?ref=' + data.value.code)
    copied.value = true
  } catch {
    linkInput.value?.focus()
    linkInput.value?.select()
  }
}
async function update(action = '') {
  error.value = ''
  busy.value = true
  try {
    data.value = await request<Dashboard>(
      '/api/partner' + action + (action === '/payouts' && method.value === 'sbp' ? '/sbp' : ''),
      withAuth(
        action
          ? jsonBody(
              'POST',
              action !== '/payouts'
                ? {}
                : method.value === 'sbp'
                  ? { phone: phone.value, bank_id: bank.value }
                  : { details: details.value },
            )
          : {},
      ),
    )
    details.value = ''
    phone.value = ''
    bank.value = ''
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}
onMounted(() => update())
</script>
<template>
  <section class="partner">
    <h1>Партнёрская программа</h1>
    <p v-if="error" class="err" role="alert">
      {{ error }} <button v-if="!data" class="lab-secondary" @click="update()">Повторить</button>
    </p>
    <p v-if="!data && !error" role="status">Загружаем условия программы…</p>
    <template v-if="data">
      <div class="ref-card">
        <div class="commission">
          <Wallet :size="23" /><strong>{{ data.percent }}<small>%</small></strong
          ><span>с каждой оплаты</span>
        </div>
        <div class="ref-content">
          <h2>{{ data.code ? 'Ваша партнёрская ссылка' : 'Приглашайте продавцов' }}</h2>
          <p>
            Отправьте ссылку продавцу. Когда он зарегистрируется и оплатит тариф, вы получите {{ data.percent }}% от
            подтверждённого платежа.
          </p>
          <button v-if="!data.code" class="lab-primary" :disabled="busy" @click="update('/join')">
            <Link2 :size="17" />{{ busy ? 'Создаём ссылку…' : 'Создать партнёрскую ссылку' }} <ArrowRight :size="16" />
          </button>
          <div v-else class="ref-link">
            <input
              ref="linkInput"
              readonly
              class="input"
              aria-label="Ваша ссылка для регистрации"
              :value="origin + '/?ref=' + data.code"
              @focus="($event.target as HTMLInputElement).select()"
            /><button class="lab-secondary" @click="copyLink">
              <component :is="copied ? Check : Copy" :size="16" />{{ copied ? 'Скопировано' : 'Скопировать' }}
            </button>
          </div>
        </div>
      </div>
      <template v-if="data.code">
        <div class="partner-stats">
          <div>
            <Users :size="19" /><span>Регистраций</span><strong>{{ data.buyers }}</strong>
          </div>
          <div>
            <Wallet :size="19" /><span>Доступно к выплате</span><strong>{{ money(data.available) }}</strong>
          </div>
        </div>
        <form v-if="data.available > 0" @submit.prevent="update('/payouts')">
          <label v-if="data.sbp" class="field"
            >Способ выплаты<select class="input" v-model="method" @change="loadBanks">
              <option value="manual">Перевод по реквизитам</option>
              <option value="sbp">СБП через ЮKassa</option>
            </select></label
          >
          <template v-if="method === 'sbp'"
            ><label class="field"
              >Телефон, привязанный к СБП<input
                class="input ym-hide-content"
                v-model="phone"
                inputmode="tel"
                placeholder="79991234567"
                pattern="7[0-9]{10}"
                maxlength="11"
                required
            /></label>
            <label class="field"
              >Банк получателя<select class="input" v-model="bank" required>
                <option value="">Выберите банк</option>
                <option v-for="b in banks" :key="b.bank_id" :value="b.bank_id">{{ b.name }}</option>
              </select></label
            ></template
          >
          <label v-else class="field"
            >Получатель и реквизиты для перевода<textarea
              v-model.trim="details"
              class="input ym-hide-content"
              placeholder="ФИО получателя, банк и телефон для СБП или банковские реквизиты"
              minlength="5"
              maxlength="1000"
              required
            ></textarea></label
          ><button class="btn primary" :disabled="busy">Запросить {{ money(data.available) }}</button>
        </form>
        <div class="payout-list">
          <h2>Мои выплаты</h2>
          <p v-if="!data.payouts.length">Здесь появятся ваши заявки на выплату.</p>
          <p v-for="p in data.payouts" :key="p.id">
            № {{ p.id }} · {{ money(p.kopecks) }} · {{ labels[p.status] }} {{ p.reference }}
          </p>
        </div>
      </template>
    </template>
  </section>
</template>
<style scoped>
.ref-card {
  display: grid;
  grid-template-columns: minmax(150px, 0.55fr) minmax(0, 1.5fr);
  overflow: hidden;
  border-radius: 18px;
  border: 1px solid var(--line);
  background: var(--panel);
}
.commission {
  display: flex;
  flex-direction: column;
  align-items: start;
  justify-content: center;
  padding: clamp(20px, 3vw, 38px);
  color: white;
  background: #371b36;
  gap: 7px;
}
.commission svg {
  color: #f2a4e6;
}
.commission strong {
  font: 770 clamp(46px, 6vw, 80px)/1.1 var(--display-font);
  letter-spacing: -0.065em;
}
.commission small {
  display: inline;
  color: #f5cbe9;
  font-size: 0.45em;
  margin-left: 2px;
}
.commission span {
  color: #efdae9;
}
.ref-content {
  padding: clamp(20px, 3vw, 36px);
  align-self: center;
}
.partner h2 {
  font-size: clamp(20px, 2.4vw, 28px);
  letter-spacing: -0.04em;
  margin: 0;
}
.ref-content p,
.payout-list p {
  color: var(--ink-2);
  margin: 8px 0 20px;
  max-width: 56ch;
}
.ref-link {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.ref-link input {
  flex: 1 1 180px;
}
.partner-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin: 16px 0;
}
.partner-stats > div,
.payout-list {
  padding: 20px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--panel);
}
.partner-stats > div {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 6px 9px;
}
.partner-stats strong {
  grid-column: 2;
  font-size: 26px;
}
.partner-stats svg {
  color: var(--brand);
}
.payout-list p:last-child {
  margin-bottom: 0;
}
@media (max-width: 650px) {
  .ref-card {
    grid-template-columns: 1fr;
  }
  .commission {
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    padding: 14px 20px;
    gap: 12px;
  }
  .commission strong {
    font-size: 42px;
  }
  .commission svg {
    display: none;
  }
  .partner-stats {
    gap: 8px;
  }
  .partner-stats > div {
    padding: 12px;
  }
  .partner-stats span {
    font-size: 13px;
  }
  .partner-stats strong {
    grid-column: 1/-1;
    font-size: 21px;
  }
  .ref-content .lab-primary {
    width: 100%;
  }
}
</style>
