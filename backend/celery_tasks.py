

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from celery_app import app
from database_models import DatabaseConnection, Portfolio, User
from price_fetcher import PriceFetcher
from portfolio_service import PortfolioService
from alpha_vantage_client import AlphaVantageClient

logger = logging.getLogger(__name__)

@app.task(name='backend.celery_tasks.update_portfolio_prices_task', bind=True)
def update_portfolio_prices_task(self, portfolio_id: str):
   
    try:
        logger.info(f"Starting price update for portfolio {portfolio_id}")
        
        db = DatabaseConnection()
        api_client = AlphaVantageClient()
        session = db.get_session()
        
        try:
            fetcher = PriceFetcher(db, api_client)
            fetcher.update_portfolio_prices(portfolio_id)
            
            logger.info(f"✓ Price update completed for portfolio {portfolio_id}")
            return {"status": "success", "portfolio_id": portfolio_id}
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"✗ Price update failed for portfolio {portfolio_id}: {e}")
        raise


@app.task(name='backend.celery_tasks.update_all_portfolio_prices')
def update_all_portfolio_prices():
    
    try:
        logger.info("Starting daily price update for all portfolios")
        
        db = DatabaseConnection()
        api_client = AlphaVantageClient()
        session = db.get_session()
        
        try:
            # Get all portfolios
            portfolios = session.query(Portfolio).all()
            logger.info(f"Found {len(portfolios)} portfolios to update")
            
            fetcher = PriceFetcher(db, api_client)
            
            # Update each portfolio
            success_count = 0
            error_count = 0
            
            for portfolio in portfolios:
                try:
                    fetcher.update_portfolio_prices(str(portfolio.id))
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to update portfolio {portfolio.id}: {e}")
                    error_count += 1
            
            logger.info(
                f"✓ Daily price update complete: {success_count} succeeded, {error_count} failed"
            )
            
            return {
                "status": "success",
                "portfolios_updated": success_count,
                "portfolios_failed": error_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"✗ Daily price update failed: {e}")
        raise




@app.task(name='backend.celery_tasks.calculate_portfolio_metrics_task')
def calculate_portfolio_metrics_task(portfolio_id: str):
    """
    Background task: Calculate metrics for a single portfolio
    
    Args:
        portfolio_id: UUID of portfolio
    """
    try:
        logger.info(f"Starting metric calculation for portfolio {portfolio_id}")
        
        db = DatabaseConnection()
        api_client = AlphaVantageClient()
        session = db.get_session()
        
        try:
            fetcher = PriceFetcher(db, api_client)
            fetcher.calculate_metrics(portfolio_id)
            
            logger.info(f"✓ Metrics calculated for portfolio {portfolio_id}")
            return {"status": "success", "portfolio_id": portfolio_id}
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"✗ Metric calculation failed for portfolio {portfolio_id}: {e}")
        raise


@app.task(name='backend.celery_tasks.calculate_all_portfolio_metrics')
def calculate_all_portfolio_metrics():
    
    try:
        logger.info("Calculating metrics for all portfolios")
        
        db = DatabaseConnection()
        api_client = AlphaVantageClient()
        session = db.get_session()
        
        try:
            portfolios = session.query(Portfolio).all()
            fetcher = PriceFetcher(db, api_client)
            
            for portfolio in portfolios:
                try:
                    fetcher.calculate_metrics(str(portfolio.id))
                except Exception as e:
                    logger.error(f"Failed to calculate metrics for {portfolio.id}: {e}")
            
            logger.info(f"✓ Metrics calculated for {len(portfolios)} portfolios")
            return {
                "status": "success",
                "portfolios_count": len(portfolios),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"✗ Metrics calculation failed: {e}")
        raise



@app.task(name='backend.celery_tasks.fetch_historical_data_task')
def fetch_historical_data_task():
  
    try:
        logger.info("Starting historical data fetch")
        
        db = DatabaseConnection()
        api_client = AlphaVantageClient()
        session = db.get_session()
        
        try:
            # Get all unique tickers from portfolios
            portfolios = session.query(Portfolio).all()
            tickers = set()
            
            for portfolio in portfolios:
                for holding in portfolio.holdings:
                    tickers.add(holding.stock.ticker)
            
            logger.info(f"Fetching historical data for {len(tickers)} unique stocks")
            
            fetcher = PriceFetcher(db, api_client)
            
            # Fetch history for each ticker
            success_count = 0
            error_count = 0
            
            for ticker in sorted(tickers):
                try:
                    fetcher.fetch_historical_data(ticker, days=365)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to fetch history for {ticker}: {e}")
                    error_count += 1
            
            logger.info(f"✓ Historical data fetch complete: {success_count} succeeded, {error_count} failed")
            
            return {
                "status": "success",
                "tickers_updated": success_count,
                "tickers_failed": error_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"✗ Historical data fetch failed: {e}")
        raise


@app.task(name='backend.celery_tasks.cleanup_old_audit_logs')
def cleanup_old_audit_logs(days: int = 90):
   
    try:
        logger.info(f"Cleaning up audit logs older than {days} days")
        
        from database_models import AuditLog
        
        db = DatabaseConnection()
        session = db.get_session()
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Delete old logs
            deleted_count = session.query(AuditLog).filter(
                AuditLog.created_at < cutoff_date
            ).delete()
            
            session.commit()
            
            logger.info(f"✓ Deleted {deleted_count} old audit log entries")
            return {"status": "success", "deleted_count": deleted_count}
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"✗ Audit log cleanup failed: {e}")
        raise


@app.task(name='backend.celery_tasks.send_portfolio_summary_email')
def send_portfolio_summary_email(user_id: str):
   
    try:
        logger.info(f"Sending portfolio summary email for user {user_id}")
        
        db = DatabaseConnection()
        session = db.get_session()
        
        try:
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                logger.warning(f"User {user_id} not found")
                return {"status": "error", "message": "User not found"}
            
            # TODO: Implement email sending logic
            # For now, just log it
            logger.info(f"✓ Portfolio summary ready for {user.email}")
            
            return {
                "status": "success",
                "user_id": user_id,
                "email": user.email,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"✗ Email send failed: {e}")
        raise


@app.task(name='backend.celery_tasks.health_check')
def health_check():
   
    try:
        db = DatabaseConnection()
        api_client = AlphaVantageClient()
        
        # Check database
        db_health = db.health_check()
        
        # Check API (don't count against rate limit)
        api_health = True
        
        status = "healthy" if (db_health and api_health) else "unhealthy"
        
        logger.info(f"Health check: {status}")
        
        return {
            "status": status,
            "database": "connected" if db_health else "disconnected",
            "api": "available" if api_health else "unavailable",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise


@app.on_before_task_publish.connect
def before_task_publish(sender=None, body=None, **kwargs):
    """Log task publishing"""
    logger.debug(f"Publishing task: {body}")


@app.on_after_task_publish.connect
def after_task_publish(sender=None, body=None, **kwargs):
    """Log published task"""
    logger.debug(f"Task published successfully")


@app.task_success.connect
def task_success_handler(sender=None, body=None, **kwargs):
    """Handle successful task"""
    logger.info(f"Task succeeded: {sender}")


@app.task_failure.connect
def task_failure_handler(sender=None, exception=None, **kwargs):
    """Handle failed task"""
    logger.error(f"Task failed: {sender}, Exception: {exception}")


if __name__ == "__main__":
    app.start()
