const TIME_LABELS = ['Just now', '2h ago', 'Yesterday', '3 days ago', 'Last week']

export default function HistorySection({ history }) {
  const displayItems = history.length > 0 ? history : [
    { title: 'How to Build a Startup',       tag: 'Business',    duration: '12:45' },
    { title: 'Mastering React Native',        tag: 'Engineering', duration: '45:10' },
    { title: 'Intro to Machine Learning',     tag: 'AI Research', duration: '1:02:30' },
  ]

  return (
    <section className="w-full mt-4 border-t-2 border-primary pt-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-headline font-bold text-headline-lg-mobile text-on-surface">
          Recent History
        </h2>
        <button className="font-label font-bold text-xs uppercase tracking-widest text-tertiary hover:underline">
          View All
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {displayItems.slice(0, 4).map((item, i) => (
          <div
            key={i}
            className="brutal-card p-4 cursor-pointer group flex flex-col justify-between"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="w-9 h-9 bg-secondary flex items-center justify-center border-2 border-primary">
                <span className="material-symbols-outlined text-on-primary text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                  play_circle
                </span>
              </div>
              <span className="text-outline text-body-sm font-mono">
                {item.timestamp
                  ? new Date(item.timestamp).toLocaleDateString()
                  : TIME_LABELS[i] || '—'}
              </span>
            </div>
            <div>
              <h3 className="font-bold text-on-surface group-hover:text-tertiary transition-colors line-clamp-1 font-headline">
                {item.title}
              </h3>
              <div className="flex gap-2 mt-2">
                {item.tag && (
                  <span className="bg-primary-fixed text-primary border border-primary px-2 py-0.5 text-xs font-bold uppercase">
                    {item.tag}
                  </span>
                )}
                {item.duration && (
                  <span className="bg-surface-container text-outline border border-outline-variant px-2 py-0.5 text-xs font-bold">
                    {item.duration}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
