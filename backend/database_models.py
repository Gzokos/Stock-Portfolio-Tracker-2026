

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import uuid
from sqlalchemy import (
    Column, String, Integer, Float, Date, DateTime, Boolean, 
    Text, Numeric, BigInteger, ForeignKey, Index, UniqueConstraint,
    func, and_, or_, desc, event, create_engine
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.pool import NullPool
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

Base = declarative_base()
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://postgres:postgres@localhost:5432/stock_portfolio_tracker'
)



class User(Base):
    """User account model"""
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)

    # Relationships
    portfolios = relationship('Portfolio', back_populates='user', cascade='all, delete-orphan')
    api_keys = relationship('APIKey', back_populates='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<User {self.username}>"




class Portfolio(Base):
    """Portfolio container (user can have multiple)"""
    __tablename__ = 'portfolios'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_default = Column(Boolean, default=False)

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='unique_portfolio_name_per_user'),
        Index('idx_portfolios_user_id', 'user_id'),
    )

    # Relationships
    user = relationship('User', back_populates='portfolios')
    holdings = relationship('Holding', back_populates='portfolio', cascade='all, delete-orphan')
    transactions = relationship('Transaction', back_populates='portfolio', cascade='all, delete-orphan')
    metrics = relationship('PortfolioMetrics', back_populates='portfolio', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Portfolio {self.name}>"

class Stock(Base):
    """Stock master data"""
    __tablename__ = 'stocks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    company_name = Column(String(255), nullable=False)
    sector = Column(String(100))
    industry = Column(String(100))
    country = Column(String(50))
    currency = Column(String(3), default='USD')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    holdings = relationship('Holding', back_populates='stock')
    transactions = relationship('Transaction', back_populates='stock')
    price_history = relationship('PriceHistory', back_populates='stock', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Stock {self.ticker}>"


class Holding(Base):
    """Current stock position"""
    __tablename__ = 'holdings'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey('portfolios.id'), nullable=False, index=True)
    stock_id = Column(UUID(as_uuid=True), ForeignKey('stocks.id'), nullable=False, index=True)
    quantity = Column(Numeric(18, 4), nullable=False)
    average_cost = Column(Numeric(18, 6), nullable=False)
    current_price = Column(Numeric(18, 6))
    last_price_update = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        UniqueConstraint('portfolio_id', 'stock_id', name='unique_holding'),
        Index('idx_holdings_portfolio_id', 'portfolio_id'),
        Index('idx_holdings_stock_id', 'stock_id'),
        Index('idx_holdings_updated_at', 'updated_at'),
    )

    # Relationships
    portfolio = relationship('Portfolio', back_populates='holdings')
    stock = relationship('Stock', back_populates='holdings')

    @property
    def total_cost(self) -> Decimal:
        """Calculate total cost basis"""
        return self.quantity * self.average_cost

    @property
    def current_value(self) -> Decimal:
        """Calculate current market value"""
        if self.current_price is None:
            return Decimal('0')
        return self.quantity * self.current_price

    @property
    def unrealized_gain_loss(self) -> Decimal:
        """Calculate unrealized P&L in dollars"""
        return self.current_value - self.total_cost

    @property
    def unrealized_gain_loss_pct(self) -> float:
        """Calculate unrealized P&L percentage"""
        if self.total_cost == 0:
            return 0.0
        return float((self.unrealized_gain_loss / self.total_cost) * 100)

    def __repr__(self):
        return f"<Holding {self.stock.ticker}: {self.quantity} @ ${self.average_cost}>"


class Transaction(Base):
    """Buy/Sell transaction history"""
    __tablename__ = 'transactions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey('portfolios.id'), nullable=False, index=True)
    stock_id = Column(UUID(as_uuid=True), ForeignKey('stocks.id'), nullable=False, index=True)
    transaction_type = Column(String(10), nullable=False)  # BUY, SELL, DIVIDEND
    quantity = Column(Numeric(18, 4), nullable=False)
    price_per_share = Column(Numeric(18, 6), nullable=False)
    total_amount = Column(Numeric(18, 2), nullable=False)
    commission_fee = Column(Numeric(18, 2), default=Decimal('0.00'))
    transaction_date = Column(Date, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        Index('idx_transactions_portfolio_id', 'portfolio_id'),
        Index('idx_transactions_stock_id', 'stock_id'),
        Index('idx_transactions_type', 'transaction_type'),
        Index('idx_transactions_date', 'transaction_date'),
    )

    # Relationships
    portfolio = relationship('Portfolio', back_populates='transactions')
    stock = relationship('Stock', back_populates='transactions')

    @property
    def total_cost(self) -> Decimal:
        """Total cost including commission"""
        return self.total_amount + self.commission_fee

    def __repr__(self):
        return f"<Transaction {self.transaction_type} {self.quantity} {self.stock.ticker} on {self.transaction_date}>"



class PriceHistory(Base):
    """Daily historical prices"""
    __tablename__ = 'price_history'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey('stocks.id'), nullable=False, index=True)
    date = Column(Date, nullable=False)
    open_price = Column(Numeric(18, 6))
    high_price = Column(Numeric(18, 6))
    low_price = Column(Numeric(18, 6))
    close_price = Column(Numeric(18, 6), nullable=False)
    adjusted_close = Column(Numeric(18, 6))
    volume = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        UniqueConstraint('stock_id', 'date', name='unique_stock_date'),
        Index('idx_price_history_stock_date', 'stock_id', 'date'),
    )

    # Relationships
    stock = relationship('Stock', back_populates='price_history')

    def __repr__(self):
        return f"<PriceHistory {self.stock.ticker} {self.date}: ${self.close_price}>"


class PortfolioMetrics(Base):
    """Cached portfolio performance metrics"""
    __tablename__ = 'portfolio_metrics'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), ForeignKey('portfolios.id'), unique=True, nullable=False, index=True)
    total_invested = Column(Numeric(18, 2))
    current_value = Column(Numeric(18, 2))
    total_unrealized_gain_loss = Column(Numeric(18, 2))
    total_unrealized_gain_loss_pct = Column(Numeric(10, 4))
    volatility_30d = Column(Numeric(10, 6))
    volatility_60d = Column(Numeric(10, 6))
    volatility_90d = Column(Numeric(10, 6))
    sharpe_ratio_30d = Column(Numeric(10, 6))
    sharpe_ratio_60d = Column(Numeric(10, 6))
    sharpe_ratio_90d = Column(Numeric(10, 6))
    best_performing_stock = Column(String(10))
    worst_performing_stock = Column(String(10))
    last_calculated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    portfolio = relationship('Portfolio', back_populates='metrics')

    def __repr__(self):
        return f"<PortfolioMetrics {self.portfolio_id}>"


class APIKey(Base):
    """API credentials (encrypted)"""
    __tablename__ = 'api_keys'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    key_type = Column(String(50), nullable=False)  # ALPHA_VANTAGE, FINNHUB, etc.
    encrypted_key = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime)

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'key_type', name='unique_api_key'),
    )

    # Relationships
    user = relationship('User', back_populates='api_keys')

    def __repr__(self):
        return f"<APIKey {self.key_type}>"


class AuditLog(Base):
    """Audit trail for compliance"""
    __tablename__ = 'audit_log'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    table_name = Column(String(100), nullable=False)
    record_id = Column(UUID(as_uuid=True))
    action = Column(String(20), nullable=False)  # INSERT, UPDATE, DELETE
    old_values = Column(Text)  # JSON
    new_values = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    ip_address = Column(String(45))

    __table_args__ = (
        Index('idx_audit_log_user_id', 'user_id'),
        Index('idx_audit_log_table', 'table_name'),
    )

    def __repr__(self):
        return f"<AuditLog {self.action} on {self.table_name}>"


class DatabaseConnection:
    """Database connection manager"""

    def __init__(self, database_url: str = DATABASE_URL):
        """
        Initialize database connection
        
        Args:
            database_url: PostgreSQL connection string
        """
        self.engine = create_engine(
            database_url,
            echo=False,  
            pool_pre_ping=True,  
            poolclass=NullPool,  
        )
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def create_all_tables(self):
        """Create all tables in database"""
        Base.metadata.create_all(bind=self.engine)
        print("✓ Database tables created successfully")

    def drop_all_tables(self):
        """Drop all tables (CAUTION: Destructive)"""
        Base.metadata.drop_all(bind=self.engine)
        print("✓ All tables dropped")

    def get_session(self) -> Session:
        """Get new database session"""
        return self.SessionLocal()

    def health_check(self) -> bool:
        """Test database connection"""
        try:
            with self.engine.connect() as connection:
                connection.execute("SELECT 1")
            return True
        except Exception as e:
            print(f"Database connection failed: {e}")
            return False



def init_database():
    """Initialize database and create all tables"""
    db = DatabaseConnection()
    
    if db.health_check():
        print("✓ Database connection successful")
        db.create_all_tables()
        print("✓ Database initialized")
        return db
    else:
        raise ConnectionError("Failed to connect to database")


def test_models():
    """Test ORM models"""
    db = DatabaseConnection()
    session = db.get_session()

    try:
        # Create sample user
        user = User(
            email="investor@example.com",
            username="investor1",
            password_hash="hashed_password",
            first_name="John",
            last_name="Investor"
        )
        session.add(user)
        session.commit()
        print(f"✓ Created user: {user}")

        # Create portfolio
        portfolio = Portfolio(
            user_id=user.id,
            name="Main Portfolio",
            description="Primary investment portfolio"
        )
        session.add(portfolio)
        session.commit()
        print(f"✓ Created portfolio: {portfolio}")

        # Create stocks
        stocks = [
            Stock(ticker='AAPL', company_name='Apple Inc.', sector='Technology'),
            Stock(ticker='MSFT', company_name='Microsoft Corp.', sector='Technology'),
            Stock(ticker='GOOGL', company_name='Alphabet Inc.', sector='Technology'),
        ]
        session.add_all(stocks)
        session.commit()
        print(f"✓ Created {len(stocks)} stocks")

        # Create holdings
        holding = Holding(
            portfolio_id=portfolio.id,
            stock_id=stocks[0].id,  # AAPL
            quantity=Decimal('10.5'),
            average_cost=Decimal('150.25'),
            current_price=Decimal('180.50')
        )
        session.add(holding)
        session.commit()
        print(f"✓ Created holding: {holding}")
        print(f"  Total Cost: ${holding.total_cost}")
        print(f"  Current Value: ${holding.current_value}")
        print(f"  Unrealized P&L: ${holding.unrealized_gain_loss} ({holding.unrealized_gain_loss_pct:.2f}%)")

        print("\n✓ All model tests passed")

    except Exception as e:
        session.rollback()
        print(f"✗ Error: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    print("Initializing Stock Portfolio Tracker Database...\n")
    db = init_database()
    print("\nTesting ORM Models...\n")
    test_models()
