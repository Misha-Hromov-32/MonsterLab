<script setup lang="ts">
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
  <section>
    <h1>Партнёрская программа</h1>
    <p v-if="error" class="err" role="alert">{{ error }}</p>
    <template v-if="data">
      <p>
        Приглашайте новых продавцов. На баланс поступает {{ data.percent }}% от каждой подтверждённой оплаты тех, кто
        зарегистрировался по вашей ссылке.
      </p>
      <button v-if="!data.code" :disabled="busy" class="btn primary" @click="update('/join')">
        Получить партнёрский доступ
      </button>
      <template v-else
        ><label class="field"
          >Ваша ссылка для регистрации<input
            readonly
            class="input"
            :value="origin + '/?ref=' + data.code"
            @focus="($event.target as HTMLInputElement).select()"
        /></label>
        <div class="totals">
          <span
            >Регистраций <b>{{ data.buyers }}</b></span
          ><span
            >Доступно к выплате <b>{{ money(data.available) }}</b></span
          >
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
        <h2>Мои выплаты</h2>
        <p v-if="!data.payouts.length">Выплат пока нет.</p>
        <p v-for="p in data.payouts" :key="p.id">
          № {{ p.id }} · {{ money(p.kopecks) }} · {{ labels[p.status] }} {{ p.reference }}
        </p></template
      ></template
    >
  </section>
</template>
