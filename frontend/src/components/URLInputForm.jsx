export default function URLInputForm({ url, setUrl, instructions, setInstructions, onGenerate, isLoading }) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !isLoading) onGenerate()
  }

  return (
    <div className="w-full space-y-4">
      {/* URL Input */}
      <div className="brutal-card p-0 overflow-hidden">
        <div className="flex items-center border-b-2 border-primary">
          <span className="material-symbols-outlined px-4 text-secondary font-bold">link</span>
          <input
            type="text"
            className="flex-1 bg-transparent py-4 pr-4 text-body-md text-on-surface placeholder:text-outline/50 outline-none"
            placeholder="Paste YouTube Link here..."
            value={url}
            onChange={e => setUrl(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            id="youtube-url"
          />
        </div>
      </div>

      {/* Instructions */}
      <div className="brutal-card p-0 overflow-hidden">
        <label className="block px-4 pt-3 font-label text-label-caps text-outline uppercase tracking-widest text-xs">
          Specific Instructions
        </label>
        <textarea
          id="instructions"
          className="w-full bg-transparent px-4 pb-3 pt-1 text-body-md text-on-surface placeholder:text-outline/50 outline-none resize-none"
          placeholder="What specific notes should I generate? (e.g., 'Focus on technical details', 'Summarize key points')"
          rows={3}
          value={instructions}
          onChange={e => setInstructions(e.target.value)}
          disabled={isLoading}
        />
      </div>

      {/* Generate Button */}
      <button
        id="generate-btn"
        className="btn-primary w-full py-4 flex items-center justify-center gap-2 text-base disabled:opacity-60 disabled:cursor-not-allowed"
        onClick={onGenerate}
        disabled={isLoading || !url.trim()}
      >
        <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>
          {isLoading ? 'hourglass_top' : 'bolt'}
        </span>
        {isLoading ? 'Generating Notes...' : 'Generate Notes'}
      </button>
    </div>
  )
}
