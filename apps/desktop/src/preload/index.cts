import { contextBridge, ipcRenderer, webUtils } from 'electron'
import type { DesktopJob, WorkbenchApi } from '../shared/api.js'

const api: WorkbenchApi = {
  health: () => ipcRenderer.invoke('health'),
  models: () => ipcRenderer.invoke('models'),
  pickAudioFile: () => ipcRenderer.invoke('pick-audio'),
  pickAudioFiles: () => ipcRenderer.invoke('pick-audio-files'),
  registerDroppedAudio: (file) => {
    const path = webUtils.getPathForFile(file)
    if (!path) return Promise.reject(new Error('请拖入磁盘上的音频或视频文件。'))
    return ipcRenderer.invoke('register-audio', path)
  },
  registerDroppedAudios: (files) => {
    const paths = Array.from(files).map((file) => {
      try {
        return webUtils.getPathForFile(file)
      } catch {
        return ''
      }
    })
    return ipcRenderer.invoke('register-audios', paths)
  },
  createJob: (input, options) => ipcRenderer.invoke('create-job', input, options),
  listJobs: () => ipcRenderer.invoke('list-jobs'),
  cancelJob: (id) => ipcRenderer.invoke('cancel-job', id),
  updateSegment: (id, segmentId, edit) => ipcRenderer.invoke('update-segment', id, segmentId, edit),
  reviewSegment: (id, segmentId, decision) => ipcRenderer.invoke('review-segment', id, segmentId, decision),
  exportJob: (id, format, policy) => ipcRenderer.invoke('export-job', id, format, policy),
  exportJobToDirectory: (id, format, directory, baseName) =>
    ipcRenderer.invoke('export-job-dir', id, format, directory, baseName),
  onJobUpdate: (callback) => {
    const listener = (_event: Electron.IpcRendererEvent, job: DesktopJob) => callback(job)
    ipcRenderer.on('job-update', listener)
    return () => { ipcRenderer.removeListener('job-update', listener) }
  },
  pickModelDirectory: () => ipcRenderer.invoke('pick-model-directory'),
  openModelDirectory: () => ipcRenderer.invoke('open-model-directory'),
  rescanModels: () => ipcRenderer.invoke('rescan-models'),
  pickOutputDirectory: () => ipcRenderer.invoke('pick-output-directory'),
  listGlossaries: () => ipcRenderer.invoke('list-glossaries'),
  readGlossary: (id) => ipcRenderer.invoke('read-glossary', id),
  saveGlossary: (id, entries) => ipcRenderer.invoke('save-glossary', id, entries),
  deleteGlossary: (id) => ipcRenderer.invoke('delete-glossary', id),
  importGlossary: (id, format, content) => ipcRenderer.invoke('import-glossary', id, format, content),
  exportGlossary: (id, format) => ipcRenderer.invoke('export-glossary', id, format),
  previewGlossary: (id, field, text) => ipcRenderer.invoke('preview-glossary', id, field, text),
  saveTextFile: (name, content) => ipcRenderer.invoke('save-text-file', name, content),
  translationPrompt: () => ipcRenderer.invoke('translation-prompt'),
  saveTranslationPrompt: (prompt) => ipcRenderer.invoke('save-translation-prompt', prompt),
  deepSeekSettings: () => ipcRenderer.invoke('deepseek-settings'),
  saveDeepSeekSettings: (input) => ipcRenderer.invoke('save-deepseek-settings', input),
  deepSeekModels: () => ipcRenderer.invoke('deepseek-models'),
}

contextBridge.exposeInMainWorld('api', api)
