import { create } from 'zustand'
import { apiClient, UserResponse } from '../api/client'

interface AuthStore {
  user: UserResponse | null
  isLoading: boolean
  error: string | null
  isAuthenticated: boolean
  
  login: (email: string, password: string) => Promise<void>
  register: (email: string, username: string, password: string, firstName: string, lastName: string) => Promise<void>
  logout: () => void
  getProfile: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  isLoading: false,
  error: null,
  isAuthenticated: !!localStorage.getItem('access_token'),

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiClient.login({ email, password })
      apiClient.setAuthToken(response.access_token)
      
      const user = await apiClient.getProfile()
      set({ user, isAuthenticated: true, isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Login failed'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  register: async (email: string, username: string, password: string, firstName: string, lastName: string) => {
    set({ isLoading: true, error: null })
    try {
      const user = await apiClient.register({
        email,
        username,
        password,
        first_name: firstName,
        last_name: lastName,
      })
      set({ user, isLoading: false })
    } catch (error: any) {
      console.error('Full registration error:', error)
      console.error('Error response:', error.response)
      console.error('Error data:', error.response?.data)
      const message = error.response?.data?.detail || error.message || 'Registration failed'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  logout: () => {
    apiClient.clearAuthToken()
    set({ user: null, isAuthenticated: false, error: null })
  },

  getProfile: async () => {
    set({ isLoading: true })
    try {
      const user = await apiClient.getProfile()
      set({ user, isAuthenticated: true, isLoading: false })
    } catch (error: any) {
      apiClient.clearAuthToken()
      set({ user: null, isAuthenticated: false, isLoading: false })
    }
  },

  clearError: () => set({ error: null }),
}))
