<script setup lang="ts">
import { computed, ref } from 'vue'
import { CreditCard, Loader2 } from 'lucide-vue-next'
import ModalDialog from './ModalDialog.vue'
import { account, checkout, closeDialog, isPaid } from '../lib/account'
import { formatDate, plural } from '../lib/format'
import { features } from '../store'
import type { PlanInfo } from '../lib/types'

const busy = ref('')
const error = ref('')
// аккаунт без почты (вход через VK ID): кассовый чек без адреса не отправить — спрашиваем при оплате
const receiptEmail = ref('')
const needsEmail = computed(() => !!account.user && !account.user.email)

const billing = computed(() => account.billing)
const canPay = computed(() => features.value.billing && !!billing.value?.enabled)
const current = computed(() => (isPaid.value ? account.user?.plan : ''))

defineProps<{ inline?: boolean }>()
const labels: Record<string, string> = {
  analyze: 'Анализ обложки',
  shelf: 'Тест полки',
  expert: 'Визуальный разбор',
  choice: 'Выбор покупателя',
  competitors: 'Подбор конкурентов',
  rules: 'Правила площадок',
  wb: 'Аудит каталога WB',
}
const periods = computed({
  get: () => account.tariffPeriods,
  set: (n: number) => {
    account.tariffPeriods = n
  },
})
const terms = (p: PlanInfo) =>
  p.offers?.find((o) => o.periods === periods.value) ?? { days: p.period_days, price: p.price_rub, discount: 0 }
const days = (p: PlanInfo) => `${terms(p).days} ${plural(terms(p).days, ['день', 'дня', 'дней'])}`
const monthly = computed(() => billing.value?.plans.every((p) => p.period_days === 30))

async function pay(p: PlanInfo) {
  busy.value = p.id
  error.value = await checkout(p.id, receiptEmail.value, periods.value)
  busy.value = ''
}
</script>

<template>
  <component
    :is="inline ? 'section' : ModalDialog"
    :id="inline ? 'plans' : undefined"
    :class="{ publicPlans: inline }"
    title="Тарифы"
    wide
    @close="closeDialog"
    ><h2 v-if="inline">Тарифы</h2>
    <p v-if="!inline && account.reason" class="reason">{{ account.reason }}</p>

    <div v-if="!billing" class="loading"><Loader2 :size="18" class="spin" /> Загружаем условия…</div>
    <template v-else>
      <section class="demo">
        <span class="label">Демо-доступ · после подтверждения почты</span>
        <p>
          {{ billing.demo_credits }} импульсов на весь демо-доступ. Четыре готовых примера можно открыть без
          регистрации.
        </p>
      </section>

      <label class="field"
        >Срок оплаты
        <select v-model.number="periods" class="input" :disabled="!!busy">
          <option :value="1">{{ monthly ? '1 месяц' : '1 период' }}</option>
          <option :value="3">{{ monthly ? '3 месяца' : '3 периода' }} · скидка {{ billing.discount3 ?? 10 }}%</option>
          <option :value="6">{{ monthly ? '6 месяцев' : '6 периодов' }} · скидка {{ billing.discount6 ?? 20 }}%</option>
        </select>
      </label>
      <div class="cols">
        <section
          v-for="p in billing.plans"
          :key="p.id"
          class="col"
          :class="{ featured: p.featured, current: current === p.id }"
        >
          <header>
            <span class="name">{{ p.title }}</span>
            <span v-if="current === p.id" class="tag cur">ваш тариф</span>
            <span v-else-if="p.featured" class="tag hot">популярный</span>
          </header>
          <p v-if="p.note" class="pnote">{{ p.note }}</p>
          <div class="price">
            <strong class="num">{{ terms(p).price.toLocaleString('ru-RU') }} ₽</strong>
            <span>/ {{ days(p) }}</span>
          </div>
          <strong class="grant"
            >{{ p.credits?.toLocaleString('ru-RU') }} импульсов каждые {{ p.period_days }} дней</strong
          >
          <button
            v-if="canPay"
            class="btn wide"
            :class="p.featured ? 'primary' : 'pill'"
            :disabled="!!busy"
            @click="pay(p)"
          >
            <Loader2 v-if="busy === p.id" :size="15" class="spin" /><CreditCard v-else :size="15" />
            {{ current === p.id ? 'Продлить' : 'Выбрать' }}
          </button>
        </section>
      </div>

      <label v-if="canPay && needsEmail" class="receipt field">
        <span class="flabel">Почта для чека</span>
        <input v-model="receiptEmail" class="input" type="email" autocomplete="email" inputmode="email" />
      </label>

      <details class="costs">
        <summary>Сколько импульсов стоит действие</summary>
        <dl>
          <template v-for="(title, key) in labels" :key="key"
            ><dt>{{ title }}</dt>
            <dd>{{ billing.costs?.[key] }}</dd></template
          >
          <template v-for="m in billing.image_models" :key="m.id"
            ><dt>{{ m.title }}</dt>
            <dd>{{ m.cost }}</dd></template
          >
        </dl>
      </details>
      <p v-if="error" class="err" role="alert">{{ error }}</p>

      <p class="note">
        <template v-if="isPaid && account.user?.pro_until">
          Сейчас действует «{{ account.user.plan_title }}» до {{ formatDate(account.user.pro_until) }}.
        </template>
        Импульсы начисляются на каждый базовый период тарифа. При продлении срок суммируется. Предоплаченные периоды
        действуют последовательно, со своими тарифами.
        <template v-if="canPay && billing?.provider === 'tochka'">Оплата через Точку Банк: картой или по СБП.</template>
        <template v-else-if="canPay">Оплата через ЮKassa: картой, SberPay или ЮMoney.</template>
        <template v-else>Оплата пока недоступна.</template>
        {{ ' ' }}<a href="/legal#terms" target="_blank" rel="noopener">Условия и возврат</a>
      </p>
    </template>
  </component>
</template>

<style scoped>
.publicPlans {
  max-width: 1180px;
  margin: 0 auto;
  padding: clamp(32px, 6vw, 84px) clamp(18px, 4vw, 50px);
  display: grid;
  gap: 20px;
  scroll-margin-top: 24px;
}
.publicPlans h2 {
  font-size: clamp(32px, 5vw, 62px);
  letter-spacing: -0.045em;
  margin: 0;
}
.grant {
  font-size: 15px;
  line-height: 1.45;
}
.costs summary {
  cursor: pointer;
  font-weight: 650;
}
.costs dl {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 6px 20px;
  max-width: 540px;
}
.costs dd {
  font-variant-numeric: tabular-nums;
}
.receipt {
  max-width: 340px;
}

.flabel {
  font-size: 12px;
  color: var(--ink-2);
}

.reason {
  margin: -6px 0 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--lime-soft);
  font-size: 13px;
  line-height: 1.45;
}

.loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--ink-3);
}

.demo {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: var(--panel-2);
}

.demo p {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--ink-2);
}

.cols {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
}

.col {
  display: grid;
  grid-template-rows: auto auto auto auto 1fr auto;
  gap: 10px;
  padding: 16px 14px 14px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--bg);
}

.col.featured {
  border-color: color-mix(in srgb, var(--lime) 60%, var(--line-strong));
  background: var(--lime-soft);
}

.col.current {
  border-color: var(--ink);
}

.col header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.name {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.tag {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 500;
  white-space: nowrap;
}

.tag.hot {
  background: var(--lime);
  color: var(--on-tile);
}

.tag.cur {
  background: var(--ink);
  color: var(--bg);
}

.pnote {
  margin: -4px 0 0;
  font-size: 12px;
  color: var(--ink-3);
}

.price {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
}

.price strong {
  font-size: 26px;
  font-weight: 300;
  letter-spacing: -0.04em;
}

.price span {
  font-size: 12px;
  color: var(--ink-3);
}

ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  align-content: start;
  gap: 7px;
}

li {
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 7px;
  font-size: 12.5px;
  line-height: 1.35;
  color: var(--ink-2);
}

li svg {
  margin-top: 1px;
  color: var(--good);
}

.wide {
  justify-content: center;
  height: 38px;
}

.note {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--ink-3);
}

.note a {
  color: var(--ink-2);
  text-underline-offset: 2px;
}

.err {
  margin: 0;
  color: var(--bad);
  font-size: 13px;
}
</style>
