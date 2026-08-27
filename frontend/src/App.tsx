import { BrowserRouter } from 'react-router-dom'
import { AppProviders } from './app/providers'
import { AppShell } from './app/AppShell'
import { AppRouter } from './app/router'

export default function App() {
  return <AppProviders><BrowserRouter><AppShell><AppRouter /></AppShell></BrowserRouter></AppProviders>
}
