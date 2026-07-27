import { useEffect, useState } from 'react'

const DISMISS_KEY = 'ytnm-install-dismissed'

function isStandalone() {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  )
}

function isMobile() {
  return window.matchMedia('(max-width: 767px)').matches
}

function isIos() {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent)
}

export default function InstallPrompt() {
  const [deferred, setDeferred] = useState(null)
  const [visible, setVisible] = useState(false)
  const [iosHint, setIosHint] = useState(false)

  useEffect(() => {
    if (localStorage.getItem(DISMISS_KEY) === '1') return
    if (!isMobile() || isStandalone()) return

    const onBip = (e) => {
      e.preventDefault()
      setDeferred(e)
      setVisible(true)
      setIosHint(false)
    }
    window.addEventListener('beforeinstallprompt', onBip)

    // iOS Safari has no beforeinstallprompt — show Add to Home Screen tip
    if (isIos()) {
      setIosHint(true)
      setVisible(true)
    }

    return () => window.removeEventListener('beforeinstallprompt', onBip)
  }, [])

  if (!visible) return null

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, '1')
    setVisible(false)
  }

  const install = async () => {
    if (!deferred) return
    deferred.prompt()
    const { outcome } = await deferred.userChoice
    setDeferred(null)
    if (outcome === 'accepted') setVisible(false)
  }

  return (
    <div className="md:hidden fixed bottom-20 left-3 right-3 z-[60]">
      <div
        className="bg-surface border-2 border-primary p-3 flex gap-3 items-start"
        style={{ boxShadow: '4px 4px 0px var(--shadow-color)' }}
      >
        <span className="material-symbols-outlined text-secondary shrink-0 mt-0.5">
          install_mobile
        </span>
        <div className="flex-1 min-w-0">
          <p className="font-headline font-bold text-sm text-on-surface">
            Install this app
          </p>
          <p className="text-xs text-outline mt-0.5 leading-snug">
            {iosHint
              ? 'Tap Share → Add to Home Screen for quick access.'
              : 'Add ytNotesMaker to your home screen.'}
          </p>
          <div className="flex gap-2 mt-2">
            {!iosHint && deferred && (
              <button
                type="button"
                onClick={install}
                className="btn-yellow px-3 py-1.5 text-[11px]"
              >
                Install
              </button>
            )}
            <button
              type="button"
              onClick={dismiss}
              className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-outline border-2 border-outline hover:text-primary"
            >
              Not now
            </button>
          </div>
        </div>
        <button
          type="button"
          onClick={dismiss}
          className="text-outline hover:text-primary shrink-0"
          aria-label="Dismiss"
        >
          <span className="material-symbols-outlined text-lg">close</span>
        </button>
      </div>
    </div>
  )
}
