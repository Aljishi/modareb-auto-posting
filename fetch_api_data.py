#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch market data from sahmk.sa API
"""

import json
import os
import sys
import requests
from datetime import datetime
from pathlib import Path

class MarketDataFetcher:
    def __init__(self):
        self.api_key = os.environ.get('API_KEY', '')
        self.api_url = os.environ.get('API_URL', 'https://www.sahmk.sa/api/v1')
        self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Emergency fallback stocks (Top Saudi stocks)
        self.emergency_stocks = [
            {'symbol': '2222', 'name': 'أرامكو السعودية', 'sector': 'الطاقة', 'current_price': 30.50, 'change_percent': 1.2, 'rsi': 55, 'volume_ratio': 1.8, 'rs_rank': 75},
            {'symbol': '1120', 'name': 'الراجحي', 'sector': 'المصارف', 'current_price': 85.20, 'change_percent': 0.8, 'rsi': 58, 'volume_ratio': 1.5, 'rs_rank': 70},
            {'symbol': '2010', 'name': 'سابك', 'sector': 'الصناعات', 'current_price': 95.40, 'change_percent': -0.5, 'rsi': 48, 'volume_ratio': 1.2, 'rs_rank': 60},
            {'symbol': '2050', 'name': 'صافولا', 'sector': 'الطاقة', 'current_price': 26.92, 'change_percent': 2.1, 'rsi': 62, 'volume_ratio': 2.1, 'rs_rank': 82},
            {'symbol': '1180', 'name': 'الأهلي', 'sector': 'المصارف', 'current_price': 42.15, 'change_percent': 1.5, 'rsi': 60, 'volume_ratio': 1.7, 'rs_rank': 72},
        ]
    
    def fetch_from_api(self, endpoint, params=None):
        """Fetch data from API with proper authentication"""
        url = f"{self.api_url}/{endpoint}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
            if params is None:
                params = {}
            params['apikey'] = self.api_key
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                print(f"⚠️ HTTP 401: Unauthorized - Check API Key")
                return None
            elif response.status_code == 404:
                print(f"⚠️ HTTP 404: Endpoint not found - {endpoint}")
                return None
            else:
                print(f"⚠️ HTTP {response.status_code}: {endpoint}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Request failed: {e}")
            return None
    
    def fetch_gainers(self):
        """Fetch top gainers"""
        print("📈 Fetching top gainers...")
        data = self.fetch_from_api('market/gainers/', {'limit': 20})
        return data if data else []
    
    def fetch_volume(self):
        """Fetch high volume stocks"""
        print("📊 Fetching high volume stocks...")
        data = self.fetch_from_api('market/volume/', {'limit': 20})
        return data if data else []
    
    def fetch_active(self):
        """Fetch most active stocks"""
        print("🔥 Fetching most active stocks...")
        data = self.fetch_from_api('market/active/', {'limit': 20})
        return data if data else []
    
    def fetch_stock_details(self, symbol):
        """Fetch detailed data for a specific stock"""
        print(f"🔍 Fetching details for {symbol}...")
        data = self.fetch_from_api(f'stocks/{symbol}/')
        return data
    
    def process_stock_data(self, stock):
        """Process and normalize stock data"""
        try:
            return {
                'symbol': stock.get('symbol', stock.get('ticker', '')),
                'name': stock.get('name', stock.get('company_name', '')),
                'sector': stock.get('sector', stock.get('sector_name', 'غير محدد')),
                'current_price': float(stock.get('price', stock.get('current_price', stock.get('last_price', 0)))),
                'change_percent': float(stock.get('change_percent', stock.get('change_percentage', stock.get('percent_change', 0)))),
                'change': float(stock.get('change', stock.get('price_change', 0))),
                'volume': int(stock.get('volume', stock.get('traded_volume', 0))),
                'value': float(stock.get('value', stock.get('traded_value', 0))),
                'high': float(stock.get('high', stock.get('high_price', 0))),
                'low': float(stock.get('low', stock.get('low_price', 0))),
                'open': float(stock.get('open', stock.get('open_price', 0))),
                'previous_close': float(stock.get('previous_close', stock.get('prev_close', 0))),
                'rsi': float(stock.get('rsi', stock.get('RSI', 50))),
                'volume_ratio': float(stock.get('volume_ratio', stock.get('volumeRatio', 1.0))),
                'rs_rank': float(stock.get('rs_rank', stock.get('rsRank', stock.get('RS_Rank', 50)))),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"⚠️ Error processing stock data: {e}")
            return None
    
    def fetch_all_data(self):
        """Fetch all market data"""
        print("=" * 60)
        print("📡 راصد - جلب بيانات السوق")
        print("=" * 60)
        
        all_stocks = []
        seen_symbols = set()
        
        # Try fetching from different endpoints
        endpoints = [
            ('gainers', self.fetch_gainers()),
            ('volume', self.fetch_volume()),
            ('active', self.fetch_active()),
        ]
        
        for endpoint_name, data in endpoints:
            if data:
                print(f"✅ {endpoint_name}: {len(data)} stocks")
                for stock in data:
                    processed = self.process_stock_data(stock)
                    if processed and processed['symbol'] not in seen_symbols:
                        all_stocks.append(processed)
                        seen_symbols.add(processed['symbol'])
            else:
                print(f"❌ {endpoint_name}: Failed")
        
        return all_stocks
    
    def save_data(self, stocks):
        """Save data to JSON file"""
        output_file = self.data_dir / "daily.json"
        
        data = {
            'stocks': stocks,
            'total_stocks': len(stocks),
            'timestamp': datetime.now().isoformat(),
            'timezone': 'Asia/Riyadh',
            'market_status': 'open'
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Saved {len(stocks)} stocks to {output_file}")
        return output_file
    
    def use_emergency_fallback(self):
        """Use emergency fallback stocks when API fails"""
        print("\n⚠️ Using emergency fallback stocks...")
        
        stocks = []
        for stock in self.emergency_stocks:
            processed = self.process_stock_data(stock)
            if processed:
                stocks.append(processed)
                print(f"  📌 {stock['symbol']} - {stock['name']}")
        
        if stocks:
            self.save_data(stocks)
            return stocks
        
        return []

def main():
    fetcher = MarketDataFetcher()
    
    # Try to fetch from API
    stocks = fetcher.fetch_all_data()
    
    # Check if we got enough data
    if len(stocks) >= 5:
        fetcher.save_data(stocks)
        print(f"\n✅ Successfully fetched {len(stocks)} stocks")
        sys.exit(0)
    else:
        print(f"\n⚠️ Only {len(stocks)} stocks fetched, using fallback...")
        stocks = fetcher.use_emergency_fallback()
        
        if stocks:
            print(f"✅ Fallback successful: {len(stocks)} stocks")
            sys.exit(0)
        else:
            print("❌ Failed to fetch any data")
            sys.exit(1)

if __name__ == "__main__":
    main()

