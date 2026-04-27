import { useEffect, useState } from 'react'
import { useAuthStore } from '../store/auth'
import { usePortfolioStore } from '../store/portfolio'
import { apiClient } from '../api/client'
import { RefreshCw, LogOut, Plus, X } from 'lucide-react'
import {
  PieChart, Pie, Cell, Tooltip as PieTooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as BarTooltip,
} from 'recharts'
import { useNavigate } from 'react-router-dom'

function CreatePortfolioModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const { createPortfolio } = usePortfolioStore()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) { setError('Name is required'); return }
    setLoading(true)
    try {
      await createPortfolio(name.trim(), description.trim() || undefined)
      onCreated()
      onClose()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create portfolio')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Create Portfolio</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>
        {error && <div className="mb-3 p-2 bg-danger-100 text-danger-700 rounded text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="My Portfolio"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Optional"
            />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={onClose} className="px-4 py-2 text-gray-600 hover:text-gray-900">Cancel</button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function AddTransactionModal({ portfolioId, onClose, onAdded }: { portfolioId: string; onClose: () => void; onAdded: () => void }) {
  const today = new Date().toISOString().split('T')[0]
  const [ticker, setTicker] = useState('')
  const [type, setType] = useState<'BUY' | 'SELL'>('BUY')
  const [quantity, setQuantity] = useState('')
  const [price, setPrice] = useState('')
  const [commission, setCommission] = useState('0')
  const [date, setDate] = useState(today)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ticker || !quantity || !price) { setError('Ticker, quantity and price are required'); return }
    setLoading(true)
    try {
      await apiClient.createTransaction(portfolioId, {
        ticker: ticker.toUpperCase(),
        transaction_type: type,
        quantity: parseFloat(quantity),
        price: parseFloat(price),
        commission: parseFloat(commission) || 0,
        transaction_date: date,
        notes: notes.trim() || undefined,
      })
      onAdded()
      onClose()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to add transaction')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Add Transaction</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>
        {error && <div className="mb-3 p-2 bg-danger-100 text-danger-700 rounded text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ticker *</label>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="IBM"
                autoFocus
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Type *</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as 'BUY' | 'SELL')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Quantity *</label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="10"
                min="0"
                step="any"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Price per Share *</label>
              <input
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="150.00"
                min="0"
                step="any"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Commission</label>
              <input
                type="number"
                value={commission}
                onChange={(e) => setCommission(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="0"
                min="0"
                step="any"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Date *</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Optional"
            />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={onClose} className="px-4 py-2 text-gray-600 hover:text-gray-900">Cancel</button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {loading ? 'Adding...' : 'Add Transaction'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const {
    portfolios,
    selectedPortfolio,
    isLoading,
    error,
    fetchPortfolios,
    selectPortfolio,
    updatePrices,
  } = usePortfolioStore()

  const [priceLoading, setPriceLoading] = useState(false)
  const [showCreatePortfolio, setShowCreatePortfolio] = useState(false)
  const [showAddTransaction, setShowAddTransaction] = useState(false)

  useEffect(() => {
    fetchPortfolios()
  }, [fetchPortfolios])

  const handleUpdatePrices = async () => {
    if (!selectedPortfolio) return
    setPriceLoading(true)
    try {
      await updatePrices(selectedPortfolio.portfolio_id)
    } finally {
      setPriceLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const handleTransactionAdded = () => {
    if (selectedPortfolio) selectPortfolio(selectedPortfolio.portfolio_id)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {showCreatePortfolio && (
        <CreatePortfolioModal
          onClose={() => setShowCreatePortfolio(false)}
          onCreated={() => fetchPortfolios()}
        />
      )}
      {showAddTransaction && selectedPortfolio && (
        <AddTransactionModal
          portfolioId={selectedPortfolio.portfolio_id}
          onClose={() => setShowAddTransaction(false)}
          onAdded={handleTransactionAdded}
        />
      )}

      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">Portfolio Tracker</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">{user?.email}</span>
            <button onClick={handleLogout} className="text-gray-600 hover:text-gray-900">
              <LogOut size={20} />
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Portfolio Selector */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="flex justify-between items-center">
            <div className="flex items-end gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Select Portfolio</label>
                <select
                  value={selectedPortfolio?.portfolio_id || ''}
                  onChange={(e) => e.target.value && selectPortfolio(e.target.value)}
                  className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {portfolios.length === 0 && <option value="">No portfolios yet</option>}
                  {portfolios.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <button
                onClick={() => setShowCreatePortfolio(true)}
                className="px-3 py-2 border border-primary-600 text-primary-600 rounded-lg hover:bg-primary-100 flex items-center gap-1 text-sm transition"
              >
                <Plus size={16} /> New Portfolio
              </button>
            </div>
            <div className="flex items-center gap-3">
              {selectedPortfolio && (
                <button
                  onClick={() => setShowAddTransaction(true)}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center gap-2 transition"
                >
                  <Plus size={18} /> Add Transaction
                </button>
              )}
              <button
                onClick={handleUpdatePrices}
                disabled={priceLoading || !selectedPortfolio}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 flex items-center gap-2 transition"
              >
                <RefreshCw size={18} />
                {priceLoading ? 'Updating...' : 'Update Prices'}
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-danger-100 text-danger-700 rounded-lg">{error}</div>
        )}

        {/* Empty state — no portfolios */}
        {portfolios.length === 0 && !isLoading && (
          <div className="text-center py-16">
            <p className="text-gray-500 mb-4">No portfolios yet. Create one to get started.</p>
            <button
              onClick={() => setShowCreatePortfolio(true)}
              className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 inline-flex items-center gap-2 transition"
            >
              <Plus size={20} /> Create Portfolio
            </button>
          </div>
        )}

        {/* Portfolio Summary */}
        {selectedPortfolio && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow p-6">
              <p className="text-sm text-gray-600">Total Invested</p>
              <p className="text-2xl font-bold text-gray-900">${selectedPortfolio.total_invested.toFixed(2)}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <p className="text-sm text-gray-600">Current Value</p>
              <p className="text-2xl font-bold text-gray-900">${selectedPortfolio.current_value.toFixed(2)}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <p className="text-sm text-gray-600">Unrealized Gain/Loss</p>
              <p className={`text-2xl font-bold ${selectedPortfolio.unrealized_gain_loss >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                ${selectedPortfolio.unrealized_gain_loss.toFixed(2)}
              </p>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <p className="text-sm text-gray-600">Return %</p>
              <p className={`text-2xl font-bold ${selectedPortfolio.return_percentage >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                {selectedPortfolio.return_percentage.toFixed(2)}%
              </p>
            </div>
          </div>
        )}

        {/* Charts */}
        {selectedPortfolio && selectedPortfolio.holdings.length > 0 && (() => {
          const PIE_COLORS = ['#0284c7','#0ea5e9','#38bdf8','#7dd3fc','#bae6fd','#0369a1','#075985']
          const pieData = selectedPortfolio.holdings.map((h) => ({
            name: h.ticker,
            value: parseFloat(h.current_value > 0 ? h.current_value.toFixed(2) : h.total_cost.toFixed(2)),
          }))
          const barData = selectedPortfolio.holdings.map((h) => ({
            ticker: h.ticker,
            gain: parseFloat(h.unrealized_gain_loss.toFixed(2)),
          }))
          return (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              {/* Allocation Pie */}
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-base font-semibold text-gray-900 mb-4">Portfolio Allocation</h2>
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(1)}%`}>
                      {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                    </Pie>
                    <PieTooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Gain/Loss Bar */}
              <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-base font-semibold text-gray-900 mb-4">Unrealized Gain / Loss</h2>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={barData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="ticker" tick={{ fontSize: 13 }} />
                    <YAxis tickFormatter={(v) => `$${v}`} tick={{ fontSize: 12 }} />
                    <BarTooltip formatter={(v: number) => [`$${v.toFixed(2)}`, 'Gain/Loss']} />
                    <Bar dataKey="gain" radius={[4, 4, 0, 0]}>
                      {barData.map((entry, i) => (
                        <Cell key={i} fill={entry.gain >= 0 ? '#16a34a' : '#dc2626'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )
        })()}

        {/* Holdings Table */}
        {selectedPortfolio && selectedPortfolio.holdings.length > 0 && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Holdings</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Ticker</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Quantity</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Avg Cost</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Current Price</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Current Value</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Gain/Loss</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedPortfolio.holdings.map((holding, idx) => (
                    <tr key={idx} className="border-b border-gray-200 hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-medium text-gray-900">{holding.ticker}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">{holding.quantity.toFixed(2)}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">${holding.average_cost.toFixed(2)}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {holding.current_price ? `$${holding.current_price.toFixed(2)}` : 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">${holding.current_value.toFixed(2)}</td>
                      <td className={`px-6 py-4 text-sm font-medium ${holding.unrealized_gain_loss >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                        ${holding.unrealized_gain_loss.toFixed(2)} ({holding.unrealized_gain_loss_pct.toFixed(2)}%)
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">{holding.weight_pct.toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Empty holdings state */}
        {selectedPortfolio && selectedPortfolio.holdings.length === 0 && (
          <div className="text-center py-12 bg-white rounded-lg shadow">
            <p className="text-gray-500 mb-4">No holdings yet. Add your first transaction.</p>
            <button
              onClick={() => setShowAddTransaction(true)}
              className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 inline-flex items-center gap-2 transition"
            >
              <Plus size={20} /> Add Transaction
            </button>
          </div>
        )}

        {isLoading && (
          <div className="text-center py-8">
            <p className="text-gray-600">Loading...</p>
          </div>
        )}
      </main>
    </div>
  )
}
