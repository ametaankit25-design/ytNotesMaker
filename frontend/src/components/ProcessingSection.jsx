export default function ProcessingSection({ progress }) {
  const steps = [
    { label: 'Fetching transcript', done: progress > 25 },
    { label: 'Analysing with LLM', done: progress > 60 },
    { label: 'Generating PDFs',    done: progress >= 100 },
  ]

  return (
    <div className="w-full space-y-4">
      {/* Dark processing card */}
      <div className="w-full bg-primary border-2 border-primary p-6" style={{ boxShadow: '4px 4px 0px #ffcc00' }}>
        <div className="flex items-center gap-3 mb-4">
          <span className="material-symbols-outlined text-primary-fixed loading-pulse">auto_awesome</span>
          <span className="text-on-primary font-headline font-bold tracking-wide text-sm uppercase">
            AI is processing your video...
          </span>
        </div>

        {/* Steps */}
        <div className="space-y-2 mb-4">
          {steps.map((step, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <span className={`material-symbols-outlined text-base ${step.done ? 'text-primary-fixed' : 'text-outline/50'}`}
                    style={{ fontVariationSettings: step.done ? "'FILL' 1" : "'FILL' 0" }}>
                {step.done ? 'check_circle' : 'radio_button_unchecked'}
              </span>
              <span className={step.done ? 'text-primary-fixed font-bold' : 'text-on-primary/50'}>
                {step.label}
              </span>
            </div>
          ))}
        </div>

        {/* Progress bar */}
        <div className="w-full h-2 bg-on-primary/20 border border-on-primary/30">
          <div
            className="h-full bg-primary-fixed transition-all duration-500"
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
        <div className="text-right text-xs text-on-primary/50 mt-1 font-mono">
          {Math.round(Math.min(progress, 100))}%
        </div>
      </div>
    </div>
  )
}
