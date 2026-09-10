import { useState } from 'react'
import { Calculator } from './pages/Calculator'
import { Experiments } from './pages/Experiments'
import { Results } from './pages/Results'

type View = 'plan' | 'experiments' | 'results'

export default function App() {
  const [view, setView] = useState<View>('plan')
  const [selectedExp, setSelectedExp] = useState<string | null>(null)

  function openResults(id: string) {
    setSelectedExp(id)
    setView('results')
  }

  const navItem = (v: View, label: string) => (
    <button
      className={view === v ? 'active' : ''}
      onClick={() => setView(v)}
    >
      {label}
    </button>
  )

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand"><span className="dot" /> ExperimentOS</div>
        <nav>
          {navItem('plan', 'Plan')}
          {navItem('experiments', 'Experiments')}
          {navItem('results', 'Results')}
        </nav>
        <div className="sidebar-foot muted small">v0.2 · dev</div>
      </aside>
      <main className="content">
        {view === 'plan' && <Calculator />}
        {view === 'experiments' && <Experiments onOpenResults={openResults} />}
        {view === 'results' && <Results initialId={selectedExp} />}
      </main>
    </div>
  )
}
