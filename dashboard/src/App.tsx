import { Calculator } from './pages/Calculator'

export default function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">◇ ExperimentOS</div>
        <nav>
          <a className="active" href="#plan">Plan</a>
          <a className="disabled" href="#experiments">Experiments</a>
          <a className="disabled" href="#results">Results</a>
        </nav>
        <div className="sidebar-foot muted small">v0.2 · dev</div>
      </aside>
      <main className="content">
        <Calculator />
      </main>
    </div>
  )
}
