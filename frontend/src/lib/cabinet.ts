import { ref } from 'vue'

export const cabinetTabs = ['overview', 'covers', 'rewards', 'rules', 'wb', 'partner'] as const
export type CabinetTab = (typeof cabinetTabs)[number]
function readRoute(): CabinetTab | null {
  if (!/^\/(account|studio)\/?$/.test(location.pathname)) return null
  const fallback = location.pathname.startsWith('/studio') ? 'rules' : 'overview'
  return cabinetTabs.find((id) => '#' + id === location.hash) ?? fallback
}
export const cabinetTab = ref(readRoute())
export function syncCabinet() {
  cabinetTab.value = readRoute()
}
export function navigateCabinet(tab: CabinetTab | null = 'overview') {
  const url = tab ? '/account' + (tab === 'overview' ? '' : '#' + tab) : '/'
  if (location.pathname + location.search + location.hash !== url) history.pushState(null, '', url)
  syncCabinet()
}
