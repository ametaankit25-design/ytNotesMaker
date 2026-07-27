import { useState, useEffect, useCallback } from 'react'

const PROFILE_KEY = 'ytnm_user_profile'

export function useProfile() {
  const [profile, setProfile] = useState(() => {
    try {
      const raw = localStorage.getItem(PROFILE_KEY)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })

  useEffect(() => {
    if (profile) {
      localStorage.setItem(PROFILE_KEY, JSON.stringify(profile))
    }
  }, [profile])

  const saveProfile = useCallback((name, education) => {
    const newProfile = {
      name: name.trim(),
      education: education.trim(),
      updatedAt: new Date().toISOString(),
    }
    setProfile(newProfile)
    localStorage.setItem(PROFILE_KEY, JSON.stringify(newProfile))
  }, [])

  const clearProfile = useCallback(() => {
    setProfile(null)
    localStorage.removeItem(PROFILE_KEY)
  }, [])

  return {
    profile,
    saveProfile,
    clearProfile,
    hasProfile: Boolean(profile?.name),
  }
}
