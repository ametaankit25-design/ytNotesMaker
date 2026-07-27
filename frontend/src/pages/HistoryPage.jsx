import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ResultsSection from '../components/ResultsSection'

function timeAgo(isoString) {
  const diff  = Date.now() - new Date(isoString).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (mins  < 1)  return 'Just now'
  if (hours < 1)  return `${mins}m ago`
  if (days  < 1)  return `${hours}h ago`
  if (days  < 7)  return `${days}d ago`
  return new Date(isoString).toLocaleDateString()
}

export default function HistoryPage({ history, removeItem, clearAll }) {
  const navigate = useNavigate()
  const [selected, setSelected] = useState(null)
  const [search, setSearch]     = useState('')
  const [confirmClear, setConfirmClear] = useState(false)

  const filtered = history.filter(h =>
    h.title.toLowerCase().includes(search.toLowerCase()) ||
    h.url.toLowerCase().includes(search.toLowerCase())
  )

  if (selected) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 pb-24 md:pb-8 space-y-4">
        {/* Back button */}
        <button
          onClick={() => setSelected(null)}
          className="flex items-center gap-2 font-label font-bold text-sm uppercase tracking-wider text-primary border-2 border-primary px-4 py-2 hover:bg-primary hover:text-on-primary transition-colors"
          style={{ boxShadow: '3px 3px 0px #ffcc00' }}
        >
          <span className="material-symbols-outlined text-base">arrow_back</span>
          Back to History
        </button>

        {/* Results viewer */}
        <ResultsSection results={{ notes: selected.notes, pdf_urls: selected.pdf_urls }} />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 pb-24 md:pb-8 space-y-6">

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-headline font-bold text-2xl text-on-surface uppercase tracking-tight">
            History
          </h1>
          <p className="text-outline text-sm mt-0.5">{history.length} note{history.length !== 1 ? 's' : ''} saved</p>
        </div>
        <button
          onClick={() => navigate('/')}
          className="btn-primary px-4 py-2 text-sm flex items-center gap-2"
        >
          <span className="material-symbols-outlined text-base">add</span>
          New Note
        </button>
      </div>

      {/* Search */}
      <div className="brutal-card flex items-center gap-3 px-4 py-3">
        <span className="material-symbols-outlined text-outline text-base">search</span>
        <input
          type="text"
          className="flex-1 bg-transparent text-body-md text-on-surface placeholder:text-outline/50 outline-none"
          placeholder="Search by title or URL..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        {search && (
          <button onClick={() => setSearch('')} className="text-outline hover:text-primary">
            <span className="material-symbols-outlined text-base">close</span>
          </button>
        )}
      </div>

      {/* Empty state */}
      {history.length === 0 && (
        <div className="text-center py-16 border-2 border-dashed border-outline-variant bg-surface-container-lowest/50">
          <span className="material-symbols-outlined text-4xl text-outline block mb-3">history</span>
          <p className="font-headline font-bold text-on-surface mb-1">No history yet</p>
          <p className="text-outline text-sm mb-4">Generate notes from a YouTube video to get started.</p>
          <button
            onClick={() => navigate('/')}
            className="btn-primary px-6 py-2 text-sm"
          >
            Generate Notes
          </button>
        </div>
      )}

      {/* No search results */}
      {history.length > 0 && filtered.length === 0 && (
        <div className="text-center py-10 border-2 border-dashed border-outline-variant bg-surface-container-lowest/50">
          <span className="material-symbols-outlined text-3xl text-outline block mb-2">search_off</span>
          <p className="text-outline text-sm">No results for "{search}"</p>
        </div>
      )}

      {/* History list */}
      <div className="space-y-3">
        {filtered.map((item) => (
          <div
            key={item.id}
            className="brutal-card p-4 cursor-pointer group"
            onClick={() => setSelected(item)}
          >
            <div className="flex items-start justify-between gap-3">
              {/* Icon + info */}
              <div className="flex items-start gap-3 min-w-0">
                <div className="shrink-0 w-10 h-10 bg-secondary border-2 border-primary flex items-center justify-center">
                  <span
                    className="material-symbols-outlined text-on-primary text-base"
                    style={{ fontVariationSettings: "'FILL' 1" }}
                  >
                    play_circle
                  </span>
                </div>

                <div className="min-w-0">
                  <h3 className="font-headline font-bold text-on-surface group-hover:text-tertiary transition-colors line-clamp-2 text-sm leading-tight">
                    {item.title}
                  </h3>
                  <p className="text-xs text-outline font-mono mt-1 truncate">{item.url}</p>

                  {/* Stats */}
                  <div className="flex flex-wrap gap-2 mt-2">
                    <span className="bg-primary-fixed text-primary border border-primary px-2 py-0.5 text-xs font-bold uppercase">
                      {item.notes.key_concepts.length} concepts
                    </span>
                    <span className="bg-surface-container text-outline border border-outline-variant px-2 py-0.5 text-xs font-bold">
                      {item.notes.bullet_points.length} notes
                    </span>
                    <span className="bg-surface-container text-outline border border-outline-variant px-2 py-0.5 text-xs font-bold">
                      {item.notes.flashcards.length} flashcards
                    </span>
                  </div>
                </div>
              </div>

              {/* Right: time + actions */}
              <div className="flex flex-col items-end gap-2 shrink-0">
                <span className="text-xs text-outline font-mono whitespace-nowrap">
                  {timeAgo(item.timestamp)}
                </span>
                <div className="flex gap-1">
                  {['summary', 'cheatsheet', 'flashcards'].map(type => (
                    <a
                      key={type}
                      href={item.pdf_urls[type]}
                      download
                      onClick={e => e.stopPropagation()}
                      title={`Download ${type} PDF`}
                      className="w-7 h-7 border-2 border-primary bg-surface-container-lowest flex items-center justify-center hover:bg-primary-fixed transition-colors"
                      style={{ boxShadow: '1px 1px 0px var(--shadow-color)' }}
                    >
                      <span className="material-symbols-outlined text-xs" style={{ fontVariationSettings: "'FILL' 1" }}>
                        download
                      </span>
                    </a>
                  ))}
                  <button
                    onClick={e => { e.stopPropagation(); removeItem(item.id) }}
                    className="w-7 h-7 border-2 border-error bg-surface-container-lowest flex items-center justify-center hover:bg-error hover:text-on-error transition-colors"
                    style={{ boxShadow: '1px 1px 0px #cc0000' }}
                    title="Delete"
                  >
                    <span className="material-symbols-outlined text-xs text-error hover:text-on-error">delete</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Summary snippet */}
            <p className="mt-3 text-xs text-on-surface/60 line-clamp-2 border-t border-outline-variant pt-2">
              {item.notes.summary}
            </p>
          </div>
        ))}
      </div>

      {/* Clear all */}
      {history.length > 0 && (
        <div className="border-t-2 border-outline-variant pt-4 flex justify-end">
          {confirmClear ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-error font-bold">Clear all history?</span>
              <button
                onClick={() => { clearAll(); setConfirmClear(false) }}
                className="btn-primary bg-error border-error px-3 py-1.5 text-xs"
              >
                Yes, clear
              </button>
              <button
                onClick={() => setConfirmClear(false)}
                className="border-2 border-primary px-3 py-1.5 text-xs font-bold uppercase hover:bg-surface-container transition-colors"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmClear(true)}
              className="font-label font-bold text-xs uppercase tracking-widest text-error hover:underline flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-sm">delete_sweep</span>
              Clear History
            </button>
          )}
        </div>
      )}
    </div>
  )
}
