<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowRight, Zap, Loader2 } from 'lucide-vue-next'
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
    :class="{ 'lab-section': inline }"
    title="Тарифы"
    wide
    @close="closeDialog"
    ><h2 v-if="inline" class="lab-title">Тарифы</h2>
    <p v-if="!inline && account.reason" class="reason">{{ account.reason }}</p>

    <div v-if="!billing" class="loading"><Loader2 :size="18" class="spin" /> Загружаем условия…</div>
    <template v-else>
      <div class="term-picker" role="group" aria-label="Срок оплаты">
        <button
          v-for="n in [1, 3, 6]"
          :key="n"
          type="button"
          :aria-pressed="periods === n"
          :disabled="!!busy"
          @click="periods = n"
        >
          {{ n }}
          {{
            monthly
              ? n === 1
                ? 'месяц'
                : n === 3
                  ? 'месяца'
                  : 'месяцев'
              : n === 1
                ? 'период'
                : n === 3
                  ? 'периода'
                  : 'периодов'
          }}<small v-if="n !== 1">−{{ n === 3 ? (billing.discount3 ?? 10) : (billing.discount6 ?? 20) }}%</small>
        </button>
      </div>
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
            ><Zap :size="17" />{{ p.credits?.toLocaleString('ru-RU') }} импульсов каждые
            {{ p.period_days }} дней</strong
          >
          <button v-if="canPay" class="plan-buy" :disabled="!!busy" @click="pay(p)">
            <Loader2 v-if="busy === p.id" :size="15" class="spin" />
            {{ current === p.id ? 'Продлить тариф' : 'Выбрать тариф' }} <ArrowRight :size="16" />
          </button>
        </section>
      </div>

      <label v-if="canPay && needsEmail" class="receipt lab-field">
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
        При оплате нескольких периодов импульсы поступают в начале каждого периода.
        <template v-if="canPay && billing?.provider === 'tochka'">Оплата через Точку Банк: картой или по СБП.</template>
        <template v-else-if="canPay">Оплата через ЮKassa: картой, SberPay или ЮMoney.</template>
        <template v-else>Оплата пока недоступна.</template>
        {{ ' ' }}<a href="/legal#terms" target="_blank" rel="noopener">Условия и возврат</a>
      </p>
    </template>
  </component>
</template>

<style scoped>
.term-picker {
  display: inline-flex;
  max-width: 100%;
  width: fit-content;
  gap: 3px;
  padding: 4px;
  background: var(--panel-2);
  border: 1px solid var(--line);
  border-radius: 12px;
  margin: 20px 0;
}
.term-picker button {
  border: 0;
  background: transparent;
  color: var(--ink-2);
  padding: 9px 13px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  min-height: 39px;
}
.term-picker [aria-pressed='true'] {
  background: var(--panel);
  color: var(--ink);
  box-shadow: 0 1px 4px #0002;
}
.term-picker small {
  color: var(--brand);
  font-weight: 750;
  margin-left: 5px;
}
.cols {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.col {
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--line-strong);
  background: var(--panel);
  color: var(--ink);
  padding: clamp(17px, 2.2vw, 30px);
  min-width: 0;
}
.col.featured {
  background: #2b1128;
  color: #fff;
  border-color: #2b1128;
}
.col header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.name {
  font: 750 clamp(19px, 2.2vw, 29px) var(--display-font);
  letter-spacing: -0.05em;
}
.tag {
  border-radius: 20px;
  padding: 4px 9px;
  background: var(--panel-2);
  font-size: 11px;
  color: var(--ink);
}
.featured .tag {
  background: #69315d;
  color: #ffdbf7;
}
.pnote,
.price span,
.note {
  color: var(--ink-2);
}
.pnote {
  margin: 7px 0 0;
  font-size: 14px;
  line-height: 1.4;
}
.featured .pnote,
.featured .price span {
  color: #e2c6dd;
}
.price {
  margin-top: auto;
  padding-top: 25px;
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;
}
.price strong {
  font: 800 clamp(24px, 3.2vw, 48px)/1 var(--display-font);
  letter-spacing: -0.065em;
}
.price span {
  font-size: 13px;
}
.grant {
  border-top: 1px solid var(--line);
  margin: 20px 0 16px;
  padding-top: 16px;
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 14px;
}
.grant svg {
  color: var(--brand);
  flex-shrink: 0;
}
.featured .grant {
  border-color: #62415d;
}
.featured .grant svg {
  color: #f788e5;
}
.plan-buy {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  background: var(--panel-2);
  color: var(--ink);
  border: 0;
  border-radius: 9px;
  padding: 12px 14px;
  min-height: 44px;
  font-weight: 650;
}
.featured .plan-buy {
  background: #af199e;
  color: white;
}
.plan-buy:hover {
  filter: brightness(0.95);
}
.costs {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 15px 18px;
  margin-top: 16px;
}
.costs summary {
  cursor: pointer;
  font-weight: 600;
}
.costs dl {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px 20px;
  margin-bottom: 0;
  max-width: 640px;
}
.costs dd {
  font-weight: 650;
}
.note,
.reason {
  font-size: 14px;
  line-height: 1.5;
}
.note a {
  color: inherit;
  text-underline-offset: 3px;
}
.receipt {
  margin-top: 15px;
}
.err {
  color: var(--bad);
}
.loading {
  padding: 18px 0;
}
.reason {
  margin: 0;
}
@media (max-width: 720px) {
  .cols {
    grid-template-columns: 1fr;
  }
  .col {
    padding: 19px;
  }
  .price {
    padding-top: 16px;
  }
  .grant {
    margin: 14px 0;
    padding-top: 12px;
  }
  .term-picker button {
    padding: 7px 9px;
  }
  .term-picker {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
  }
  .term-picker small {
    display: block;
    margin: 2px 0 0;
  }
  .term-picker button {
    line-height: 1.17;
  }
}
</style>
