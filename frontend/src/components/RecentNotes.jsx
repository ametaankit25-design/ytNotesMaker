import { useNavigate } from 'react-router-dom'

function timeAgo(isoString) {
  const diff = Date.now() - new Date(isoString).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (mins  < 1)  return 'Just now'
  if (hours < 1)  return `${mins}m ago`
  if (days  < 1)  return `${hours}h ago`
  if (days  < 7)  return `${days}d ago`
  return new Date(isoString).toLocaleDateString()
}

export default function RecentNotes({ history, onSelectNote }) {
  const navigate = useNavigate()

  if (history.length === 0) return null

  const recent = history.slice(0, 3)

  return (
    <section className="w-full">
      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-headline font-bold text-lg text-on-surface uppercase tracking-tight">
          Recent Notes
        </h2>
        <button
          onClick={() => navigate('/history')}
          className="font-label font-bold text-xs uppercase tracking-widest text-tertiary hover:underline"
        >
          View All →
        </button>
      </div>

      <div className="space-y-3">
        {recent.map((item) => (
          <div
            key={item.id}
            onClick={() => onSelectNote(item)}
            className="brutal-card p-4 cursor-pointer group flex items-center justify-between gap-4"
          >
            {/* Left: icon + text */}
            <div className="flex items-center gap-3 min-w-0">
              <div className="shrink-0 w-10 h-10 bg-secondary border-2 border-primary flex items-center justify-center">
                <span
                  className="material-symbols-outlined text-on-primary text-base"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  play_circle
                </span>
              </div>
              <div className="min-w-0">
                <p className="font-headline font-bold text-on-surface group-hover:text-tertiary transition-colors truncate text-sm">
                  {item.title}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-outline font-mono">{timeAgo(item.timestamp)}</span>
                  <span className="text-outline/40">·</span>
                  <span className="text-xs text-outline">
                    {item.notes.bullet_points.length} notes
                  </span>
                  <span className="text-outline/40">·</span>
                  <span className="text-xs text-outline">
                    {item.notes.flashcards.length} cards
                  </span>
                </div>
              </div>
            </div>

            {/* Right: quick download pills */}
            <div className="flex gap-1 shrink-0">
              {['summary', 'cheatsheet', 'flashcards'].map(type => (
                <a
                  key={type}
                  href={item.pdf_urls[type]}
                  download
                  onClick={e => e.stopPropagation()}
                  title={`Download ${type} PDF`}
                  className="w-7 h-7 border-2 border-primary bg-primary-fixed flex items-center justify-center hover:bg-primary hover:text-on-primary transition-colors"
                  style={{ boxShadow: '2px 2px 0px var(--shadow-color)' }}
                >
                  <span className="material-symbols-outlined text-xs" style={{ fontVariationSettings: "'FILL' 1" }}>
                    download
                  </span>
                </a>
              ))}
              <span className="material-symbols-outlined text-outline self-center ml-1 text-sm group-hover:text-tertiary transition-colors">
                chevron_right
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
