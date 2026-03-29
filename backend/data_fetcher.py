import pandas as pd
import yfinance as yf
import time
import logging

try:
    from config import SCAN_ALL_SP500, TEST_SUBSET_SIZE
except ImportError:
    # Fallback for direct execution
    SCAN_ALL_SP500 = False
    TEST_SUBSET_SIZE = 5

logger = logging.getLogger("asymptote-lt.data_fetcher")

def get_sp500_tickers() -> list[str]:
    """Scrapes the current S&P 500 tickers from Wikipedia."""
    import requests
    from io import StringIO
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).text
        tables = pd.read_html(StringIO(html))
        df = tables[0]
        # Ticker column is usually 'Symbol'
        tickers = df["Symbol"].tolist()
        # Some yahoo tickers use '-' instead of '.' (like BRK.B -> BRK-B)
        tickers = [ticker.replace('.', '-') for ticker in tickers]
        
        if not SCAN_ALL_SP500:
            logger.info(f"Test mode: Using only {TEST_SUBSET_SIZE} tickers for testing.")
            return tickers[:TEST_SUBSET_SIZE]
            
        return tickers
    except Exception as e:
        logger.error(f"Failed to scrape S&P 500 list: {e}")
        # Fallback to a hardcoded critical list if scrape fails
        return ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B", "UNH", "XOM"]

def fetch_data(ticker: str, period="2y", interval="1d") -> pd.DataFrame | None:
    """Fetches historical EOD data for a given ticker and timeframe."""
    try:
        # Avoid overwhelming yfinance occasionally
        time.sleep(0.1)
        data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, prepost=False, progress=False)
        
        if data.empty:
            logger.warning(f"No data returned for {ticker} at {interval}")
            return None
            
        # Standardize columns to lowercase, remove MultiIndex if present from yf.download in newer versions
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0].lower() for col in data.columns]
        else:
            data.columns = [col.lower() for col in data.columns]
            
        # Reset index to make 'Date' or 'Datetime' a column
        data.reset_index(inplace=True)
        # Rename date column consistently to 'datetime'
        date_col = [col for col in data.columns if "date" in col.lower() or "time" in col.lower()][0]
        data.rename(columns={date_col: "datetime"}, inplace=True)
        
        # Ensure we have the standard columns
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in data.columns:
                logger.error(f"Missing column '{col}' for {ticker}")
                return None
                
        # Drop rows with NaN values in crucial columns
        data.dropna(subset=["close"], inplace=True)
        
        return data

    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        return None

def fetch_bulk_data(tickers: list[str], period="2y", interval="1d") -> dict[str, pd.DataFrame]:
    """
    Fetches historical OHLCV data for multiple tickers in a single bulk request.
    Returns a dictionary mapping ticker -> standardized DataFrame.
    """
    if not tickers:
        return {}
        
    logger.info(f"Bulk downloading {len(tickers)} tickers for interval {interval}...")
    try:
        # yf.download returns a MultiIndex DataFrame if more than one ticker
        # We use group_by='ticker' to get [Ticker][OHLCV] structure
        data = yf.download(
            tickers, 
            period=period, 
            interval=interval, 
            group_by='ticker', 
            auto_adjust=True, 
            prepost=False, 
            progress=True
        )
        
        results = {}
        for ticker in tickers:
            try:
                # Handle potential missing ticker in result
                if ticker not in data.columns.levels[0]:
                    continue
                
                ticker_df = data[ticker].copy()
                if ticker_df.empty or ticker_df.isnull().all().all():
                    continue
                
                # Standardize columns
                ticker_df.columns = [col.lower() for col in ticker_df.columns]
                ticker_df.reset_index(inplace=True)
                
                # Standardize date column
                date_col = [col for col in ticker_df.columns if "date" in col.lower() or "time" in col.lower()][0]
                ticker_df.rename(columns={date_col: "datetime"}, inplace=True)
                
                # Final cleanup
                ticker_df.dropna(subset=["close"], inplace=True)
                if not ticker_df.empty:
                    results[ticker] = ticker_df
                    
            except Exception as ticker_err:
                logger.debug(f"Error extracting {ticker} from bulk data: {ticker_err}")
                continue
                
        logger.info(f"Bulk download complete. Successfully retrieved {len(results)}/{len(tickers)} tickers.")
        return results

    except Exception as e:
        logger.error(f"Bulk fetch failed: {e}")
        return {}
