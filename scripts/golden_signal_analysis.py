#!/usr/bin/env python3
"""
Golden Signal Analysis - Deep Market Analysis
Analyzes:
1. Historical price patterns (30-90 days)
2. Technical indicators from multiple timeframes
3. Volume analysis
4. News sentiment from trusted sources (Argaam, Mubasher, etc.)
5. Market momentum
6. Sector performance
"""

import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

class GoldenSignalAnalyzer:
    def __init__(self):
        self.symbols = []
        self.analysis_results = []
        self.api_key = os.environ.get('API_KEY', '')
        self.api_url = os.environ.get('API_URL', 'https://www.sahmk.sa/api/v1')
        
    def fetch_historical_data(self, symbol, days=90):
        """Fetch 90 days historical data from sahmk.sa API"""
        try:
            url = f"{self.api_url}/stocks/{symbol}/historical"
            params = {'days': days, 'apikey': self.api_key}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️ Failed to fetch data for {symbol}: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error fetching data for {symbol}: {e}")
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
            indicators['RSI'] = df['RSI'].iloc[-1]
        else:
            indicators['RSI'] = 50
        
        # MACD
        if len(df) >= 26:
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            indicators['MACD'] = df['MACD'].iloc[-1]
            indicators['MACD_signal'] = df['MACD_signal'].iloc[-1]
        else:
            indicators['MACD'] = 0
            indicators['MACD_signal'] = 0
        
        # Moving Averages
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['SMA_200'] = df['close'].rolling(window=200).mean()
        
        indicators['SMA_20'] = df['SMA_20'].iloc[-1]
        indicators['SMA_50'] = df['SMA_50'].iloc[-1]
        indicators['SMA_200'] = df['SMA_200'].iloc[-1]
        
        # Price position relative to SMAs
        latest_price = df['close'].iloc[-1]
        indicators['price_vs_sma20'] = ((latest_price / indicators['SMA_20']) - 1) * 100
        indicators['price_vs_sma50'] = ((latest_price / indicators['SMA_50']) - 1) * 100
        indicators['price_vs_sma200'] = ((latest_price / indicators['SMA_200']) - 1) * 100
        
        # Volume Analysis
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        indicators['volume_ratio'] = df['volume_ratio'].iloc[-1]
        
        # ATR (Average True Range)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['ATR'] = true_range.rolling(14).mean()
        indicators['ATR'] = df['ATR'].iloc[-1]
        
        # Bollinger Bands
        df['BB_middle'] = df['close'].rolling(window=20).mean()
        df['BB_std'] = df['close'].rolling(window=20).std()
        df['BB_upper'] = df['BB_middle'] + (df['BB_std'] * 2)
        df['BB_lower'] = df['BB_middle'] - (df['BB_std'] * 2)
        indicators['BB_position'] = ((latest_price - df['BB_lower'].iloc[-1]) / 
                                     (df['BB_upper'].iloc[-1] - df['BB_lower'].iloc[-1])) * 100
        
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
        if len(df) >= 5:
            recent_5 = df['close'].iloc[-5:].mean()
            prev_5 = df['close'].iloc[-10:-5].mean()
            if recent_5 > prev_5 * 1.02:
                trend['daily'] = 'bullish'
                trend['strength'] += 1
            elif recent_5 < prev_5 * 0.98:
                trend['daily'] = 'bearish'
        
        # Weekly trend (resample)
        weekly = df.resample('W').last()
        if len(weekly) >= 2:
            if weekly['close'].iloc[-1] > weekly['close'].iloc[-2] * 1.03:
                trend['weekly'] = 'bullish'
                trend['strength'] += 2
            elif weekly['close'].iloc[-1] < weekly['close'].iloc[-2] * 0.97:
                trend['weekly'] = 'bearish'
        
        # Monthly trend
        monthly = df.resample('M').last()
        if len(monthly) >= 2:
            if monthly['close'].iloc[-1] > monthly['close'].iloc[-2] * 1.05:
                trend['monthly'] = 'bullish'
                trend['strength'] += 3
            elif monthly['close'].iloc[-1] < monthly['close'].iloc[-2] * 0.95:
                trend['monthly'] = 'bearish'
        
        return trend
    
    def fetch_news_sentiment(self, symbol):
        """Fetch and analyze news sentiment from trusted sources"""
        sentiment = {
            'score': 0,
            'news_count': 0,
            'positive_count': 0,
            'negative_count': 0
        }
        
        # Keywords for sentiment analysis
        positive_keywords = [
            'نمو', 'أرباح', 'عقد', 'مشروع', 'توسع', 'إيجابي', 'ربح', 
            'زيادة', 'ارتفاع', 'نجاح', 'إنجاز', 'تفوق', 'مكسب'
        ]
        negative_keywords = [
            'خسارة', 'انخفاض', 'سلبي', 'تراجع', 'خسائر', 'هبوط', 
            'تدهور', 'مشكلة', 'أزمة', 'انكماش'
        ]
        
        try:
            # Try to fetch from Argaam API (if available)
            url = f"https://www.argaam.com/api/news/stock/{symbol}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                news_data = response.json()
                news_items = news_data.get('data', [])[:10]
                
                for news in news_items:
                    sentiment['news_count'] += 1
                    text = news.get('title', '') + ' ' + news.get('summary', '')
                    
                    for keyword in positive_keywords:
                        if keyword in text:
                            sentiment['score'] += 1
                            sentiment['positive_count'] += 1
                            break
                    
                    for keyword in negative_keywords:
                        if keyword in text:
                            sentiment['score'] -= 1
                            sentiment['negative_count'] += 1
                            break
        except Exception as e:
            print(f"⚠️ Could not fetch news for {symbol}: {e}")
        
        return sentiment
    
    def check_golden_conditions(self, symbol, indicators, trend, sentiment):
        """
        Check if stock meets golden signal conditions:
        - Strong momentum (RSI 55-70)
        - Price above SMA 20, 50, 200
        - Volume surge (2x average)
        - MACD bullish crossover
        - Positive news sentiment
        - Strong weekly/monthly trend
        """
        
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
        
        # Condition 1: RSI in golden zone (55-70) - Not overbought
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
        
        # Condition 4: Price above SMA 200 (Long-term trend)
        if indicators.get('price_vs_sma200', 0) > 0:
            score += weights['sma200']
            conditions.append(f"✅ السعر فوق SMA 200 (+{indicators['price_vs_sma200']:.1f}%)")
        
        # Condition 5: Volume surge (at least 1.5x average)
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
        
        # Golden Signal threshold: 80/100 (Very strict)
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
    analyzer = GoldenSignalAnalyzer()
    
    # Load symbols from daily data or use top stocks
    try:
        with open('data/daily.json', 'r', encoding='utf-8') as f:
            daily_data = json.load(f)
            symbols = [stock.get('symbol') for stock in daily_data.get('stocks', [])[:30]]
    except:
        # Fallback: Top 20 Saudi stocks
        symbols = [
            '2222', '1120', '2010', '1180', '2380',
            '2030', '1211', '2350', '4030', '1150',
            '2020', '2090', '1050', '4001', '2280',
            '2060', '4002', '1010', '2050', '1060'
        ]
    
    golden_signals = analyzer.analyze_all_symbols(symbols)
    
    # Exit code for GitHub Actions
    if len(golden_signals) > 0:
        print(f"\n✅ Golden signals detected: {len(golden_signals)}")
        exit(0)  # Success
    else:
        print(f"\nℹ️ No golden signals today")
        exit(1)  # No signals

if __name__ == "__main__":
    main()
