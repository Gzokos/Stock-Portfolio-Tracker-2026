

import os
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import time


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


BASE_URL = "https://www.alphavantage.co/query"
DEFAULT_TIMEOUT = 10
API_KEY = os.getenv('ALPHAVANTAGE_API_KEY')


REQUEST_DELAY = 0.2  


class TimeInterval(Enum):
    ONE_MIN = "1min"
    FIVE_MIN = "5min"
    FIFTEEN_MIN = "15min"
    THIRTY_MIN = "30min"
    SIXTY_MIN = "60min"


@dataclass
class StockPrice:
    
    ticker: str
    price: float
    timestamp: datetime
    volume: int = None
    bid: float = None
    ask: float = None
    change: float = None
    change_percent: float = None


@dataclass
class DailyPrice:
   
    date: str
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: int


class AlphaVantageClient:


    def __init__(self, api_key: str = None, timeout: int = DEFAULT_TIMEOUT):
     
        self.api_key = api_key or API_KEY
        self.timeout = timeout
        self.last_request_time = 0

        if not self.api_key:
            raise ValueError(
                "API key not found. Please set ALPHAVANTAGE_API_KEY environment variable"
            )

    def _rate_limit(self):
        
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self.last_request_time = time.time()

    def _request(self, params: Dict) -> Dict:
       
        self._rate_limit()

        params['apikey'] = self.api_key
        
        try:
            response = requests.get(
                BASE_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if 'Error Message' in data:
                raise ValueError(f"Alpha Vantage API Error: {data['Error Message']}")
            
            if 'Note' in data:
                logger.warning(f"API Rate Limit: {data['Note']}")
                raise ValueError("Rate limit reached. Please wait before retrying.")
            
            return data
            
        except requests.exceptions.Timeout:
            raise requests.exceptions.RequestException("API request timeout")
        except requests.exceptions.ConnectionError as e:
            raise requests.exceptions.RequestException(f"Connection error: {e}")

    def get_current_price(self, ticker: str) -> StockPrice:
        
        logger.info(f"Fetching current price for {ticker}")
        
        params = {
            'function': 'GLOBAL_QUOTE',
            'symbol': ticker.upper()
        }
        
        data = self._request(params)
        quote = data.get('Global Quote', {})
        
        if not quote or quote.get('01. symbol') is None:
            raise ValueError(f"No data found for ticker {ticker}")
        
        return StockPrice(
            ticker=quote.get('01. symbol'),
            price=float(quote.get('05. price', 0)),
            timestamp=datetime.now(),
            volume=int(quote.get('06. volume', 0)),
            change=float(quote.get('09. change', 0)),
            change_percent=float(quote.get('10. change percent', '0%').replace('%', ''))
        )

    def get_daily_prices(
        self,
        ticker: str,
        output_size: str = 'compact'
    ) -> List[DailyPrice]:
       
        logger.info(f"Fetching daily prices for {ticker}")
        
        params = {
            'function': 'TIME_SERIES_DAILY_ADJUSTED',
            'symbol': ticker.upper(),
            'outputsize': output_size
        }
        
        data = self._request(params)
        time_series = data.get('Time Series (Daily)', {})
        
        if not time_series:
            raise ValueError(f"No data found for ticker {ticker}")
        
        prices = []
        for date_str, daily_data in time_series.items():
            prices.append(DailyPrice(
                date=date_str,
                open=float(daily_data.get('1. open', 0)),
                high=float(daily_data.get('2. high', 0)),
                low=float(daily_data.get('3. low', 0)),
                close=float(daily_data.get('4. close', 0)),
                adjusted_close=float(daily_data.get('5. adjusted close', 0)),
                volume=int(daily_data.get('6. volume', 0))
            ))
        
        # Sort by date (oldest first)
        prices.sort(key=lambda x: x.date)
        return prices

    def get_intraday_prices(
        self,
        ticker: str,
        interval: TimeInterval = TimeInterval.FIVE_MIN,
        output_size: str = 'compact'
    ) -> List[DailyPrice]:
       
        logger.info(f"Fetching intraday prices for {ticker} at {interval.value}")
        
        params = {
            'function': 'TIME_SERIES_INTRADAY',
            'symbol': ticker.upper(),
            'interval': interval.value,
            'outputsize': output_size
        }
        
        data = self._request(params)
        time_series_key = f'Time Series ({interval.value})'
        time_series = data.get(time_series_key, {})
        
        if not time_series:
            raise ValueError(f"No intraday data found for {ticker}")
        
        prices = []
        for timestamp_str, intraday_data in time_series.items():
            prices.append(DailyPrice(
                date=timestamp_str,
                open=float(intraday_data.get('1. open', 0)),
                high=float(intraday_data.get('2. high', 0)),
                low=float(intraday_data.get('3. low', 0)),
                close=float(intraday_data.get('4. close', 0)),
                adjusted_close=float(intraday_data.get('4. close', 0)),
                volume=int(intraday_data.get('5. volume', 0))
            ))
        
        # Sort by date (oldest first)
        prices.sort(key=lambda x: x.date)
        return prices

    def get_symbol_search(self, keyword: str) -> List[Dict]:
       
        logger.info(f"Searching for symbols matching '{keyword}'")
        
        params = {
            'function': 'SYMBOL_SEARCH',
            'keywords': keyword
        }
        
        data = self._request(params)
        matches = data.get('bestMatches', [])
        
        return [
            {
                'symbol': match.get('1. symbol'),
                'name': match.get('2. name'),
                'type': match.get('3. type'),
                'region': match.get('4. region'),
                'market_open': match.get('5. marketOpen'),
                'market_close': match.get('6. marketClose'),
                'timezone': match.get('7. timezone'),
                'currency': match.get('8. currency'),
                'match_score': float(match.get('9. matchScore', 0))
            }
            for match in matches
        ]

    def batch_fetch_prices(
        self,
        tickers: List[str],
        max_retries: int = 3
    ) -> Dict[str, Optional[StockPrice]]:
      
        logger.info(f"Batch fetching prices for {len(tickers)} tickers")
        
        results = {}
        failed_tickers = []
        
        for ticker in tickers:
            try:
                results[ticker.upper()] = self.get_current_price(ticker)
            except Exception as e:
                logger.error(f"Failed to fetch {ticker}: {e}")
                failed_tickers.append(ticker)
                results[ticker.upper()] = None
        
        # Retry failed requests once
        for ticker in failed_tickers[:max_retries]:
            logger.info(f"Retrying {ticker}")
            try:
                results[ticker.upper()] = self.get_current_price(ticker)
            except Exception as e:
                logger.error(f"Retry failed for {ticker}: {e}")
        
        return results

    def get_company_info(self, ticker: str) -> Dict:
       
        logger.info(f"Fetching company info for {ticker}")
        
        params = {
            'function': 'OVERVIEW',
            'symbol': ticker.upper()
        }
        
        return self._request(params)



def main():
   
    
    try:
        client = AlphaVantageClient()
        
        # Example 1: Get current price
        print("=" * 60)
        print("Example 1: Current Price")
        print("=" * 60)
        price = client.get_current_price('AAPL')
        print(f"Ticker: {price.ticker}")
        print(f"Current Price: ${price.price}")
        print(f"Change: {price.change} ({price.change_percent}%)")
        print(f"Volume: {price.volume:,}")
        print(f"Timestamp: {price.timestamp}")
        
        # Example 2: Get daily prices
        print("\n" + "=" * 60)
        print("Example 2: Daily Prices (Last 5 days)")
        print("=" * 60)
        daily_prices = client.get_daily_prices('AAPL', 'compact')
        for price in daily_prices[-5:]:
            print(f"{price.date}: Open ${price.open:.2f}, Close ${price.close:.2f}, Volume {price.volume:,}")
        
        # Example 3: Search for symbols
        print("\n" + "=" * 60)
        print("Example 3: Symbol Search")
        print("=" * 60)
        results = client.get_symbol_search('Tesla')
        for result in results[:3]:
            print(f"{result['symbol']}: {result['name']} ({result['region']})")
        
        # Example 4: Batch fetch prices
        print("\n" + "=" * 60)
        print("Example 4: Batch Fetch Prices")
        print("=" * 60)
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
        prices = client.batch_fetch_prices(tickers)
        for ticker, price_data in prices.items():
            if price_data:
                print(f"{ticker}: ${price_data.price} ({price_data.change_percent:+.2f}%)")
            else:
                print(f"{ticker}: FAILED")
        
    except ValueError as e:
        logger.error(f"Configuration Error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
