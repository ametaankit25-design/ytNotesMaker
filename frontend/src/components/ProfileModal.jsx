import { useState, useEffect } from 'react'

const EDUCATION_OPTIONS = [
  { id: 'cs',          label: '💻 Computer Science & Software Engineering' },
  { id: 'engineering', label: '⚙️ Engineering & Technology' },
  { id: 'medical',     label: '🩺 Medicine & Healthcare' },
  { id: 'business',    label: '📊 Business, Finance & Management' },
  { id: 'school',      label: '🏫 High School / Higher Secondary' },
  { id: 'academic',    label: '📚 General Academic & Science' },
  { id: 'learner',     label: '🚀 Self-Learner & Professional' },
]

export default function ProfileModal({ isOpen, initialProfile, onSave, onClose, isForceOnboarding }) {
  const [name, setName]           = useState('')
  const [education, setEducation] = useState('cs')
  const [error, setError]         = useState('')

  useEffect(() => {
    if (initialProfile) {
      setName(initialProfile.name || '')
      setEducation(initialProfile.education || 'cs')
    }
  }, [initialProfile, isOpen])

  if (!isOpen) return null

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Please enter your name.')
      return
    }
    setError('')
    onSave(name.trim(), education)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-primary/60 backdrop-blur-sm">
      <div
        className="w-full max-w-md bg-surface border-4 border-primary p-6 space-y-6 animate-in fade-in zoom-in-95 duration-200"
        style={{ boxShadow: '8px 8px 0px #ffcc00' }}
      >
        {/* Header */}
        <div className="flex justify-between items-start border-b-2 border-primary pb-3">
          <div>
            <h2 className="font-headline font-bold text-xl text-primary uppercase tracking-tight">
              {initialProfile ? 'Edit Profile' : 'Welcome to ytNotesMaker! 👋'}
            </h2>
            <p className="text-xs text-outline mt-1 font-body">
              Tell us a bit about yourself so AI can tailor your study notes.
            </p>
          </div>
          {!isForceOnboarding && onClose && (
            <button
              onClick={onClose}
              className="text-primary hover:text-secondary font-bold text-lg leading-none"
            >
              ✕
            </button>
          )}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-error-container border-2 border-error p-3 text-xs font-bold text-on-error-container">
              {error}
            </div>
          )}

          {/* Name input */}
          <div className="space-y-1">
            <label className="block font-label text-xs uppercase font-bold tracking-wider text-primary">
              Your Name
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Ankit Ameta"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full bg-white border-2 border-primary px-4 py-3 font-body text-sm font-bold outline-none focus:border-tertiary"
              style={{ boxShadow: '2px 2px 0px #1a1a1a' }}
            />
          </div>

          {/* Education background */}
          <div className="space-y-2">
            <label className="block font-label text-xs uppercase font-bold tracking-wider text-primary">
              Education / Field of Study
            </label>
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {EDUCATION_OPTIONS.map((opt) => (
                <label
                  key={opt.id}
                  className={`flex items-center gap-3 p-3 border-2 border-primary cursor-pointer transition-all ${
                    education === opt.label
                      ? 'bg-primary-fixed text-primary font-bold'
                      : 'bg-white text-on-surface hover:bg-surface-container'
                  }`}
                  style={{ boxShadow: '2px 2px 0px #1a1a1a' }}
                >
                  <input
                    type="radio"
                    name="education"
                    value={opt.label}
                    checked={education === opt.label}
                    onChange={() => setEducation(opt.label)}
                    className="accent-primary"
                  />
                  <span className="text-xs font-body">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            className="btn-primary w-full py-4 text-sm tracking-widest font-headline uppercase"
          >
            {initialProfile ? 'Save Changes' : 'Get Started →'}
          </button>
        </form>
      </div>
    </div>
  )
}
