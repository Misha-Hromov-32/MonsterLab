import { reactive } from 'vue'
import type { Job } from './types'

/**
 * Задачи очереди, которые сейчас ждут или выполняются у этого покупателя, — для плашки
 * «Вы 2-й в очереди · ~20 с». Наполняет api.ts, пока опрашивает /api/jobs/{id}.
 */
export const queue = reactive({ jobs: {} as Record<string, Job> })

export function trackJob(job: Job) {
  if (job.status === 'queued' || job.status === 'running') queue.jobs[job.id] = job
  else delete queue.jobs[job.id]
}

export function forgetJob(id: string) {
  delete queue.jobs[id]
}
