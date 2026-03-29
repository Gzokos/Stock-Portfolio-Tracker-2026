
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from database_models import (
    Portfolio, Stock, Holding, Transaction, PriceHistory
)
from alpha_vantage_client import AlphaVantageClient

logger = logging.getLogger(__name__)


class PortfolioService:
  

    def __init__(self, session: Session, api_client: AlphaVantageClient):
        
        self.session = session
        self.api = api_client

    def buy_stock(
        self,
        portfolio_id: str,
        ticker: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal('0'),
        transaction_date: date = None,
        notes: str = None
    ) -> Holding:
     
        transaction_date = transaction_date or date.today()
        total_amount = quantity * price

        logger.info(f"Recording BUY: {quantity} {ticker} @ ${price}")

        try:
            # Get or create stock record
            stock = self.session.query(Stock).filter(
                Stock.ticker == ticker.upper()
            ).first()

            if not stock:
                logger.info(f"Creating new stock record for {ticker}")
                stock = Stock(
                    ticker=ticker.upper(),
                    company_name=ticker.upper()
                )
                self.session.add(stock)
                self.session.flush()

            # Create transaction record
            transaction = Transaction(
                portfolio_id=portfolio_id,
                stock_id=stock.id,
                transaction_type='BUY',
                quantity=quantity,
                price_per_share=price,
                total_amount=total_amount,
                commission_fee=commission,
                transaction_date=transaction_date,
                notes=notes
            )
            self.session.add(transaction)

            # Get or create holding
            holding = self.session.query(Holding).filter(
                Holding.portfolio_id == portfolio_id,
                Holding.stock_id == stock.id
            ).first()

            if holding:
                # Update weighted average cost
                old_cost_basis = holding.quantity * holding.average_cost
                new_cost = total_amount + commission
                total_shares = holding.quantity + quantity

                # Weighted average: (old_cost + new_cost) / total_shares
                holding.average_cost = (old_cost_basis + new_cost) / total_shares
                holding.quantity = total_shares

                logger.info(f"Updated existing holding: qty={total_shares}, avg_cost=${holding.average_cost}")
            else:
                # Create new holding
                # Average cost includes commission per share
                avg_cost_with_commission = price + (commission / quantity if quantity > 0 else 0)

                holding = Holding(
                    portfolio_id=portfolio_id,
                    stock_id=stock.id,
                    quantity=quantity,
                    average_cost=avg_cost_with_commission
                )
                self.session.add(holding)
                logger.info(f"Created new holding: {quantity} shares @ ${avg_cost_with_commission}")

            self.session.commit()
            logger.info("Transaction committed successfully")

            return holding

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error recording purchase: {e}")
            raise

    def sell_stock(
        self,
        portfolio_id: str,
        ticker: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal('0'),
        transaction_date: date = None,
        notes: str = None
    ) -> Dict:
        
        transaction_date = transaction_date or date.today()
        total_proceeds = quantity * price

        logger.info(f"Recording SELL: {quantity} {ticker} @ ${price}")

        try:
            # Get stock
            stock = self.session.query(Stock).filter(
                Stock.ticker == ticker.upper()
            ).first()

            if not stock:
                raise ValueError(f"Stock {ticker} not found")

            # Get holding
            holding = self.session.query(Holding).filter(
                Holding.portfolio_id == portfolio_id,
                Holding.stock_id == stock.id
            ).first()

            if not holding:
                raise ValueError(f"No position in {ticker}")

            if holding.quantity < quantity:
                raise ValueError(
                    f"Cannot sell {quantity} shares, only have {holding.quantity}"
                )

            # Calculate realized gain/loss
            cost_basis = quantity * holding.average_cost
            realized_gain_loss = total_proceeds - commission - cost_basis
            realized_gain_loss_pct = (
                (realized_gain_loss / cost_basis * 100) if cost_basis > 0 else 0
            )

            # Create transaction record
            transaction = Transaction(
                portfolio_id=portfolio_id,
                stock_id=stock.id,
                transaction_type='SELL',
                quantity=quantity,
                price_per_share=price,
                total_amount=total_proceeds,
                commission_fee=commission,
                transaction_date=transaction_date,
                notes=notes
            )
            self.session.add(transaction)

            # Update holding
            holding.quantity -= quantity

            # If no shares left, optionally delete holding
            if holding.quantity <= 0:
                self.session.delete(holding)
                logger.info(f"Sold all shares, removed holding")
            else:
                logger.info(f"Updated holding after sale: remaining {holding.quantity} shares")

            self.session.commit()

            logger.info(
                f"Sale recorded - Realized P&L: ${realized_gain_loss} ({realized_gain_loss_pct:.2f}%)"
            )

            return {
                'ticker': ticker,
                'quantity': quantity,
                'sale_price': float(price),
                'gross_proceeds': float(total_proceeds),
                'commission': float(commission),
                'net_proceeds': float(total_proceeds - commission),
                'cost_basis': float(cost_basis),
                'realized_gain_loss': float(realized_gain_loss),
                'realized_gain_loss_pct': realized_gain_loss_pct,
                'date': transaction_date.isoformat()
            }

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error recording sale: {e}")
            raise

    def record_transaction(
        self,
        portfolio_id: str,
        ticker: str,
        transaction_type: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal('0'),
        transaction_date: date = None,
        notes: str = None
    ) -> Transaction:
        
        t_type = transaction_type.upper()
        if t_type == 'BUY':
            self.buy_stock(
                portfolio_id=portfolio_id,
                ticker=ticker,
                quantity=quantity,
                price=price,
                commission=commission,
                transaction_date=transaction_date,
                notes=notes
            )
        elif t_type == 'SELL':
            self.sell_stock(
                portfolio_id=portfolio_id,
                ticker=ticker,
                quantity=quantity,
                price=price,
                commission=commission,
                transaction_date=transaction_date,
                notes=notes
            )
        else:
            raise ValueError(f"Invalid transaction type: {transaction_type}")

        stock = self.session.query(Stock).filter(
            Stock.ticker == ticker.upper()
        ).first()

        transaction = self.session.query(Transaction).filter(
            Transaction.portfolio_id == portfolio_id,
            Transaction.stock_id == stock.id,
            Transaction.transaction_type == t_type
        ).order_by(Transaction.created_at.desc()).first()

        return transaction

    def get_holding(self, portfolio_id: str, ticker: str) -> Optional[Holding]:
       
        stock = self.session.query(Stock).filter(
            Stock.ticker == ticker.upper()
        ).first()

        if not stock:
            return None

        return self.session.query(Holding).filter(
            Holding.portfolio_id == portfolio_id,
            Holding.stock_id == stock.id
        ).first()

    def update_prices(self, portfolio_id: str, use_cache: bool = True):
       
        logger.info(f"Updating prices for portfolio {portfolio_id}")

        portfolio = self.session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()

        if not portfolio:
            logger.error(f"Portfolio {portfolio_id} not found")
            return

        updated_count = 0
        failed_count = 0

        for holding in portfolio.holdings:
            try:
                # Get current price from API
                price_data = self.api.get_current_price(holding.stock.ticker)
                holding.current_price = Decimal(str(price_data.price))
                holding.last_price_update = datetime.utcnow()

                # Store in price history
                price_history = PriceHistory(
                    stock_id=holding.stock_id,
                    date=datetime.utcnow().date(),
                    close_price=Decimal(str(price_data.price))
                )
                # Use merge for upsert functionality
                self.session.merge(price_history)

                updated_count += 1
                logger.info(
                    f"Updated {holding.stock.ticker}: ${price_data.price} "
                    f"(change: {price_data.change_percent:+.2f}%)"
                )

            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to update {holding.stock.ticker}: {e}")

        self.session.commit()
        logger.info(
            f"Price update complete: {updated_count} updated, {failed_count} failed"
        )

    def get_portfolio_summary(self, portfolio_id: str) -> Dict:
     
        portfolio = self.session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()

        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        holdings = portfolio.holdings
        
        if not holdings:
            return {
                'portfolio_id': str(portfolio.id),
                'name': portfolio.name,
                'total_invested': 0.0,
                'current_value': 0.0,
                'unrealized_gain_loss': 0.0,
                'return_percentage': 0.0,
                'holdings_count': 0,
                'holdings': []
            }

        # Calculate totals
        total_invested = sum(h.total_cost for h in holdings)
        current_value = sum(h.current_value for h in holdings)
        unrealized_gain_loss = current_value - total_invested

        return_percentage = (
            (unrealized_gain_loss / total_invested * 100)
            if total_invested > 0 else 0
        )

        # Build holdings list
        holdings_list = []
        for h in holdings:
            holdings_list.append({
                'ticker': h.stock.ticker,
                'company_name': h.stock.company_name,
                'sector': h.stock.sector,
                'quantity': float(h.quantity),
                'average_cost': float(h.average_cost),
                'current_price': float(h.current_price) if h.current_price else None,
                'total_cost': float(h.total_cost),
                'current_value': float(h.current_value),
                'unrealized_gain_loss': float(h.unrealized_gain_loss),
                'unrealized_gain_loss_pct': h.unrealized_gain_loss_pct,
                'weight_pct': float(h.current_value / current_value * 100) if current_value > 0 else 0,
                'last_updated': h.last_price_update.isoformat() if h.last_price_update else None
            })

        return {
            'portfolio_id': str(portfolio.id),
            'name': portfolio.name,
            'total_invested': float(total_invested),
            'current_value': float(current_value),
            'unrealized_gain_loss': float(unrealized_gain_loss),
            'return_percentage': return_percentage,
            'holdings_count': len(holdings),
            'top_position': max(holdings, key=lambda h: h.current_value).stock.ticker if holdings else None,
            'holdings': holdings_list
        }

    def get_transaction_history(
        self,
        portfolio_id: str,
        limit: int = 100
    ) -> List[Dict]:
       
        transactions = self.session.query(Transaction).filter(
            Transaction.portfolio_id == portfolio_id
        ).order_by(Transaction.transaction_date.desc()).limit(limit).all()

        return [
            {
                'id': str(t.id),
                'type': t.transaction_type,
                'ticker': t.stock.ticker,
                'quantity': float(t.quantity),
                'price': float(t.price_per_share),
                'total_amount': float(t.total_amount),
                'commission': float(t.commission_fee),
                'total_cost': float(t.total_amount + t.commission_fee),
                'date': t.transaction_date.isoformat(),
                'notes': t.notes
            }
            for t in transactions
        ]

    def calculate_cost_basis(self, portfolio_id: str) -> float:
        
        holdings = self.session.query(Holding).filter(
            Holding.portfolio_id == portfolio_id
        ).all()

        return sum(h.total_cost for h in holdings)


# Example usage
if __name__ == "__main__":
    from database_models import DatabaseConnection

    db = DatabaseConnection()
    session = db.get_session()
    api = AlphaVantageClient()

    service = PortfolioService(session, api)


    print("Portfolio service ready for use")
