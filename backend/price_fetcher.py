

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
import time

from alpha_vantage_client import AlphaVantageClient
from database_models import (
    DatabaseConnection, Stock, Holding, PriceHistory,
    Portfolio, PortfolioMetrics
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class PriceFetcher:
   

    def __init__(self, db: DatabaseConnection = None, 
                 api_client: AlphaVantageClient = None):
       
        self.db = db or DatabaseConnection()
        self.api = api_client or AlphaVantageClient()
        self.session = self.db.get_session()

    def __del__(self):
     
        if hasattr(self, 'session'):
            self.session.close()

    def update_portfolio_prices(self, portfolio_id: str):
        
        logger.info(f"Updating prices for portfolio {portfolio_id}")

        portfolio = self.session.query(Portfolio).filter(
            Portfolio.id == portfolio_id
        ).first()

        if not portfolio:
            logger.error(f"Portfolio {portfolio_id} not found")
            return

        tickers = list(set(h.stock.ticker for h in portfolio.holdings))
        
        if not tickers:
            logger.warning(f"Portfolio {portfolio_id} has no holdings")
            return

        prices = self.api.batch_fetch_prices(tickers)

  
        for holding in portfolio.holdings:
            ticker = holding.stock.ticker
            price_data = prices.get(ticker)

            if price_data:
                holding.current_price = Decimal(str(price_data.price))
                holding.last_price_update = datetime.utcnow()
                logger.info(f"Updated {ticker}: ${price_data.price}")
            else:
                logger.warning(f"Failed to fetch price for {ticker}")

        self.session.commit()
        logger.info(f"Portfolio prices updated")

    def update_all_portfolios(self):
      
        logger.info("Updating prices for all portfolios")

        portfolios = self.session.query(Portfolio).all()
        logger.info(f"Found {len(portfolios)} portfolios")

        for portfolio in portfolios:
            try:
                self.update_portfolio_prices(str(portfolio.id))
            except Exception as e:
                logger.error(f"Error updating portfolio {portfolio.id}: {e}")
                continue

        logger.info("All portfolios updated")

    def fetch_historical_data(self, ticker: str, days: int = 100):
        
        logger.info(f"Fetching historical data for {ticker}")

        try:
   
            stock = self.session.query(Stock).filter(
                Stock.ticker == ticker.upper()
            ).first()

            if not stock:
                logger.warning(f"Stock {ticker} not found, creating new record")
                stock = Stock(ticker=ticker.upper(), company_name=ticker)
                self.session.add(stock)
                self.session.flush()

            prices = self.api.get_daily_prices(ticker, 'compact')

          
            inserted_count = 0
            for price in prices[-days:]:
                existing = self.session.query(PriceHistory).filter(
                    PriceHistory.stock_id == stock.id,
                    PriceHistory.date == price.date
                ).first()

                if not existing:
                    history = PriceHistory(
                        stock_id=stock.id,
                        date=price.date,
                        open_price=Decimal(str(price.open)),
                        high_price=Decimal(str(price.high)),
                        low_price=Decimal(str(price.low)),
                        close_price=Decimal(str(price.close)),
                        adjusted_close=Decimal(str(price.adjusted_close)),
                        volume=price.volume
                    )
                    self.session.add(history)
                    inserted_count += 1

            self.session.commit()
            logger.info(f"Stored {inserted_count} historical records for {ticker}")

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error fetching historical data for {ticker}: {e}")

    def fill_missing_data(self, ticker: str):
        
        logger.info(f"Checking for missing data for {ticker}")

        stock = self.session.query(Stock).filter(
            Stock.ticker == ticker.upper()
        ).first()

        if not stock:
            logger.warning(f"Stock {ticker} not found")
            return

        # Get date range of existing data
        min_date_result = self.session.query(
            func.min(PriceHistory.date)
        ).filter(PriceHistory.stock_id == stock.id).first()

        max_date_result = self.session.query(
            func.max(PriceHistory.date)
        ).filter(PriceHistory.stock_id == stock.id).first()

        if not min_date_result[0] or not max_date_result[0]:
            logger.warning(f"No existing data for {ticker}")
            return

        # Find gaps
        gaps = self._find_date_gaps(stock.id, min_date_result[0], max_date_result[0])

        if gaps:
            logger.info(f"Found {len(gaps)} missing dates for {ticker}")
            # Fetch new data to fill gaps
            self.fetch_historical_data(ticker, days=365)
        else:
            logger.info(f"No gaps found for {ticker}")

    def _find_date_gaps(self, stock_id: str, start_date: date, end_date: date) -> List[date]:
   
        # Get all existing dates
        existing_dates = set(
            r[0] for r in self.session.query(PriceHistory.date).filter(
                PriceHistory.stock_id == stock_id,
                PriceHistory.date >= start_date,
                PriceHistory.date <= end_date
            ).all()
        )

        missing = []
        current = start_date
        while current <= end_date:
            # Skip weekends
            if current.weekday() < 5:  # Mon=0, Fri=4
                if current not in existing_dates:
                    missing.append(current)
            current += timedelta(days=1)

        return missing

    def calculate_metrics(self, portfolio_id: str):
       
        logger.info(f"Calculating metrics for portfolio {portfolio_id}")

        try:
            portfolio = self.session.query(Portfolio).filter(
                Portfolio.id == portfolio_id
            ).first()

            if not portfolio:
                logger.error(f"Portfolio {portfolio_id} not found")
                return

            holdings = portfolio.holdings
            if not holdings:
                logger.warning(f"Portfolio {portfolio_id} has no holdings")
                return

            # Calculate basic metrics
            total_invested = sum(Decimal(str(h.total_cost)) for h in holdings)
            current_value = sum(Decimal(str(h.current_value)) for h in holdings)
            unrealized_gain_loss = current_value - total_invested

            total_return_pct = (
                (unrealized_gain_loss / total_invested * 100)
                if total_invested > 0 else Decimal('0')
            )

            # Find best and worst performers
            best_stock = max(holdings, key=lambda h: h.unrealized_gain_loss_pct or 0)
            worst_stock = min(holdings, key=lambda h: h.unrealized_gain_loss_pct or 0)

            # Update or create metrics record
            metrics = self.session.query(PortfolioMetrics).filter(
                PortfolioMetrics.portfolio_id == portfolio_id
            ).first()

            if metrics:
                metrics.total_invested = total_invested
                metrics.current_value = current_value
                metrics.total_unrealized_gain_loss = unrealized_gain_loss
                metrics.total_unrealized_gain_loss_pct = total_return_pct
                metrics.best_performing_stock = best_stock.stock.ticker
                metrics.worst_performing_stock = worst_stock.stock.ticker
                metrics.last_calculated = datetime.utcnow()
            else:
                metrics = PortfolioMetrics(
                    portfolio_id=portfolio_id,
                    total_invested=total_invested,
                    current_value=current_value,
                    total_unrealized_gain_loss=unrealized_gain_loss,
                    total_unrealized_gain_loss_pct=total_return_pct,
                    best_performing_stock=best_stock.stock.ticker,
                    worst_performing_stock=worst_stock.stock.ticker
                )
                self.session.add(metrics)

            self.session.commit()
            logger.info(f"Metrics calculated for portfolio {portfolio_id}")

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error calculating metrics: {e}")

    def run_daily_update(self):
       
        logger.info("=" * 60)
        logger.info("Starting daily price update")
        logger.info("=" * 60)

        start_time = datetime.utcnow()

        self.update_all_portfolios()

        
        portfolios = self.session.query(Portfolio).all()
        for portfolio in portfolios:
            self.calculate_metrics(str(portfolio.id))

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info("=" * 60)
        logger.info(f"Daily update complete (took {elapsed:.1f}s)")
        logger.info("=" * 60)



def schedule_daily_updates():

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        import atexit

        scheduler = BackgroundScheduler()
        fetcher = PriceFetcher()

   
        scheduler.add_job(
            func=fetcher.run_daily_update,
            trigger="cron",
            hour=20,  
            minute=0,
            id='daily_price_update',
            name='Daily Price Update',
            replace_existing=True
        )

        scheduler.start()

        atexit.register(lambda: scheduler.shutdown())

        logger.info("Price update scheduler started (daily at 4 PM ET)")

    except ImportError:
        logger.warning("APScheduler not installed. Install with: pip install apscheduler")




if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Stock Price Fetcher')
    parser.add_argument(
        '--action',
        choices=['update-all', 'update-portfolio', 'fetch-history', 'calculate-metrics'],
        default='update-all',
        help='Action to perform'
    )
    parser.add_argument('--portfolio-id', help='Portfolio ID (for update-portfolio)')
    parser.add_argument('--ticker', help='Stock ticker (for fetch-history)')
    parser.add_argument('--days', type=int, default=100, help='Number of days (for fetch-history)')

    args = parser.parse_args()

    fetcher = PriceFetcher()

    try:
        if args.action == 'update-all':
            fetcher.run_daily_update()

        elif args.action == 'update-portfolio':
            if not args.portfolio_id:
                print("Error: --portfolio-id required")
                exit(1)
            fetcher.update_portfolio_prices(args.portfolio_id)

        elif args.action == 'fetch-history':
            if not args.ticker:
                print("Error: --ticker required")
                exit(1)
            fetcher.fetch_historical_data(args.ticker, args.days)

        elif args.action == 'calculate-metrics':
            if not args.portfolio_id:
                print("Error: --portfolio-id required")
                exit(1)
            fetcher.calculate_metrics(args.portfolio_id)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        exit(1)
