import { create } from 'zustand'
import { apiClient, Portfolio, PortfolioSummary } from '../api/client'

interface PortfolioStore {
  portfolios: Portfolio[]
  selectedPortfolioId: string | null
  selectedPortfolio: PortfolioSummary | null
  isLoading: boolean
  error: string | null
  
  fetchPortfolios: () => Promise<void>
  selectPortfolio: (id: string) => Promise<void>
  createPortfolio: (name: string, description?: string) => Promise<void>
  updatePortfolio: (id: string, name: string, description?: string) => Promise<void>
  deletePortfolio: (id: string) => Promise<void>
  updatePrices: (portfolioId: string) => Promise<void>
  clearError: () => void
}

export const usePortfolioStore = create<PortfolioStore>((set, get) => ({
  portfolios: [],
  selectedPortfolioId: null,
  selectedPortfolio: null,
  isLoading: false,
  error: null,

  fetchPortfolios: async () => {
    set({ isLoading: true, error: null })
    try {
      const portfolios = await apiClient.listPortfolios()
      set({ portfolios, isLoading: false })
      
      // Auto-select first portfolio
      if (portfolios.length > 0 && !get().selectedPortfolioId) {
        await get().selectPortfolio(portfolios[0].id)
      }
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to fetch portfolios'
      set({ error: message, isLoading: false })
    }
  },

  selectPortfolio: async (id: string) => {
    set({ isLoading: true, error: null })
    try {
      const summary = await apiClient.getPortfolioSummary(id)
      set({ selectedPortfolioId: id, selectedPortfolio: summary, isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to load portfolio'
      set({ error: message, isLoading: false })
    }
  },

  createPortfolio: async (name: string, description?: string) => {
    set({ isLoading: true, error: null })
    try {
      const portfolio = await apiClient.createPortfolio(name, description)
      const { portfolios } = get()
      set({ portfolios: [...portfolios, portfolio], isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to create portfolio'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  updatePortfolio: async (id: string, name: string, description?: string) => {
    set({ isLoading: true, error: null })
    try {
      const updated = await apiClient.updatePortfolio(id, name, description)
      const { portfolios } = get()
      const newPortfolios = portfolios.map(p => p.id === id ? updated : p)
      set({ portfolios: newPortfolios, isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to update portfolio'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  deletePortfolio: async (id: string) => {
    set({ isLoading: true, error: null })
    try {
      await apiClient.deletePortfolio(id)
      const { portfolios, selectedPortfolioId } = get()
      const newPortfolios = portfolios.filter(p => p.id !== id)
      
      let newSelected = selectedPortfolioId
      if (selectedPortfolioId === id) {
        newSelected = newPortfolios.length > 0 ? newPortfolios[0].id : null
      }
      
      set({
        portfolios: newPortfolios,
        selectedPortfolioId: newSelected,
        selectedPortfolio: null,
        isLoading: false,
      })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to delete portfolio'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  updatePrices: async (portfolioId: string) => {
    set({ isLoading: true, error: null })
    try {
      await apiClient.updatePortfolioPrices(portfolioId)
      // Refresh the portfolio summary
      await get().selectPortfolio(portfolioId)
      set({ isLoading: false })
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to update prices'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  clearError: () => set({ error: null }),
}))
