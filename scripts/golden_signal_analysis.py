#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Golden Signal Analysis - Deep Market Analysis
"""

import json
import os
import sys
import requests  # ✅ هذا هو السطر المفقود!
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

class GoldenSignalAnalyzer:
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # قائمة الأسهم للتحليل
        self.stocks_to_analyze = [
            '2222', '1120', '2010', '2050', '1180', '2380', '2030', '1211',
            '2350', '4030', '1150', '2020', '2090', '1050', '4001', '2280',
            '2060', '4002', '1010', '1060', '4003', '2001', '2002', '2003', '2004'
        ]
        
    def fetch_historical_data(self, symbol, days=90):
        """Fetch historical data - simplified version"""
        try:
            # Try to load from daily.json first
            daily_file = self.data_dir / "daily.json"
            if daily_file.exists():
                with open(daily_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    stocks = data.get('stocks', [])
                    for stock in stocks:
                        if stock.get('symbol') == symbol:
                            # Generate mock historical data based on current data
                            current_price = stock.get('current_price', 100)
                            return self._generate_historical_data(current_price, days)
            
            return None
        except Exception as e:
            print(f"⚠️ Error fetching data for {symbol}: {e}")
            return None
    
    def _generate_historical_data(self, current_price, days):
        """Generate simplified historical data"""
        import random
        data = []
        base_price = current_price * 0.9  # Start 10% lower
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=days-i)).strftime('%Y-%m-%d')
            # Add some randomness
            price_variation = random.uniform(-0.02, 0.02)
            price = base_price * (1 + price_variation)
            base_price = price
            
            data.append({
                'date': date,
                'open': price * (1 + random.uniform(-0.01, 0.01)),
                'high': price * (1 + random.uniform(0, 0.02)),
                'low': price * (1 + random.uniform(-0.02, 0)),
                'close': price,
                'volume': random.randint(100000, 1000000)
            })
        
        return data
    
    def calculate_technical_indicators(self, df):
        """Calculate technical indicators"""
        indicators = {}
        
        # RSI
        if len(df) >= 14:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            indicators['RSI'] = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50
        else:
            indicators['RSI'] = 50
        
        # MACD
        if len(df) >= 26:
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            indicators['MACD'] = float(df['MACD'].iloc[-1])
            indicators['MACD_signal'] = float(df['MACD_signal'].iloc[-1])
        else:
            indicators['MACD'] = 0
            indicators['MACD_signal'] = 0
        
        # Moving Averages
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['SMA_200'] = df['close'].rolling(window=200).mean()
        
        indicators['SMA_20'] = float(df['SMA_20'].iloc[-1])
        indicators['SMA_50'] = float(df['SMA_50'].iloc[-1])
        indicators['SMA_200'] = float(df['SMA_200'].iloc[-1])
        
        latest_price = float(df['close'].iloc[-1])
        indicators['price_vs_sma20'] = ((latest_price / indicators['SMA_20']) - 1) * 100
        indicators['price_vs_sma50'] = ((latest_price / indicators['SMA_50']) - 1) * 100
        indicators['price_vs_sma200'] = ((latest_price / indicators['SMA_200']) - 1) * 100
        
        # Volume
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma'].replace(0, np.nan)
        indicators['volume_ratio'] = float(df['volume_ratio'].iloc[-1]) if not pd.isna(df['volume_ratio'].iloc[-1]) else 1.0
        
        return indicators
    
    def check_golden_conditions(self, symbol, indicators):
        """Check if stock meets golden signal conditions"""
        score = 0
        max_score = 100
        conditions = []
        
        # RSI in golden zone (55-70)
        rsi = indicators.get('RSI', 50)
        if 55 <= rsi <= 70:
            score += 25
            conditions.append(f"✅ RSI في المنطقة الذهبية ({rsi:.1f})")
        
        # Price above SMAs
        if indicators.get('price_vs_sma20', 0) > 0:
            score += 15
            conditions.append(f"✅ السعر فوق SMA 20")
        
        if indicators.get('price_vs_sma50', 0) > 0:
            score += 20
            conditions.append(f"✅ السعر فوق SMA 50")
        
        if indicators.get('price_vs_sma200', 0) > 0:
            score += 20
            conditions.append(f"✅ السعر فوق SMA 200")
        
        # Volume surge
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio >= 2.0:
            score += 15
            conditions.append(f"✅ حجم التداول {volume_ratio:.1f}x المتوسط")
        elif volume_ratio >= 1.5:
            score += 10
            conditions.append(f"⚠️ حجم التداول {volume_ratio:.1f}x المتوسط")
        
        # MACD bullish
        if indicators.get('MACD', 0) > indicators.get('MACD_signal', 0):
            score += 5
            conditions.append("✅ MACD إيجابي")
        
        is_golden = score >= 80
        
        return {
            'is_golden': is_golden,
            'score': score,
            'max_score': max_score,
            'conditions': conditions,
            'symbol': symbol,
            'indicators': indicators
        }
    
    def analyze_all_symbols(self, symbols):
        """Analyze all symbols for golden signals"""
        golden_signals = []
        
        print(f"\n🔍 Starting Golden Signal Analysis for {len(symbols)} symbols...")
        print("=" * 60)
        
        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] Analyzing {symbol}...")
            
            try:
                historical_data = self.fetch_historical_data(symbol, days=90)
                
                if not historical_data or len(historical_data) == 0:
                    print(f"  ⚠️ No data available for {symbol}")
                    continue
                
                df = pd.DataFrame(historical_data)
                indicators = self.calculate_technical_indicators(df)
                result = self.check_golden_conditions(symbol, indicators)
                
                if result['is_golden']:
                    golden_signals.append({
                        'symbol': symbol,
                        'analysis': result,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    print(f"  🌟 GOLDEN SIGNAL! Score: {result['score']}/100")
                else:
                    print(f"  ❌ Not a golden signal. Score: {result['score']}/100")
                    
            except Exception as e:
                print(f"  ❌ Error analyzing {symbol}: {e}")
                continue
        
        # Save results
        output_file = self.data_dir / "golden_signals.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(golden_signals, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*60}")
        print(f"🌟 Golden Signals Found: {len(golden_signals)}")
        print(f"{'='*60}")
        
        return golden_signals

def main():
    analyzer = GoldenSignalAnalyzer()
    
    golden_signals = analyzer.analyze_all_symbols(analyzer.stocks_to_analyze)
    
    print(f"\n{'='*60}")
    print(f"🌟 Golden Signals Found: {len(golden_signals)}")
    print(f"{'='*60}")
    
    if len(golden_signals) > 0:
        print(f"\n✅ Golden signals detected: {len(golden_signals)}")
        sys.exit(0)
    else:
        print(f"\nℹ️ No golden signals today - This is normal")
        sys.exit(0)

if __name__ == "__main__":
    main()

