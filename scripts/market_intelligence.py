#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Market Intelligence - Multi-Source Data Aggregation
Sources:
- Sahmk.sa API
- Argaam.com
- TradingView
- Mubasher.info
- Google Finance
"""

import json
import os
import sys
import requests
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

class MarketIntelligence:
    def __init__(self):
        self.api_key = os.environ.get('API_KEY', '')
        self.api_url = os.environ.get('API_URL', 'https://www.sahmk.sa/api/v1')
        self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Session for requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Top Saudi stocks to monitor
        self.monitored_stocks = [
            '2222', '1120', '2010', '2050', '1180', '2380', '2030', '1211',
            '2350', '4030', '1150', '2020', '2090', '1050', '4001', '2280'
        ]
    
    def fetch_from_sahmk(self, endpoint, params=None):
        """Fetch from Sahmk API"""
        try:
            url = f"{self.api_url}/{endpoint}"
            headers = {'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
            
            response = self.session.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️ Sahmk API error: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️ Sahmk API exception: {e}")
            return None
    
    def fetch_from_argaam(self, symbol=None):
        """
        Fetch data from Argaam.com
        Returns: Market news, stock data, analyst recommendations
        """
        print("📰 Fetching from Argaam...")
        
        data = {
            'news': [],
            'stock_data': {},
            'analyst_ratings': {}
        }
        
        try:
            # Fetch market news
            news_url = "https://www.argaam.com/ar/news/newslist/1"
            response = self.session.get(news_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                news_items = soup.find_all('div', class_='news-item')[:10]
                
                for item in news_items:
                    title_elem = item.find('a')
                    if title_elem:
                        data['news'].append({
                            'title': title_elem.get_text(strip=True),
                            'url': title_elem.get('href'),
                            'timestamp': datetime.now().isoformat()
                        })
            
            # Fetch specific stock data if symbol provided
            if symbol:
                stock_url = f"https://www.argaam.com/ar/article/articledetail/id/{symbol}"
                # This is a placeholder - actual implementation depends on Argaam structure
                
        except Exception as e:
            print(f"⚠️ Argaam error: {e}")
        
        return data
    
    def fetch_from_tradingview(self, symbol):
        """
        Fetch technical indicators from TradingView
        Uses public widget data
        """
        print(f"📊 Fetching TradingView data for {symbol}...")
        
        indicators = {
            'RSI': 50,
            'MACD': 0,
            'SMA_20': 0,
            'SMA_50': 0,
            'recommendation': 'NEUTRAL'
        }
        
        try:
            # TradingView doesn't have public API, but we can use their widget
            # For production, consider using their paid API
            url = f"https://scanner.tradingview.com/global/scan"
            params = {
                'symbols': f'TADAWUL:{symbol}',
                'columns': 'RSI|MACD.macd|Recommend.Other',
            }
            
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                tv_data = response.json()
                # Parse the response
                if tv_data and 'data' in tv_data:
                    for item in tv_data['data']:
                        indicators['RSI'] = item.get('RSI', 50)
                        indicators['MACD'] = item.get('MACD.macd', 0)
                        indicators['recommendation'] = item.get('Recommend.Other', 'NEUTRAL')
                        
        except Exception as e:
            print(f"⚠️ TradingView error: {e}")
        
        return indicators
    
    def fetch_from_mubasher(self, symbol):
        """
        Fetch data from Mubasher.info
        """
        print(f"📈 Fetching from Mubasher for {symbol}...")
        
        data = {
            'price': 0,
            'change': 0,
            'change_percent': 0,
            'volume': 0,
            'market_cap': 0
        }
        
        try:
            url = f"https://www.mubasher.info/markets/TADAWUL/stocks/{symbol}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract price data (selectors may need adjustment)
                price_elem = soup.find('span', class_='price')
                if price_elem:
                    try:
                        data['price'] = float(price_elem.get_text().replace(',', ''))
                    except:
                        pass
                        
        except Exception as e:
            print(f"⚠️ Mubasher error: {e}")
        
        return data
    
    def analyze_news_sentiment(self, news_list):
        """
        Analyze sentiment of news articles
        Returns: sentiment score (-1 to +1)
        """
        if not news_list:
            return 0
        
        positive_keywords = [
            'نمو', 'أرباح', 'عقد', 'مشروع', 'توسع', 'إيجابي', 'ربح',
            'زيادة', 'ارتفاع', 'نجاح', 'إنجاز', 'تفوق', 'مكسب', 'صفقة'
        ]
        
        negative_keywords = [
            'خسارة', 'انخفاض', 'سلبي', 'تراجع', 'خسائر', 'هبوط',
            'تدهور', 'مشكلة', 'أزمة', 'انكماش', 'ديون'
        ]
        
        score = 0
        total = len(news_list)
        
        for news in news_list:
            text = news.get('title', '').lower()
            
            for keyword in positive_keywords:
                if keyword in text:
                    score += 1
                    break
            
            for keyword in negative_keywords:
                if keyword in text:
                    score -= 1
                    break
        
        # Normalize to -1 to +1
        return score / total if total > 0 else 0
    
    def aggregate_stock_data(self, symbol):
        """
        Aggregate data from all sources for a single stock
        """
        print(f"\n🔍 Analyzing {symbol}...")
        
        aggregated = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'sources': {}
        }
        
        # 1. Fetch from Sahmk API
        sahmk_data = self.fetch_from_sahmk(f'stocks/{symbol}/')
        if sahmk_data:
            aggregated['sources']['sahmk'] = sahmk_data
            aggregated.update(sahmk_data)
        
        # 2. Fetch from TradingView
        tv_data = self.fetch_from_tradingview(symbol)
        if tv_data:
            aggregated['sources']['tradingview'] = tv_data
            # Merge indicators
            for key, value in tv_data.items():
                if key not in ['sources', 'symbol', 'timestamp']:
                    aggregated[key] = value
        
        # 3. Fetch from Mubasher
        mubasher_data = self.fetch_from_mubasher(symbol)
        if mubasher_data and mubasher_data['price'] > 0:
            aggregated['sources']['mubasher'] = mubasher_data
            # Use Mubasher price if available
            if not aggregated.get('current_price'):
                aggregated['current_price'] = mubasher_data['price']
        
        # 4. Fetch news sentiment
        argaam_data = self.fetch_from_argaam(symbol)
        if argaam_data['news']:
            sentiment = self.analyze_news_sentiment(argaam_data['news'])
            aggregated['news_sentiment'] = sentiment
            aggregated['news_count'] = len(argaam_data['news'])
        
        return aggregated
    
    def fetch_market_overview(self):
        """
        Fetch overall market data
        """
        print("📊 Fetching market overview...")
        
        overview = {
            'tasi_index': 0,
            'tasi_change': 0,
            'market_volume': 0,
            'advancing': 0,
            'declining': 0,
            'unchanged': 0
        }
        
        try:
            # Fetch from Sahmk
            data = self.fetch_from_sahmk('market/overview/')
            if data:
                overview.update(data)
            
            # Alternative: Fetch from Argaam
            if not overview['tasi_index']:
                response = self.session.get('https://www.argaam.com/ar/market', timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # Extract TASI index (selectors may need adjustment)
                    tasi_elem = soup.find('div', class_='tasi-value')
                    if tasi_elem:
                        try:
                            overview['tasi_index'] = float(tasi_elem.get_text().replace(',', ''))
                        except:
                            pass
                            
        except Exception as e:
            print(f"⚠️ Market overview error: {e}")
        
        return overview
    
    def save_intelligence(self, data):
        """Save intelligence data"""
        output_file = self.data_dir / "market_intel.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Saved intelligence to {output_file}")
    
    def run_full_analysis(self):
        """
        Run complete market analysis
        """
        print("=" * 60)
        print("🧠 راصد - التحليل المتقدم للسوق")
        print("=" * 60)
        
        intelligence = {
            'timestamp': datetime.now().isoformat(),
            'market_overview': {},
            'stocks': [],
            'news': [],
            'summary': {}
        }
        
        # 1. Market Overview
        intelligence['market_overview'] = self.fetch_market_overview()
        
        # 2. Analyze monitored stocks
        for symbol in self.monitored_stocks:
            stock_data = self.aggregate_stock_data(symbol)
            intelligence['stocks'].append(stock_data)
            
            # Rate limiting - be respectful to servers
            time.sleep(1)
        
        # 3. Fetch market news
        argaam_data = self.fetch_from_argaam()
        intelligence['news'] = argaam_data.get('news', [])
        
        # 4. Generate summary
        intelligence['summary'] = {
            'total_stocks_analyzed': len(intelligence['stocks']),
            'positive_sentiment': sum(1 for s in intelligence['stocks'] if s.get('news_sentiment', 0) > 0),
            'negative_sentiment': sum(1 for s in intelligence['stocks'] if s.get('news_sentiment', 0) < 0),
            'avg_rsi': sum(s.get('RSI', 50) for s in intelligence['stocks']) / len(intelligence['stocks']) if intelligence['stocks'] else 50
        }
        
        # 5. Save
        self.save_intelligence(intelligence)
        
        # 6. Convert to daily.json format for compatibility
        self.convert_to_daily_format(intelligence)
        
        print(f"\n✅ Analysis complete: {intelligence['summary']}")
        return intelligence
    
    def convert_to_daily_format(self, intelligence):
        """Convert intelligence data to daily.json format"""
        daily_data = {
            'stocks': [],
            'timestamp': intelligence['timestamp'],
            'market_overview': intelligence['market_overview']
        }
        
        for stock in intelligence['stocks']:
            if stock.get('current_price'):
                daily_stock = {
                    'symbol': stock.get('symbol', ''),
                    'name': stock.get('name', ''),
                    'sector': stock.get('sector', ''),
                    'current_price': stock.get('current_price', 0),
                    'change_percent': stock.get('change_percent', 0),
                    'rsi': stock.get('RSI', 50),
                    'volume_ratio': stock.get('volume_ratio', 1.0),
                    'rs_rank': stock.get('rs_rank', 50),
                    'news_sentiment': stock.get('news_sentiment', 0),
                    'macd': stock.get('MACD', 0),
                    'recommendation': stock.get('recommendation', 'NEUTRAL')
                }
                daily_data['stocks'].append(daily_stock)
        
        # Save as daily.json
        daily_file = self.data_dir / "daily.json"
        with open(daily_file, 'w', encoding='utf-8') as f:
            json.dump(daily_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Converted to daily.json: {len(daily_data['stocks'])} stocks")

def main():
    intel = MarketIntelligence()
    
    try:
        intelligence = intel.run_full_analysis()
        
        if intelligence['stocks']:
            print(f"\n✅ Successfully analyzed {len(intelligence['stocks'])} stocks")
            sys.exit(0)
        else:
            print("\n⚠️ No data collected")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

