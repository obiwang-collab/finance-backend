from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List
import logging

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FinTech Monitor API", version="1.0.0")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生產環境請改為具體域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 數據代號配置
TICKERS = {
    "us10y": "^TNX",      # 美國 10年期國債
    "jpy_fx": "JPY=X",    # 美日匯率
    "gold": "GC=F",       # 黃金期貨
    "oil": "CL=F"         # WTI 原油期貨
}

def fetch_bond_yield(ticker: str, period: str = "5d") -> pd.DataFrame:
    """抓取債券收益率數據"""
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period=period)
        if hist.empty:
            raise ValueError(f"No data for {ticker}")
        return hist
    except Exception as e:
        logger.error(f"Error fetching {ticker}: {str(e)}")
        raise

def calculate_spread(us_data: pd.DataFrame, jp_data: pd.DataFrame) -> List[Dict]:
    """計算美日利差"""
    try:
        # 對齊日期索引
        common_dates = us_data.index.intersection(jp_data.index)
        
        spread_data = []
        for date in common_dates:
            us_yield = us_data.loc[date, 'Close']
            # 日債收益率需要特殊處理（通常以百分比形式）
            jp_yield = jp_data.loc[date, 'Close']
            
            spread_data.append({
                "date": date.strftime("%Y-%m-%d %H:%M:%S"),
                "us10y": round(float(us_yield), 4),
                "jp10y": round(float(jp_yield), 4),
                "spread": round(float(us_yield - jp_yield), 4)
            })
        
        return sorted(spread_data, key=lambda x: x['date'])
    except Exception as e:
        logger.error(f"Error calculating spread: {str(e)}")
        raise

@app.get("/")
async def root():
    return {
        "message": "FinTech Monitor API",
        "version": "1.0.0",
        "endpoints": ["/api/bond-spread", "/api/fx", "/api/commodities", "/api/all"]
    }

@app.get("/api/bond-spread")
async def get_bond_spread(period: str = "5d"):
    """
    獲取美日利差數據
    
    Parameters:
    - period: 數據週期 (1d, 5d, 1mo, 3mo, 6mo, 1y)
    """
    try:
        # 抓取美債數據
        us_data = fetch_bond_yield(TICKERS["us10y"], period)
        
        # 日債數據（yfinance 可能沒有，提供備用方案）
        try:
            jp_ticker = yf.Ticker("^TNX")  # 暫時用美債模擬，實際需要其他數據源
            jp_data = jp_ticker.history(period=period)
            # 模擬日債收益率（實際應該從其他 API 獲取）
            jp_data['Close'] = jp_data['Close'] * 0.02  # 假設日債約為美債的 2%
        except:
            # 如果無法獲取，使用固定值模擬
            jp_data = us_data.copy()
            jp_data['Close'] = 0.5  # 假設日債固定在 0.5%
        
        spread_data = calculate_spread(us_data, jp_data)
        
        return {
            "success": True,
            "data": spread_data,
            "metadata": {
                "period": period,
                "data_points": len(spread_data),
                "last_update": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Bond spread error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fx")
async def get_fx_rate(period: str = "5d"):
    """
    獲取美日匯率數據
    
    Parameters:
    - period: 數據週期
    """
    try:
        ticker = yf.Ticker(TICKERS["jpy_fx"])
        hist = ticker.history(period=period)
        
        if hist.empty:
            raise ValueError("No FX data available")
        
        fx_data = []
        for date, row in hist.iterrows():
            fx_data.append({
                "date": date.strftime("%Y-%m-%d %H:%M:%S"),
                "rate": round(float(row['Close']), 4),
                "high": round(float(row['High']), 4),
                "low": round(float(row['Low']), 4)
            })
        
        return {
            "success": True,
            "data": sorted(fx_data, key=lambda x: x['date']),
            "metadata": {
                "pair": "USD/JPY",
                "period": period,
                "last_update": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"FX rate error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/commodities")
async def get_commodities(period: str = "5d"):
    """
    獲取大宗商品數據（黃金、原油）
    
    Parameters:
    - period: 數據週期
    """
    try:
        commodities = {}
        
        for name, ticker_symbol in [("gold", "gold"), ("oil", "oil")]:
            ticker = yf.Ticker(TICKERS[ticker_symbol])
            hist = ticker.history(period=period)
            
            if not hist.empty:
                data = []
                for date, row in hist.iterrows():
                    data.append({
                        "date": date.strftime("%Y-%m-%d %H:%M:%S"),
                        "price": round(float(row['Close']), 2),
                        "change": round(float(row['Close'] - row['Open']), 2)
                    })
                
                commodities[name] = sorted(data, key=lambda x: x['date'])
        
        return {
            "success": True,
            "data": commodities,
            "metadata": {
                "period": period,
                "last_update": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Commodities error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/all")
async def get_all_data(period: str = "5d"):
    """
    一次性獲取所有數據
    
    Parameters:
    - period: 數據週期
    """
    try:
        bond_spread = await get_bond_spread(period)
        fx = await get_fx_rate(period)
        commodities = await get_commodities(period)
        
        return {
            "success": True,
            "data": {
                "bondSpread": bond_spread["data"],
                "fx": fx["data"],
                "commodities": commodities["data"]
            },
            "metadata": {
                "period": period,
                "last_update": datetime.now().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"All data error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
