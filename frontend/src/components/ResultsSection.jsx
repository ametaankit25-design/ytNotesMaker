import { useState } from 'react'

function DownloadButton({ label, icon, url }) {
  return (
    <a
      href={url}
      download
      className="btn-yellow flex items-center gap-2 px-4 py-3 text-sm w-full justify-center"
    >
      <span className="material-symbols-outlined text-base" style={{ fontVariationSettings: "'FILL' 1" }}>
        {icon}
      </span>
      {label}
    </a>
  )
}

export default function ResultsSection({ results }) {
  const [activeTab, setActiveTab] = useState('summary')
  const { notes, pdf_urls } = results || {}

  // Handle missing or malformed data
  if (!notes) {
    return (
      <div className="w-full border-2 border-error bg-error-container p-4" style={{ boxShadow: '4px 4px 0px #cc0000' }}>
        <div className="flex gap-2 items-start">
          <span className="material-symbols-outlined text-error shrink-0">error</span>
          <p className="text-on-error-container text-body-sm font-bold">
            Unable to display results. The notes data is missing or malformed.
          </p>
        </div>
      </div>
    )
  }

  const tabs = [
    { id: 'summary',    label: 'Summary' },
    { id: 'bullets',    label: 'Notes' },
    { id: 'concepts',   label: 'Concepts' },
    { id: 'flashcards', label: 'Flashcards' },
  ]

  return (
    <div className="w-full space-y-4">
      {/* Title banner */}
      <div className="bg-primary-fixed border-2 border-primary p-4" style={{ boxShadow: '4px 4px 0px var(--shadow-color)' }}>
        <div className="flex items-start gap-2">
          <span className="material-symbols-outlined text-primary mt-0.5" style={{ fontVariationSettings: "'FILL' 1" }}>
            check_circle
          </span>
          <div>
            <p className="text-xs font-label uppercase tracking-widest text-primary/60 font-bold">Notes Ready</p>
            <h2 className="font-headline font-bold text-primary text-lg leading-tight">
              {notes.title || 'Untitled Notes'}
            </h2>
          </div>
        </div>
      </div>

      {/* PDF Downloads */}
      {pdf_urls && (
        <div className="brutal-card p-4 space-y-2">
          <p className="font-label font-bold text-xs uppercase tracking-widest text-outline mb-3">
            Download PDFs
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            <DownloadButton label="Summary PDF"    icon="description"  url={pdf_urls.summary} />
            <DownloadButton label="Cheatsheet PDF" icon="summarize"    url={pdf_urls.cheatsheet} />
            <DownloadButton label="Flashcards PDF" icon="style"        url={pdf_urls.flashcards} />
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="brutal-card overflow-hidden">
        {/* Tab bar */}
        <div className="flex border-b-2 border-primary">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 py-3 font-label font-bold text-xs uppercase tracking-wider transition-colors ${
                activeTab === tab.id
                  ? 'bg-primary text-on-primary'
                  : 'bg-surface-container-lowest text-outline hover:bg-surface-container'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="p-4 bg-surface-container-lowest">
          {/* Summary */}
          {activeTab === 'summary' && (
            <div className="space-y-3">
              <p className="text-body-md text-on-surface leading-relaxed">
                {notes.summary || 'No summary available.'}
              </p>
              {notes.important_quotes?.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="font-label font-bold text-xs uppercase tracking-widest text-outline">Notable Quotes</p>
                  {notes.important_quotes.map((q, i) => (
                    <blockquote key={i} className="border-l-4 border-primary-fixed pl-3 text-body-sm text-on-surface italic">
                      "{q}"
                    </blockquote>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Bullet points */}
          {activeTab === 'bullets' && (
            <ul className="space-y-2">
              {notes.bullet_points?.length > 0 ? (
                notes.bullet_points.map((bp, i) => (
                  <li key={i} className="flex gap-3 text-body-sm text-on-surface">
                    <span className="font-bold text-primary shrink-0 font-mono text-xs mt-1">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <span>{bp}</span>
                  </li>
                ))
              ) : (
                <p className="text-body-sm text-outline">No bullet points available.</p>
              )}
            </ul>
          )}

          {/* Key concepts */}
          {activeTab === 'concepts' && (
            <div className="flex flex-wrap gap-2">
              {notes.key_concepts?.length > 0 ? (
                notes.key_concepts.map((c, i) => (
                  <span key={i} className="concept-pill">{c}</span>
                ))
              ) : (
                <p className="text-body-sm text-outline">No key concepts available.</p>
              )}
            </div>
          )}

          {/* Flashcards */}
          {activeTab === 'flashcards' && (
            <div className="space-y-3">
              {notes.flashcards?.length > 0 ? (
                notes.flashcards.map((card, i) => (
                  <div key={i} className="border-2 border-primary">
                    <div className="flashcard-q flex gap-2">
                      <span className="text-primary-fixed shrink-0 font-mono text-xs">Q{i + 1}</span>
                      <span>{card.question}</span>
                    </div>
                    <div className="flashcard-a flex gap-2">
                      <span className="text-secondary shrink-0 font-mono text-xs font-bold">A</span>
                      <span>{card.answer}</span>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-body-sm text-outline">No flashcards available.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
