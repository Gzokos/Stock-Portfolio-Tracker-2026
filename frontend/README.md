# Stock Portfolio Tracker - Frontend

React TypeScript frontend for the Stock Portfolio Tracker application.

## Features

- 🔐 JWT-based authentication
- 📊 Real-time portfolio dashboard
- 💼 Multi-portfolio management
- 💰 Holdings and performance tracking
- 🔄 Real-time price updates via WebSocket
- 📈 Portfolio summary with metrics

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **React Router** - Routing
- **Zustand** - State management
- **Axios** - HTTP client
- **Lucide React** - Icons
- **Recharts** - Charts and graphs

## Getting Started

### Prerequisites

- Node.js 16+
- npm or yarn

### Installation

```bash
cd frontend
npm install
```

### Environment Setup

Create a `.env.local` file:

```env
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000
```

### Development

```bash
npm run dev
```

The app will run at `http://localhost:3000`

### Build

```bash
npm run build
```

### Type Checking

```bash
npm run type-check
```

### Linting

```bash
npm run lint
```

## Project Structure

```
src/
├── api/              # API client helper
├── components/       # Reusable UI components
├── pages/            # Page components
├── store/            # Zustand stores (auth, portfolio)
├── App.tsx           # Main app component
├── main.tsx          # Entry point
└── index.css         # Global styles
```

## API Integration

The frontend connects to the backend API at:
- **Base URL**: `http://localhost:8000/api`
- **WebSocket**: `ws://localhost:8000`

### Authentication

- Login/Register endpoints handle JWT token management
- Token stored in localStorage
- Automatic token refresh on page load

### Real-time Updates

WebSocket connections are established for each portfolio:
```
/ws/portfolio/{portfolio_id}?token={jwt_token}
```

## Key Components

### LoginPage
- User authentication
- Registration link
- Error handling

### DashboardPage
- Portfolio selector
- Summary metrics
- Holdings table
- Price update trigger
- User profile and logout

## State Management

### Auth Store (`store/auth.ts`)
- User login/registration
- Profile management
- Token management
- Password change

### Portfolio Store (`store/portfolio.ts`)
- Portfolio list
- Selected portfolio management
- Portfolio CRUD operations
- Price updates

## Future Enhancements

- [ ] Chart visualizations (Recharts integration)
- [ ] Transaction history view
- [ ] Advanced search/filtering
- [ ] Export portfolio data
- [ ] Portfolio comparison
- [ ] Performance analytics
- [ ] Watchlist management
- [ ] Mobile app version

## Troubleshooting

### API Connection Issues
- Ensure backend is running on `http://localhost:8000`
- Check VITE_API_URL in .env.local
- Check CORS settings if using different domain

### WebSocket Connection Issues
- Verify ws:// protocol (or wss:// for production)
- Check JWT token is valid
- See browser console for detailed errors

### Build Issues
- Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Clear Vite cache: `rm -rf dist`

## License

MIT
