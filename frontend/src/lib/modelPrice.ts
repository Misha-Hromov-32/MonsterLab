import { computed, type Ref } from 'vue'
import { account } from './account'

export function useModelPrice(model: Ref<string>) {
  const price = computed(() => account.billing?.image_models?.find((m) => m.id === model.value)?.cost)
  const balance = computed(() => account.user?.wallet?.remaining)
  const shortfall = computed(
    () => balance.value !== undefined && price.value !== undefined && price.value > balance.value,
  )
  const affordable = computed(
    () =>
      account.billing?.image_models?.filter((m) => m.cost <= (balance.value ?? 0)).sort((a, b) => b.cost - a.cost)[0],
  )
  return { price, balance, shortfall, affordable }
}
