import { useState, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'ytnm_history'
const MAX_ITEMS   = 20

/**
 * Custom hook — persists note history in localStorage.
 *
 * Each item:
 *   { id, title, url, timestamp, notes, pdf_urls }
 */
export function useHistory() {
  const [history, setHistory] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return raw ? JSON.parse(raw) : []
    } catch {
      return []
    }
  })

  // Sync to localStorage on every change
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
  }, [history])

  const addItem = useCallback((item) => {
    setHistory(prev => {
      // avoid duplicates by url — move to top if exists
      const filtered = prev.filter(h => h.url !== item.url)
      return [item, ...filtered].slice(0, MAX_ITEMS)
    })
  }, [])

  const removeItem = useCallback((id) => {
    setHistory(prev => prev.filter(h => h.id !== id))
  }, [])

  const clearAll = useCallback(() => {
    setHistory([])
  }, [])

  return { history, addItem, removeItem, clearAll }
}
