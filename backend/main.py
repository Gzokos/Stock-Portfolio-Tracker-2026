
import logging
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Query, Depends, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent))

from database_models import DatabaseConnection, User, Portfolio, Stock, Holding, Transaction
from alpha_vantage_client import AlphaVantageClient
from portfolio_service import PortfolioService
from auth import AuthService


load_dotenv()


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Stock Portfolio Tracker API",
    description="API for managing and analyzing stock portfolios",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


db = DatabaseConnection()
api_client = AlphaVantageClient()


security = HTTPBearer()




async def get_current_user(credentials = Depends(security)) -> User:
   
    session = db.get_session()
    try:
        auth_service = AuthService(session)
        token = credentials.credentials if hasattr(credentials, 'credentials') else str(credentials)
        user_id = auth_service.verify_token(token)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        user = auth_service.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user
    finally:
        session.close()




class RegisterRequest(BaseModel):
 
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class LoginRequest(BaseModel):
   
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours


class UserResponse(BaseModel):
    
    id: str
    email: str
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    created_at: str
    last_login: Optional[str] = None


class ChangePasswordRequest(BaseModel):
 
    old_password: str
    new_password: str = Field(..., min_length=8)


class StockResponse(BaseModel):
   
    ticker: str
    company_name: str
    sector: Optional[str] = None
    industry: Optional[str] = None

    class Config:
        from_attributes = True


class PriceQuote(BaseModel):
   
    ticker: str
    price: float
    change: float
    change_percent: float
    volume: int
    timestamp: str


class HistoricalPrice(BaseModel):
    
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class HoldingResponse(BaseModel):
    
    ticker: str
    company_name: str
    sector: Optional[str] = None
    quantity: float
    average_cost: float
    current_price: Optional[float] = None
    total_cost: float
    current_value: float
    unrealized_gain_loss: float
    unrealized_gain_loss_pct: float
    weight_pct: float
    last_updated: Optional[str] = None


class PortfolioCreate(BaseModel):
   
    name: str
    description: Optional[str] = None


class TransactionCreate(BaseModel):
   
    ticker: str
    transaction_type: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: Decimal
    price: Decimal
    commission: Decimal = Decimal('0')
    transaction_date: date
    notes: Optional[str] = None


class PortfolioSummary(BaseModel):
    
    portfolio_id: str
    name: str
    total_invested: float
    current_value: float
    unrealized_gain_loss: float
    return_percentage: float
    holdings_count: int
    top_position: Optional[str] = None
    holdings: List[HoldingResponse] = []


class HealthResponse(BaseModel):

    status: str
    database: str
    timestamp: str

@app.get("/", tags=["Info"])
async def root():
    
    return {
        "name": "Stock Portfolio Tracker API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }

class ConnectionManager:
    
    
    def __init__(self):
      
        self.active_connections: dict = {}
    
    async def connect(self, websocket: WebSocket, portfolio_id: str):
       
        await websocket.accept()
        if portfolio_id not in self.active_connections:
            self.active_connections[portfolio_id] = []
        self.active_connections[portfolio_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, portfolio_id: str):
        
        if portfolio_id in self.active_connections:
            self.active_connections[portfolio_id].remove(websocket)
            if not self.active_connections[portfolio_id]:
                del self.active_connections[portfolio_id]
    
    async def broadcast(self, portfolio_id: str, message: dict):
   
        if portfolio_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[portfolio_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"WebSocket send error: {e}")
                    disconnected.append(connection)
 
            for connection in disconnected:
                self.disconnect(connection, portfolio_id)


manager = ConnectionManager()


@app.websocket("/ws/portfolio/{portfolio_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    portfolio_id: str,
    token: str = None
):
    
    try:
        
        if not token:
            await websocket.close(code=1008, reason="No authentication token")
            return
        
        session = db.get_session()
        try:
            auth_service = AuthService(session)
            user_id = auth_service.verify_token(token)

            if not user_id:
                await websocket.close(code=1008, reason="Invalid token")
                return
            
        
            portfolio = session.query(Portfolio).filter(
                Portfolio.id == portfolio_id
            ).first()
            
            if not portfolio or str(portfolio.user_id) != str(user_id):
                await websocket.close(code=1008, reason="Unauthorized")
                return
            
        finally:
            session.close()
        
        
        await manager.connect(websocket, portfolio_id)
        logger.info(f"WebSocket connected for portfolio {portfolio_id}")
        
    
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "portfolio_id": portfolio_id,
            "timestamp": datetime.utcnow().isoformat()
        })
       
        try:
            while True:
            
                data = await websocket.receive_text()
                
            
                if data == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
        except WebSocketDisconnect:
            manager.disconnect(websocket, portfolio_id)
            logger.info(f"WebSocket disconnected for portfolio {portfolio_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
   
    db_health = db.health_check()
    
    return HealthResponse(
        status="healthy" if db_health else "unhealthy",
        database="connected" if db_health else "disconnected",
        timestamp=datetime.utcnow().isoformat()
    )



@app.post("/api/auth/register", response_model=UserResponse, tags=["Authentication"])
async def register(request: RegisterRequest):
  
    session = db.get_session()
    try:
        auth_service = AuthService(session)
        user, error = auth_service.register(
            email=request.email,
            username=request.username,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name
        )
        
        if error:
            raise HTTPException(status_code=400, detail=error)
        
        return UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            created_at=user.created_at.isoformat(),
            last_login=user.last_login.isoformat() if user.last_login else None
        )
    finally:
        session.close()


@app.post("/api/auth/login", response_model=TokenResponse, tags=["Authentication"])
async def login(request: LoginRequest):
   
    session = db.get_session()
    try:
        auth_service = AuthService(session)
        token, error = auth_service.login(request.email, request.password)
        
        if error:
            raise HTTPException(status_code=401, detail=error)
        
        return TokenResponse(access_token=token)
    finally:
        session.close()


@app.get("/api/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_profile(current_user: User = Depends(get_current_user)):
  
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        created_at=current_user.created_at.isoformat(),
        last_login=current_user.last_login.isoformat() if current_user.last_login else None
    )


@app.post("/api/auth/refresh", response_model=TokenResponse, tags=["Authentication"])
async def refresh_token(current_user: User = Depends(get_current_user)):
   
    session = db.get_session()
    try:
        auth_service = AuthService(session)
        new_token = auth_service.create_access_token(current_user.id)
        return TokenResponse(access_token=new_token)
    finally:
        session.close()


@app.post("/api/auth/change-password", tags=["Authentication"])
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user)
):
    
    session = db.get_session()
    try:
        auth_service = AuthService(session)
        success, error = auth_service.update_password(
            str(current_user.id),
            request.old_password,
            request.new_password
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=error)
        
        return {"status": "success", "message": "Password updated successfully"}
    finally:
        session.close()




@app.get("/api/stocks/search", response_model=List[dict], tags=["Stocks"])
async def search_stocks(
    keyword: str = Query(..., min_length=1, description="Stock name or ticker")
):
   
    try:
        results = api_client.get_symbol_search(keyword)
        return results
    except Exception as e:
        logger.error(f"Stock search error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/stocks/{ticker}/price", response_model=PriceQuote, tags=["Stocks"])
async def get_stock_price(ticker: str):
    
    try:
        price = api_client.get_current_price(ticker)
        return PriceQuote(
            ticker=price.ticker,
            price=price.price,
            change=price.change,
            change_percent=price.change_percent,
            volume=price.volume,
            timestamp=price.timestamp.isoformat()
        )
    except Exception as e:
        logger.error(f"Price fetch error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/stocks/{ticker}/history", response_model=List[HistoricalPrice], tags=["Stocks"])
async def get_stock_history(
    ticker: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve")
):
   
    try:
        prices = api_client.get_daily_prices(ticker, 'full')
        
        return [
            HistoricalPrice(
                date=p.date,
                open=float(p.open),
                high=float(p.high),
                low=float(p.low),
                close=float(p.close),
                volume=p.volume
            )
            for p in prices[-days:]
        ]
    except Exception as e:
        logger.error(f"History fetch error: {e}")
        raise HTTPException(status_code=400, detail=str(e))



@app.get("/api/portfolios", tags=["Portfolios"])
async def list_portfolios(current_user: User = Depends(get_current_user)):
    """
    List all portfolios for authenticated user
    
    Returns:
        List of user's portfolios
    """
    session = db.get_session()
    try:
        portfolios = session.query(Portfolio).filter(
            Portfolio.user_id == current_user.id
        ).all()
        
        return [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "created_at": p.created_at.isoformat(),
                "is_default": p.is_default,
                "holdings_count": len(p.holdings)
            }
            for p in portfolios
        ]
    finally:
        session.close()


@app.post("/api/portfolios", tags=["Portfolios"])
async def create_portfolio(
    request: PortfolioCreate,
    current_user: User = Depends(get_current_user)
):
   
    session = db.get_session()
    try:
        new_portfolio = Portfolio(
            id=str(__import__('uuid').uuid4()),
            user_id=current_user.id,
            name=request.name,
            description=request.description,
            is_default=False
        )
        session.add(new_portfolio)
        session.commit()
        
        return {
            "id": str(new_portfolio.id),
            "name": new_portfolio.name,
            "description": new_portfolio.description,
            "created_at": new_portfolio.created_at.isoformat(),
            "is_default": new_portfolio.is_default
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Portfolio creation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@app.put("/api/portfolios/{portfolio_id}", tags=["Portfolios"])
async def update_portfolio(
    portfolio_id: str,
    request: PortfolioCreate,
    current_user: User = Depends(get_current_user)
):
   
    session = db.get_session()
    try:
        portfolio = session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()
        
        if not portfolio or portfolio.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        portfolio.name = request.name
        if request.description is not None:
            portfolio.description = request.description
        
        session.commit()
        
        return {
            "id": str(portfolio.id),
            "name": portfolio.name,
            "description": portfolio.description,
            "created_at": portfolio.created_at.isoformat(),
            "is_default": portfolio.is_default
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Portfolio update error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@app.delete("/api/portfolios/{portfolio_id}", tags=["Portfolios"])
async def delete_portfolio(
    portfolio_id: str,
    current_user: User = Depends(get_current_user)
):
   
    session = db.get_session()
    try:
        portfolio = session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()
        
        if not portfolio or portfolio.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        if portfolio.is_default:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete default portfolio"
            )
        
        session.delete(portfolio)
        session.commit()
        
        return {
            "status": "success",
            "message": f"Portfolio {portfolio_id} deleted successfully"
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Portfolio deletion error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@app.get("/api/portfolios/{portfolio_id}", tags=["Portfolios"])
async def get_portfolio(
    portfolio_id: str,
    current_user: User = Depends(get_current_user)
):
  
    session = db.get_session()
    try:
        portfolio = session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()
        
        if not portfolio or portfolio.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        return {
            "id": str(portfolio.id),
            "user_id": str(portfolio.user_id),
            "name": portfolio.name,
            "description": portfolio.description,
            "created_at": portfolio.created_at.isoformat(),
            "is_default": portfolio.is_default
        }
    finally:
        session.close()


@app.get("/api/portfolios/{portfolio_id}/summary", response_model=PortfolioSummary, tags=["Portfolios"])
async def get_portfolio_summary(
    portfolio_id: str,
    current_user: User = Depends(get_current_user)
):
   
    session = db.get_session()
    try:
        portfolio = session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()
        
        if not portfolio or portfolio.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        service = PortfolioService(session, api_client)
        summary = service.get_portfolio_summary(portfolio_id)
        return summary
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        session.close()


@app.get("/api/portfolios/{portfolio_id}/holdings", response_model=List[HoldingResponse], tags=["Holdings"])
async def list_holdings(
    portfolio_id: str,
    current_user: User = Depends(get_current_user)
):
    
    session = db.get_session()
    try:
        portfolio = session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()
        
        if not portfolio or portfolio.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        holdings = []
        total_value = sum(h.current_value for h in portfolio.holdings)
        
        for h in portfolio.holdings:
            holdings.append(HoldingResponse(
                ticker=h.stock.ticker,
                company_name=h.stock.company_name,
                sector=h.stock.sector,
                quantity=float(h.quantity),
                average_cost=float(h.average_cost),
                current_price=float(h.current_price) if h.current_price else None,
                total_cost=float(h.total_cost),
                current_value=float(h.current_value),
                unrealized_gain_loss=float(h.unrealized_gain_loss),
                unrealized_gain_loss_pct=h.unrealized_gain_loss_pct,
                weight_pct=float(h.current_value / total_value * 100) if total_value > 0 else 0,
                last_updated=h.last_price_update.isoformat() if h.last_price_update else None
            ))
        
        return holdings
    finally:
        session.close()


@app.get("/api/portfolios/{portfolio_id}/transactions", tags=["Transactions"])
async def get_transactions(
    portfolio_id: str,
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000)
):

    session = db.get_session()
    try:
        portfolio = session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()
        
        if not portfolio or portfolio.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        service = PortfolioService(session, api_client)
        transactions = service.get_transaction_history(portfolio_id, limit)
        return transactions
    finally:
        session.close()



@app.post("/api/portfolios/{portfolio_id}/transactions", tags=["Transactions"])
async def create_transaction(
    portfolio_id: str,
    request: TransactionCreate,
    current_user: User = Depends(get_current_user)
):
    try:
        portfolio = session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()
        
        if not portfolio or portfolio.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Portfolio not found")
  
        service = PortfolioService(session, api_client)
        transaction = service.record_transaction(
            portfolio_id=portfolio_id,
            ticker=request.ticker,
            transaction_type=request.transaction_type,
            quantity=request.quantity,
            price=request.price,
            commission=request.commission,
            transaction_date=request.transaction_date,
            notes=request.notes
        )
        
        return {
            "id": str(transaction.id),
            "portfolio_id": str(transaction.portfolio_id),
            "ticker": request.ticker,
            "type": transaction.transaction_type,
            "quantity": float(transaction.quantity),
            "price": float(transaction.price_per_share),
            "commission": float(transaction.commission_fee),
            "total": float(transaction.quantity * transaction.price_per_share + transaction.commission_fee),
            "date": transaction.transaction_date.isoformat(),
            "notes": transaction.notes
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction creation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@app.delete("/api/portfolios/{portfolio_id}/transactions/{transaction_id}", tags=["Transactions"])
async def delete_transaction(
    portfolio_id: str,
    transaction_id: str,
    current_user: User = Depends(get_current_user)
):
   
    session = db.get_session()
    try:
        portfolio = session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()
        
        if not portfolio or portfolio.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        transaction = session.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.portfolio_id == portfolio_id
        ).first()
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        session.delete(transaction)
        session.commit()
        
        return {
            "status": "success",
            "message": f"Transaction {transaction_id} deleted successfully"
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction deletion error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()
@app.post("/api/portfolios/{portfolio_id}/update-prices", tags=["Portfolios"])
async def update_portfolio_prices(
    portfolio_id: str,
    current_user: User = Depends(get_current_user)
):
    
    session = db.get_session()
    try:
        portfolio = session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()
        
        if not portfolio or portfolio.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        
        service = PortfolioService(session, api_client)
        service.update_prices(portfolio_id)
        
   
        summary = service.get_portfolio_summary(portfolio_id)
        
       
        await manager.broadcast(portfolio_id, {
            "type": "price_update",
            "portfolio_id": portfolio_id,
            "data": {
                "total_value": summary['current_value'],
                "unrealized_gain_loss": summary['unrealized_gain_loss'],
                "return_percentage": summary['return_percentage']
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return {
            "status": "success",
            "message": f"Prices updated for portfolio {portfolio_id}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Price update error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return {
        "error": exc.detail,
        "status_code": exc.status_code,
        "timestamp": datetime.utcnow().isoformat()
    }
@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("Starting Stock Portfolio Tracker API...")
    
    
    if db.health_check():
        logger.info("Database connection successful")
    else:
        logger.error("Database connection failed")
    
   
    try:
        api_client.get_current_price("AAPL")
        logger.info(" Alpha Vantage API connection successful")
    except Exception as e:
        logger.warning(f"Alpha Vantage API test failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    
    logger.info("Shutting down Stock Portfolio Tracker API...")

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    logger.info(f"Starting server on {host}:{port}")
    
 
    use_reload = os.getenv("ENVIRONMENT") == "development"
    
  
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        reload=False  
    )
