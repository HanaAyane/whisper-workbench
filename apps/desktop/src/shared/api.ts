export const mediaExtensions = ['wav', 'mp3', 'm4a', 'flac', 'mp4', 'mkv', 'webm']
export const exportFormats = ['srt', 'vtt', 'lrc', 'txt'] as const
export type ExportFormat = (typeof exportFormats)[number]
export type OverwritePolicy = 'preserve' | 'replace'
export type GlossaryFormat = 'json' | 'csv'
export type Field = 'text' | 'translation'
export type Policy = 'correct' | 'translate' | 'keep'
export type Device = 'auto' | 'cpu' | 'cuda'
export type ComputeType = 'int8' | 'int8_float16' | 'float16' | 'bfloat16'

export interface Health {
  status: 'ok'
  version: string
  models_ok: boolean
}

export interface FileCheck { path: string; ok: boolean; error?: string }
export interface ModelInfo {
  id: string
  label: string
  type: 'asr' | 'translate'
  path: string
  compute_type: string
  ok: boolean
  files: FileCheck[]
}

export interface ModelCatalog {
  manifest_path: string
  models: ModelInfo[]
  vad: { ok: boolean; files: FileCheck[] } | null
  models_ok: boolean
  errors: string[]
}

export interface Glossary {
  id: string
  name: string
  entry_count: number
}

export interface Entry {
  id: string
  source: string
  variants: string[]
  target: string
  category: string
  match_mode: 'exact'
  regex: null
  priority: number
  field: Field
  policy: Policy
  enabled: boolean
}

export interface TermHit {
  entry_id: string
  field: Field
  start: number
  end: number
  matched_text: string
  replacement: string | null
  policy: Policy
  confidence: number
}

export interface Preview { text: string; replaced_text: string; hits: TermHit[] }
export interface GlossaryResult { glossary_id: string; entry_count: number; warnings: string[] }
export interface SegmentEdit { text: string; translation: string | null; revision: number }

export interface ReviewHit extends TermHit {
  decision: 'pending' | 'accepted' | 'rejected'
  original_text: string | null
}

export type SegmentReview = {
  revision: number
} & (
  | { action: 'accept' | 'reject'; hit: Pick<TermHit, 'entry_id' | 'field' | 'start' | 'end'> }
  | { action: 'undo' }
)

export interface Segment extends SegmentEdit {
  id: number
  start: number
  end: number
  raw_text: string
  raw_translation: string | null
  hits: ReviewHit[]
}

export interface DesktopJob {
  id: string
  state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  stage: 'decode' | 'vad' | 'asr' | 'glossary' | 'export' | null
  progress: number
  message: string
  error: string | null
  segments: Segment[]
  name: string
  mode: 'transcribe' | 'translate'
  recorded_path: string | null
  created_at: string
  revision: number
  cancel_requested: boolean
}

export interface AudioFile { id: string; name: string }
export type JobInput =
  | { kind: 'file'; id: string }
  | { kind: 'recording'; data: ArrayBuffer; keep: boolean }

export interface JobOptions {
  asr_model_id: string
  mode: DesktopJob['mode']
  glossary_id: string | null
  device: Device | null
  compute_type: ComputeType | null
}

export interface WorkbenchApi {
  health(): Promise<Health>
  models(): Promise<ModelCatalog>
  pickAudioFile(): Promise<AudioFile | null>
  registerDroppedAudio(file: File): Promise<AudioFile>
  createJob(input: JobInput, options: JobOptions): Promise<DesktopJob>
  listJobs(): Promise<DesktopJob[]>
  cancelJob(jobId: string): Promise<void>
  updateSegment(jobId: string, segmentId: number, edit: SegmentEdit): Promise<void>
  reviewSegment(jobId: string, segmentId: number, decision: SegmentReview): Promise<void>
  exportJob(jobId: string, format: ExportFormat, policy: OverwritePolicy): Promise<string | null>
  onJobUpdate(callback: (job: DesktopJob) => void): () => void
  pickModelDirectory(): Promise<ModelCatalog | null>
  pickOutputDirectory(): Promise<string | null>
  listGlossaries(): Promise<Glossary[]>
  readGlossary(id: string): Promise<Entry[]>
  saveGlossary(id: string, entries: Entry[]): Promise<GlossaryResult>
  deleteGlossary(id: string): Promise<void>
  importGlossary(id: string, format: GlossaryFormat, content: string): Promise<GlossaryResult>
  exportGlossary(id: string, format: GlossaryFormat): Promise<string | null>
  previewGlossary(id: string, field: Field, text: string): Promise<Preview>
  saveTextFile(name: string, content: string): Promise<string | null>
}
