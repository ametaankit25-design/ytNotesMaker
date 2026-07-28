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
import ProfileModal      from './components/ProfileModal'
import InstallPrompt     from './components/InstallPrompt'
import HistoryPage       from './pages/HistoryPage'

import { useHistory }    from './hooks/useHistory'
import { useProfile }    from './hooks/useProfile'
import { useTheme }      from './hooks/useTheme'

// API Configuration - reads from .env files
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000'

console.log('[Frontend] Using API:', API_BASE_URL)

// ── Home page ─────────────────────────────────────────────────────────────────
function HomePage({ history, addItem, profile }) {
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

    // Combine user instructions with their education profile context
    const profileContext = profile
      ? `Target audience: ${profile.name} (${profile.education}). Tailor depth and examples for this level.`
      : ''
    const combinedInstructions = [profileContext, instructions.trim()].filter(Boolean).join(' ')

    try {
      const res = await fetch(`${API_BASE_URL}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim(), instructions: combinedInstructions }),
      })

      const rawText = await res.text()
      let data = {}
      try {
        data = JSON.parse(rawText)
      } catch {
        throw new Error(`Server returned status ${res.status} (${res.statusText || 'Gateway Timeout/Error'}). Please try again.`)
      }

      if (!res.ok) {
        setError(data.error || 'Something went wrong. Please try again.')
      } else {
        setProgress(100)
        
        // Validate the response data structure
        if (!data || typeof data !== 'object') {
          throw new Error('Invalid response format from server')
        }
        
        if (!data.notes || typeof data.notes !== 'object') {
          console.error('Invalid notes structure:', data)
          setError('Server returned invalid notes data. The transcript extraction may have failed.')
          return
        }
        
        setResults(data)

        // Only add to history if we have valid notes data with a title
        if (data.notes && data.notes.title) {
          addItem({
            id:        uuid(),
            title:     data.notes.title,
            url:       url.trim(),
            timestamp: new Date().toISOString(),
            notes:     data.notes,
            pdf_urls:  data.pdf_urls,
          })
        } else {
          console.warn('Received notes data without title:', data)
          // Still show results even without title
          setError('Notes generated but title is missing. This may indicate a transcript extraction issue.')
        }
      }
    } catch (err) {
      console.error('Generation error:', err)
      setError(`${err.message}`)
    } finally {
      clearInterval(tick)
      setIsLoading(false)
    }
  }

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
            {profile ? `Welcome back, ${profile.name}! ` : ''}
            Turn any video into structured knowledge.
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

// ── Root App with routing & profile ─────────────────────────────────────────────
export default function App() {
  const { history, addItem, removeItem, clearAll } = useHistory()
  const { profile, saveProfile, hasProfile }       = useProfile()
  const { theme, toggleTheme }                     = useTheme()
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false)

  // Force onboarding modal open if user hasn't set their profile yet
  const showModal = isProfileModalOpen || !hasProfile

  const handleSaveProfile = (name, education) => {
    saveProfile(name, education)
    setIsProfileModalOpen(false)
  }

  return (
    <div className="font-body text-on-surface min-h-screen bg-background">
      <ShaderBackground isDark={theme === 'dark'} />
      <Header
        profile={profile}
        onOpenProfile={() => setIsProfileModalOpen(true)}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      <ProfileModal
        isOpen={showModal}
        initialProfile={profile}
        onSave={handleSaveProfile}
        onClose={() => setIsProfileModalOpen(false)}
        isForceOnboarding={!hasProfile}
      />

      <Routes>
        <Route
          path="/"
          element={
            <HomePage
              history={history}
              addItem={addItem}
              profile={profile}
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

      <InstallPrompt />
      <BottomNav />
    </div>
  )
}
