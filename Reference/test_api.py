"""Quick API key validation test."""
import sys
sys.path.insert(0, ".")
import asyncio
import aiohttp
import config

async def test_api():
    async with aiohttp.ClientSession() as session:
        url = f"{config.TWELVEDATA_BASE_URL}/time_series"
        params = {
            "symbol": "AAPL",
            "interval": "15min",
            "outputsize": "2",
            "apikey": config.TWELVEDATA_API_KEY,
        }
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            if data.get("status") == "error":
                print(f"[FAIL] API error: {data.get('message')}")
            elif data.get("values"):
                print(f"[OK] API key works! Got {len(data['values'])} candles for AAPL")
                print(f"  Latest candle: {data['values'][0]}")
            else:
                print(f"[WARN] Unexpected response: {data}")

asyncio.run(test_api())
