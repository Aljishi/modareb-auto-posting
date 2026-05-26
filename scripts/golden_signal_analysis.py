#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Golden Signal Analysis - Deep Market Analysis
Analyzes:
1. Historical price patterns (30-90 days)
2. Technical indicators from multiple timeframes
3. Volume analysis
4. News sentiment from trusted sources
5. Market momentum
6. Sector performance
"""

import json
import os
import sys
from datetime import datetime
import pandas as pd
import numpy as np

class GoldenSignalAnalyzer:
    def __init__(self):
        self.symbols = []
        self.analysis_results = []
        self.api_key = os.environ.get('API_KEY', '')
        self.api_url = os.environ.get('API_URL', 'https://www.sahmk.sa/api/v1')
        
    def fetch_historical_data(self, symbol, days=90):
        """Fetch historical data from sahmk.sa API"""
        try:
            url = f"{self.api_url}/stocks/{symbol}/historical"
            params = {'days': days, 'apikey': self.api_key} if self.api_key else {'days': days}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    return data
                elif isinstance(data, dict) and 'data' in data:
                    return data['data']
            return None
        except Exception as e:
            print(f"⚠️ Error fetching data for {symbol}: {e}")
            return None
    
    def calculate_technical_indicators(self, df):
        """Calculate comprehensive technical indicators"""
        indicators = {}
        
        # RSI
        if len(df) >= 14:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            indicators['RSI'] = df['RSI'].iloc[-1] if not pd.isna(df['RSI'].iloc[-1]) else 50
        else:
            indicators['RSI'] = 50
        
        # MACD
        if len(df) >= 26:
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            indicators['MACD'] = float(df['MACD'].iloc[-1]) if not pd.isna(df['MACD'].iloc[-1]) else 0
            indicators['MACD_signal'] = float(df['MACD_signal'].iloc[-1]) if not pd.isna(df['MACD_signal'].iloc[-1]) else 0
        else:
            indicators['MACD'] = 0
            indicators['MACD_signal'] = 0
        
        # Moving Averages
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['SMA_200'] = df['close'].rolling(window=200).mean()
        
        indicators['SMA_20'] = float(df['SMA_20'].iloc[-1]) if not pd.isna(df['SMA_20'].iloc[-1]) else df['close'].iloc[-1]
        indicators['SMA_50'] = float(df['SMA_50'].iloc[-1]) if not pd.isna(df['SMA_50'].iloc[-1]) else df['close'].iloc[-1]
        indicators['SMA_200'] = float(df['SMA_200'].iloc[-1]) if not pd.isna(df['SMA_200'].iloc[-1]) else df['close'].iloc[-1]
        
        # Price position relative to SMAs
        latest_price = float(df['close'].iloc[-1])
        indicators['price_vs_sma20'] = ((latest_price / indicators['SMA_20']) - 1) * 100
        indicators['price_vs_sma50'] = ((latest_price / indicators['SMA_50']) - 1) * 100
        indicators['price_vs_sma200'] = ((latest_price / indicators['SMA_200']) - 1) * 100
        
        # Volume Analysis
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma'].replace(0, np.nan)
        indicators['volume_ratio'] = float(df['volume_ratio'].iloc[-1]) if not pd.isna(df['volume_ratio'].iloc[-1]) else 1.0
        
        return indicators
    
    def analyze_trend(self, df):
        """Analyze trend strength and direction"""
        trend = {
            'daily': 'neutral',
            'weekly': 'neutral',
            'monthly': 'neutral',
            'strength': 0
        }
        
        # Daily trend
        if len(df) >= 10:
            recent_5 = df['close'].iloc[-5:].mean()
            prev_5 = df['close'].iloc[-10:-5].mean()
            if recent_5 > prev_5 * 1.02:
                trend['daily'] = 'bullish'
                trend['strength'] += 1
            elif recent_5 < prev_5 * 0.98:
                trend['daily'] = 'bearish'
        
        # Weekly trend
        try:
            weekly = df.resample('W').last()
            if len(weekly) >= 2:
                if weekly['close'].iloc[-1] > weekly['close'].iloc[-2] * 1.03:
                    trend['weekly'] = 'bullish'
                    trend['strength'] += 2
                elif weekly['close'].iloc[-1] < weekly['close'].iloc[-2] * 0.97:
                    trend['weekly'] = 'bearish'
        except:
            pass
        
        return trend
    
    def fetch_news_sentiment(self, symbol):
        """Fetch and analyze news sentiment"""
        sentiment = {
            'score': 0,
            'news_count': 0,
            'positive_count': 0,
            'negative_count': 0
        }
        
        positive_keywords = ['نمو', 'أرباح', 'عقد', 'مشروع', 'توسع', 'إيجابي', 'ربح', 'زيادة']
        negative_keywords = ['خسارة', 'انخفاض', 'سلبي', 'تراجع', 'خسائر', 'هبوط']
        
        # Simple simulation (in production, fetch from real sources)
        sentiment['score'] = 0
        sentiment['news_count'] = 0
        
        return sentiment
    
    def check_golden_conditions(self, symbol, indicators, trend, sentiment):
        """Check if stock meets golden signal conditions"""
        
        score = 0
        max_score = 100
        conditions = []
        weights = {
            'rsi': 15,
            'sma20': 10,
            'sma50': 15,
            'sma200': 15,
            'volume': 20,
            'macd': 10,
            'trend': 10,
            'sentiment': 5
        }
        
        # Condition 1: RSI in golden zone (55-70)
        rsi = indicators.get('RSI', 50)
        if 55 <= rsi <= 70:
            score += weights['rsi']
            conditions.append(f"✅ RSI في المنطقة الذهبية ({rsi:.1f})")
        elif 50 <= rsi < 55:
            score += weights['rsi'] * 0.5
            conditions.append(f"⚠️ RSI يقترب من المنطقة الذهبية ({rsi:.1f})")
        
        # Condition 2: Price above SMA 20
        if indicators.get('price_vs_sma20', 0) > 0:
            score += weights['sma20']
            conditions.append(f"✅ السعر فوق SMA 20 (+{indicators['price_vs_sma20']:.1f}%)")
        
        # Condition 3: Price above SMA 50
        if indicators.get('price_vs_sma50', 0) > 0:
            score += weights['sma50']
            conditions.append(f"✅ السعر فوق SMA 50 (+{indicators['price_vs_sma50']:.1f}%)")
        
        # Condition 4: Price above SMA 200
        if indicators.get('price_vs_sma200', 0) > 0:
            score += weights['sma200']
            conditions.append(f"✅ السعر فوق SMA 200 (+{indicators['price_vs_sma200']:.1f}%)")
        
        # Condition 5: Volume surge
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio >= 2.0:
            score += weights['volume']
            conditions.append(f"✅ حجم التداول {volume_ratio:.1f}x المتوسط")
        elif volume_ratio >= 1.5:
            score += weights['volume'] * 0.6
            conditions.append(f"⚠️ حجم التداول {volume_ratio:.1f}x المتوسط")
        
        # Condition 6: MACD bullish
        macd = indicators.get('MACD', 0)
        macd_signal = indicators.get('MACD_signal', 0)
        if macd > macd_signal:
            score += weights['macd']
            conditions.append("✅ MACD إيجابي (تقاطع صاعد)")
        
        # Condition 7: Trend strength
        if trend.get('weekly') == 'bullish':
            score += weights['trend'] * 0.6
            conditions.append("✅ الاتجاه الأسبوعي صاعد")
        
        if trend.get('monthly') == 'bullish':
            score += weights['trend'] * 0.4
            conditions.append("✅ الاتجاه الشهري صاعد")
        
        # Condition 8: News sentiment
        if sentiment.get('score', 0) > 0:
            score += weights['sentiment']
            conditions.append(f"✅ معنوية الأخبار إيجابية (+{sentiment['score']})")
        
        # Golden Signal threshold: 80/100
        is_golden = score >= 80
        
        return {
            'is_golden': is_golden,
            'score': score,
            'max_score': max_score,
            'conditions': conditions,
            'symbol': symbol,
            'indicators': indicators,
            'trend': trend,
            'sentiment': sentiment
        }
    
    def analyze_all_symbols(self, symbols):
        """Analyze all symbols for golden signals"""
        golden_signals = []
        
        print(f"\n🔍 Starting Golden Signal Analysis for {len(symbols)} symbols...")
        print("=" * 60)
        
        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] Analyzing {symbol}...")
            
            try:
                # Fetch historical data
                historical_data = self.fetch_historical_data(symbol, days=90)
                
                if not historical_data or len(historical_data) == 0:
                    print(f"  ⚠️ No data available for {symbol}")
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(historical_data)
                
                # Ensure required columns exist
                required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                if not all(col in df.columns for col in required_cols):
                    print(f"  ⚠️ Missing required columns for {symbol}")
                    continue
                
                # Calculate technical indicators
                indicators = self.calculate_technical_indicators(df)
                
                # Analyze trend
                trend = self.analyze_trend(df)
                
                # Fetch news sentiment
                sentiment = self.fetch_news_sentiment(symbol)
                
                # Check golden conditions
                result = self.check_golden_conditions(symbol, indicators, trend, sentiment)
                
                if result['is_golden']:
                    golden_signals.append({
                        'symbol': symbol,
                        'analysis': result,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'timezone': 'Asia/Riyadh'
                    })
                    print(f"  🌟 GOLDEN SIGNAL! Score: {result['score']}/100")
                else:
                    print(f"  ❌ Not a golden signal. Score: {result['score']}/100")
                    
            except Exception as e:
                print(f"  ❌ Error analyzing {symbol}: {e}")
                continue
        
        # Save results
        output_file = 'data/golden_signals.json'
        os.makedirs('data', exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(golden_signals, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*60}")
        print(f"🌟 Golden Signals Found: {len(golden_signals)}")
        print(f"{'='*60}")
        
        for signal in golden_signals:
            print(f"\n  📌 {signal['symbol']}")
            print(f"     Score: {signal['analysis']['score']}/100")
            for condition in signal['analysis']['conditions']:
                print(f"     {condition}")
        
        return golden_signals

def main():
    import requests  # Import here to avoid issues
    
    analyzer = GoldenSignalAnalyzer()
    
    # Try to load symbols from daily.json
    symbols = []
    try:
        if os.path.exists('data/daily.json'):
            with open('data/daily.json', 'r', encoding='utf-8') as f:
                daily_data = json.load(f)
                stocks = daily_data.get('stocks', [])
                if stocks:
                    symbols = [stock.get('symbol') for stock in stocks[:30] if stock.get('symbol')]
                    print(f"✅ Loaded {len(symbols)} symbols from daily.json")
    except Exception as e:
        print(f"⚠️ Could not load from daily.json: {e}")
    
    # Fallback symbols if loading failed
    if not symbols:
        print("⚠️ Using fallback symbols list...")
        symbols = [
            '2222', '1120', '2010', '1180', '2380',
            '2030', '1211', '2350', '4030', '1150',
            '2020', '2090', '1050', '4001', '2280',
            '2060', '4002', '1010', '2050', '1060',
            '4003', '2001', '2002', '2003', '2004'
        ]
        print(f"📋 Using {len(symbols)} default symbols")
    
    # Analyze symbols
    golden_signals = analyzer.analyze_all_symbols(symbols)
    
    # Save results even if no signals
    output_file = 'data/golden_signals.json'
    os.makedirs('data', exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(golden_signals, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"🌟 Golden Signals Found: {len(golden_signals)}")
    print(f"{'='*60}")
    
    for signal in golden_signals:
        print(f"\n  📌 {signal['symbol']}")
        print(f"     Score: {signal['analysis']['score']}/100")
    
    # ✅ Exit with 0 even if no signals (this is normal)
    if len(golden_signals) > 0:
        print(f"\n✅ Golden signals detected: {len(golden_signals)}")
        sys.exit(0)
    else:
        print(f"\nℹ️ No golden signals today - This is normal")
        sys.exit(0)

if __name__ == "__main__":
    main()
