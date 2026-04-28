import axios, { AxiosInstance } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  username: string
  password: string
  first_name: string
  last_name: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface UserResponse {
  id: string
  email: string
  username: string
  first_name: string
  last_name: string
  created_at: string
  last_login?: string
}

export interface Portfolio {
  id: string
  name: string
  description?: string
  created_at: string
  is_default: boolean
  holdings_count?: number
}

export interface Holding {
  ticker: string
  company_name: string
  sector?: string
  quantity: number
  average_cost: number
  current_price?: number
  total_cost: number
  current_value: number
  unrealized_gain_loss: number
  unrealized_gain_loss_pct: number
  weight_pct: number
  last_updated?: string
}

export interface PortfolioSummary {
  portfolio_id: string
  name: string
  total_invested: number
  current_value: number
  unrealized_gain_loss: number
  return_percentage: number
  holdings_count: number
  top_position?: string
  holdings: Holding[]
}

export interface StockPrice {
  ticker: string
  price: number
  change: number
  change_percent: number
  volume: number
  timestamp: string
}

class ApiClient {
  private client: AxiosInstance
  private token: string | null = null

  constructor() {
    this.token = localStorage.getItem('access_token')
    
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (this.token) {
      this.setAuthToken(this.token)
    }
  }

  setAuthToken(token: string) {
    this.token = token
    this.client.defaults.headers.common['Authorization'] = `Bearer ${token}`
    localStorage.setItem('access_token', token)
  }

  clearAuthToken() {
    this.token = null
    delete this.client.defaults.headers.common['Authorization']
    localStorage.removeItem('access_token')
  }

  // Auth endpoints
  async register(data: RegisterRequest): Promise<UserResponse> {
    const response = await this.client.post('/auth/register', data)
    return response.data
  }

  async login(data: LoginRequest): Promise<TokenResponse> {
    const response = await this.client.post('/auth/login', data)
    return response.data
  }

  async getProfile(): Promise<UserResponse> {
    const response = await this.client.get('/auth/me')
    return response.data
  }

  async refreshToken(): Promise<TokenResponse> {
    const response = await this.client.post('/auth/refresh')
    return response.data
  }

  async changePassword(oldPassword: string, newPassword: string): Promise<any> {
    const response = await this.client.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
    return response.data
  }

  // Portfolio endpoints
  async listPortfolios(): Promise<Portfolio[]> {
    const response = await this.client.get('/portfolios')
    return response.data
  }

  async getPortfolio(id: string): Promise<Portfolio> {
    const response = await this.client.get(`/portfolios/${id}`)
    return response.data
  }

  async createPortfolio(name: string, description?: string): Promise<Portfolio> {
    const response = await this.client.post('/portfolios', {
      name,
      description,
    })
    return response.data
  }

  async updatePortfolio(id: string, name: string, description?: string): Promise<Portfolio> {
    const response = await this.client.put(`/portfolios/${id}`, {
      name,
      description,
    })
    return response.data
  }

  async deletePortfolio(id: string): Promise<any> {
    const response = await this.client.delete(`/portfolios/${id}`)
    return response.data
  }

  async getPortfolioSummary(id: string): Promise<PortfolioSummary> {
    const response = await this.client.get(`/portfolios/${id}/summary`)
    return response.data
  }

  async getPortfolioHoldings(id: string): Promise<Holding[]> {
    const response = await this.client.get(`/portfolios/${id}/holdings`)
    return response.data
  }

  async updatePortfolioPrices(id: string): Promise<any> {
    const response = await this.client.post(`/portfolios/${id}/update-prices`)
    return response.data
  }

  async createTransaction(portfolioId: string, data: {
    ticker: string
    transaction_type: 'BUY' | 'SELL'
    quantity: number
    price: number
    commission: number
    transaction_date: string
    notes?: string
  }): Promise<any> {
    const response = await this.client.post(`/portfolios/${portfolioId}/transactions`, data)
    return response.data
  }

  // Stock endpoints
  async searchStocks(keyword: string): Promise<any[]> {
    const response = await this.client.get('/stocks/search', {
      params: { keyword },
    })
    return response.data
  }

  async getStockPrice(ticker: string): Promise<StockPrice> {
    const response = await this.client.get(`/stocks/${ticker}/price`)
    return response.data
  }

  async getStockHistory(ticker: string, days?: number): Promise<any[]> {
    const response = await this.client.get(`/stocks/${ticker}/history`, {
      params: { days: days || 30 },
    })
    return response.data
  }

  // WebSocket connection
  connectWebSocket(portfolioId: string, onMessage: (data: any) => void): WebSocket {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/portfolio/${portfolioId}?token=${this.token}`
    
    const ws = new WebSocket(wsUrl)
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      onMessage(data)
    }

    return ws
  }
}

export const apiClient = new ApiClient()
