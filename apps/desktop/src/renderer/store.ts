import { create } from 'zustand'
import type { ComputeType, DesktopJob, Device } from '../shared/api'
import { selectionAfterRemoval } from './format'

interface WorkbenchState {
  theme: 'light' | 'dark'
  toggleTheme(): void
  jobs: Record<string, DesktopJob>
  selectedJob: string | null
  selectJob(id: string): void
  mergeJobs(jobs: DesktopJob[]): void
  putJob(job: DesktopJob, select?: boolean): void
  removeJob(jobId: string): void
  device: Device | null
  computeType: ComputeType | null
  setDevice(device: Device | null): void
  setComputeType(computeType: ComputeType | null): void
  outputDir: string | null
  setOutputDir(outputDir: string): void
}

const latest = (previous: DesktopJob | undefined, next: DesktopJob) =>
  previous && previous.revision > next.revision ? previous : next

export const useWorkbench = create<WorkbenchState>((set) => ({
  theme: window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
  toggleTheme: () => set((state) => ({ theme: state.theme === 'light' ? 'dark' : 'light' })),
  jobs: {},
  selectedJob: null,
  selectJob: (selectedJob) => set({ selectedJob }),
  mergeJobs: (jobs) => set((state) => ({
    jobs: { ...state.jobs, ...Object.fromEntries(jobs.map((job) => [job.id, latest(state.jobs[job.id], job)])) },
    selectedJob: state.selectedJob ?? jobs[0]?.id ?? null,
  })),
  putJob: (job, select = false) => set((state) => ({
    jobs: { ...state.jobs, [job.id]: latest(state.jobs[job.id], job) },
    selectedJob: select ? job.id : state.selectedJob,
  })),
  removeJob: (jobId) => set((state) => {
    if (!state.jobs[jobId]) return state
    const jobs = { ...state.jobs }
    delete jobs[jobId]
    return { jobs, selectedJob: selectionAfterRemoval(jobs, state.selectedJob, jobId) }
  }),
  device: null,
  computeType: null,
  setDevice: (device) => set({ device }),
  setComputeType: (computeType) => set({ computeType }),
  outputDir: null,
  setOutputDir: (outputDir) => set({ outputDir }),
}))
