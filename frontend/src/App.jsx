import { useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import { v4 as uuid } from 'uuid'

import ShaderBackground  from './components/ShaderBackground'
import Header            from './components/Header'
import URLInputForm      from './components/URLInputForm'
import ProcessingSection from './components/ProcessingSection'
import ResultsSection    from './components/ResultsSection'
import RecentNotes       from './components/RecentNotes'
import BottomNav         from './components/BottomNav'
import HistoryPage       from './pages/HistoryPage'
import { useHistory }    from './hooks/useHistory'

// ── Home page ─────────────────────────────────────────────────────────────────
function HomePage({ history, addItem, removeItem, clearAll }) {
  const [url, setUrl]                     = useState('')
  const [instructions, setInstructions]   = useState('')
  const [isLoading, setIsLoading]         = useState(false)
  const [progress, setProgress]           = useState(0)
  const [results, setResults]             = useState(null)
  const [error, setError]                 = useState(null)
  const [viewingHistoryItem, setViewing]  = useState(null)

  const handleGenerate = async () => {
    if (!url.trim() || isLoading) return
    setIsLoading(true)
    setError(null)
    setResults(null)
    setViewing(null)
    setProgress(0)

    let p = 0
    const tick = setInterval(() => {
      p += Math.random() * 2.5
      if (p > 88) clearInterval(tick)
      setProgress(Math.min(p, 88))
    }, 600)

    try {
      const res  = await fetch('/api/generate', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ url: url.trim(), instructions: instructions.trim() }),
      })
      const data = await res.json()

      if (!res.ok) {
        setError(data.error || 'Something went wrong. Please try again.')
      } else {
        setProgress(100)
        setResults(data)

        // Save to persistent history
        addItem({
          id:        uuid(),
          title:     data.notes.title,
          url:       url.trim(),
          timestamp: new Date().toISOString(),
          notes:     data.notes,
          pdf_urls:  data.pdf_urls,
        })
      }
    } catch (err) {
      setError(`Network error: ${err.message}. Is Flask running on port 5000?`)
    } finally {
      clearInterval(tick)
      setIsLoading(false)
    }
  }

  // When user clicks a recent note card → show that note's results
  const handleSelectNote = (item) => {
    setViewing(item)
    setResults({ notes: item.notes, pdf_urls: item.pdf_urls })
    setError(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const displayResults = viewingHistoryItem
    ? { notes: viewingHistoryItem.notes, pdf_urls: viewingHistoryItem.pdf_urls }
    : results

  return (
    <main className="min-h-[calc(100vh-64px)] px-4 py-8 md:py-14 pb-24 md:pb-14">
      <div className="max-w-2xl mx-auto flex flex-col items-center gap-6">

        {/* Hero */}
        <div className="text-center space-y-2">
          <h1 className="font-headline font-bold text-headline-xl text-on-surface tracking-tight">
            Generate AI Notes<br />from YouTube
          </h1>
          <p className="text-outline font-body text-body-md max-w-sm mx-auto">
            Turn any video into structured knowledge — summary, cheatsheet &amp; flashcards.
          </p>
        </div>

        {/* Input form */}
        <URLInputForm
          url={url}
          setUrl={setUrl}
          instructions={instructions}
          setInstructions={setInstructions}
          onGenerate={handleGenerate}
          isLoading={isLoading}
        />

        {/* Processing */}
        {isLoading && <ProcessingSection progress={progress} />}

        {/* Error */}
        {error && (
          <div
            className="w-full border-2 border-error bg-error-container p-4"
            style={{ boxShadow: '4px 4px 0px #cc0000' }}
          >
            <div className="flex gap-2 items-start">
              <span className="material-symbols-outlined text-error shrink-0">error</span>
              <p className="text-on-error-container text-body-sm font-bold">{error}</p>
            </div>
          </div>
        )}

        {/* Results */}
        {displayResults && !isLoading && (
          <>
            {viewingHistoryItem && (
              <div className="w-full flex items-center gap-2">
                <button
                  onClick={() => { setViewing(null); setResults(null) }}
                  className="flex items-center gap-1 text-xs font-bold uppercase tracking-wider text-outline hover:text-primary"
                >
                  <span className="material-symbols-outlined text-sm">arrow_back</span>
                  Back
                </button>
                <span className="text-xs text-outline">Viewing saved note</span>
              </div>
            )}
            <ResultsSection results={displayResults} />
          </>
        )}

        {/* Recent notes on homepage */}
        {!isLoading && !displayResults && (
          <div className="w-full border-t-2 border-primary pt-6">
            <RecentNotes history={history} onSelectNote={handleSelectNote} />
          </div>
        )}
      </div>
    </main>
  )
}

// ── Root App with routing ──────────────────────────────────────────────────────
export default function App() {
  const { history, addItem, removeItem, clearAll } = useHistory()

  return (
    <div className="font-body text-on-surface min-h-screen">
      <ShaderBackground />
      <Header />

      <Routes>
        <Route
          path="/"
          element={
            <HomePage
              history={history}
              addItem={addItem}
              removeItem={removeItem}
              clearAll={clearAll}
            />
          }
        />
        <Route
          path="/history"
          element={
            <HistoryPage
              history={history}
              removeItem={removeItem}
              clearAll={clearAll}
            />
          }
        />
      </Routes>

      <BottomNav />
    </div>
  )
}
