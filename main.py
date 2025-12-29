from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
from datetime import datetime
import pandas as pd
from typing import Dict, List
import logging
import os

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FinTech Monitor API",
    version="1.0.0",
    description="金融市場監控 API"
)

# 配置 CORS - 允許所有來源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 數據代號配置
TICKERS = {
    "us10y": "^TNX",
    "jpy_fx": "JPY=X",
    "gold": "GC=F",
    "oil": "CL=F"
}

def fetch_ticker_data(ticker: str, period: str = "5d") -> pd.DataFrame:
    """抓取 ticker 數據"""
    try:
        logger.info(f"Fetching {ticker} data for period {period}")
        data = yf.Ticker(ticker)
        hist = data.history(period=period)
        
        if hist.empty:
            logger.warning(f"No data returned for {ticker}")
            raise ValueError(f"No data for {ticker}")
        
        logger.info(f"Successfully fetched {len(hist)} records for {ticker}")
        return hist
    except Exception as e:
        logger.error(f"Error fetching {ticker}: {str(e)}")
        raise

@app.get("/")
async def root():
    """根路徑 - API 資訊"""
    return {
        "message": "FinTech Monitor API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "root": "/",
            "health": "/health",
            "bond_spread": "/api/bond-spread",
            "fx": "/api/fx",
            "commodities": "/api/commodities",
            "all": "/api/all"
        }
    }

@app.get("/health")
async def health_check():
    """健康檢查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/bond-spread")
async def get_bond_spread(period: str = "5d"):
    """獲取美日利差數據"""
    try:
        logger.info(f"API /api/bond-spread called with period={period}")
        
        # 抓取美債數據
        us_data = fetch_ticker_data(TICKERS["us10y"], period)
        
        # 日債使用固定值（yfinance 沒有準確的日債數據）
        jp_yield = 1.0
        
        spread_data = []
        for date, row in us_data.iterrows():
            us_yield = float(row['Close'])
            spread_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "us10y": round(us_yield, 4),
                "jp10y": round(jp_yield, 4),
                "spread": round(us_yield - jp_yield, 4)
            })
        
        logger.info(f"Successfully calculated {len(spread_data)} spread records")
        
        return {
            "success": True,
            "data": sorted(spread_data, key=lambda x: x['date']),
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
    """獲取美日匯率數據"""
    try:
        logger.info(f"API /api/fx called with period={period}")
        
        hist = fetch_ticker_data(TICKERS["jpy_fx"], period)
        
        fx_data = []
        for date, row in hist.iterrows():
            fx_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "rate": round(float(row['Close']), 4),
                "high": round(float(row['High']), 4),
                "low": round(float(row['Low']), 4)
            })
        
        logger.info(f"Successfully fetched {len(fx_data)} FX records")
        
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
    """獲取大宗商品數據"""
    try:
        logger.info(f"API /api/commodities called with period={period}")
        
        commodities = {}
        
        # 黃金
        try:
            gold_hist = fetch_ticker_data(TICKERS["gold"], period)
            gold_data = []
            for date, row in gold_hist.iterrows():
                gold_data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "price": round(float(row['Close']), 2),
                    "change": round(float(row['Close'] - row['Open']), 2)
                })
            commodities["gold"] = sorted(gold_data, key=lambda x: x['date'])
            logger.info(f"Successfully fetched {len(gold_data)} gold records")
        except Exception as e:
            logger.error(f"Gold data error: {str(e)}")
            commodities["gold"] = []
        
        # 原油
        try:
            oil_hist = fetch_ticker_data(TICKERS["oil"], period)
            oil_data = []
            for date, row in oil_hist.iterrows():
                oil_data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "price": round(float(row['Close']), 2),
                    "change": round(float(row['Close'] - row['Open']), 2)
                })
            commodities["oil"] = sorted(oil_data, key=lambda x: x['date'])
            logger.info(f"Successfully fetched {len(oil_data)} oil records")
        except Exception as e:
            logger.error(f"Oil data error: {str(e)}")
            commodities["oil"] = []
        
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
    """一次性獲取所有數據"""
    try:
        logger.info(f"API /api/all called with period={period}")
        
        # 分別獲取各項數據
        bond_spread_result = await get_bond_spread(period)
        fx_result = await get_fx_rate(period)
        commodities_result = await get_commodities(period)
        
        return {
            "success": True,
            "data": {
                "bondSpread": bond_spread_result["data"],
                "fx": fx_result["data"],
                "commodities": commodities_result["data"]
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
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
