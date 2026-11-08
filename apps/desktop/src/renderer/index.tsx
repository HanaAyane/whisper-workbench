import { createRoot } from 'react-dom/client'
import type { WorkbenchApi } from '../shared/api'
import { App } from './App'
import './glasswork/glass.css'
import './styles.css'

declare global {
  interface Window { api: WorkbenchApi }
}

createRoot(document.getElementById('root')!).render(<App />)
