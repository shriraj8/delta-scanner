"""
Delta Exchange Spot Pivot Scanner - Streamlit Web App
Works on mobile and laptop via browser
"""

import streamlit as st
import requests
from datetime import datetime, timedelta
import pytz
import pandas as pd
import time

st.set_page_config(
    page_title="Delta Pivot Scanner",
    page_icon="📊",
    layout="wide"
)

class SpotPivotScanner:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.delta.exchange"
        self.symbols = ['BTCUSD', 'ETHUSD']
        self.pivots = {}
        self.all_crosses = []
        self.ist = pytz.timezone('Asia/Kolkata')
        self.initial_state_recorded = {}
    
    def calculate_pivot(self, high, low, close):
        return (float(high) + float(low) + float(close)) / 3
    
    def get_pivot_periods(self):
        now = datetime.now(self.ist)
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_midnight = today_midnight - timedelta(days=1)
        yesterday_noon = yesterday_midnight + timedelta(hours=12)
        
        return {
            'first_half_start': int(yesterday_midnight.timestamp()),
            'first_half_end': int(yesterday_noon.timestamp()),
            'second_half_start': int(yesterday_noon.timestamp()),
            'second_half_end': int(today_midnight.timestamp()),
            'day_start_ts': int(today_midnight.timestamp())
        }
    
    def fetch_ohlc(self, symbol, start_time, end_time, resolution='1h'):
        try:
            url = f"{self.base_url}/v2/history/candles"
            params = {
                'symbol': symbol,
                'resolution': resolution,
                'start': start_time,
                'end': end_time
            }
            headers = {'api-key': self.api_key, 'Content-Type': 'application/json'}
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                candles = response.json().get('result', [])
                if candles:
                    candles.sort(key=lambda x: int(x['time']))
                return candles
            return None
        except:
            return None
    
    def calculate_pivots_for_symbol(self, symbol):
        periods = self.get_pivot_periods()
        
        first_half = self.fetch_ohlc(symbol, periods['first_half_start'], periods['first_half_end'])
        second_half = self.fetch_ohlc(symbol, periods['second_half_start'], periods['second_half_end'])
        
        if not first_half or not second_half or len(first_half) == 0 or len(second_half) == 0:
            return None
        
        pivot1 = self.calculate_pivot(
            max([float(c['high']) for c in first_half]),
            min([float(c['low']) for c in first_half]),
            float(first_half[-1]['close'])
        )
        
        pivot2 = self.calculate_pivot(
            max([float(c['high']) for c in second_half]),
            min([float(c['low']) for c in second_half]),
            float(second_half[-1]['close'])
        )
        
        return {'pivot1': pivot1, 'pivot2': pivot2}
    
    def calculate_all_pivots(self):
        for symbol in self.symbols:
            pivots = self.calculate_pivots_for_symbol(symbol)
            if pivots:
                self.pivots[symbol] = pivots
        return len(self.pivots) > 0
    
    def scan_all_crosses(self, symbol, pivot1, pivot2):
        periods = self.get_pivot_periods()
        now = datetime.now(self.ist)
        
        candles = self.fetch_ohlc(symbol, periods['day_start_ts'], int(now.timestamp()), resolution='5m')
        
        if not candles or len(candles) == 0:
            return []
        
        crosses = []
        last_state = None
        
        for i, candle in enumerate(candles):
            candle_time = int(candle['time'])
            candle_close = float(candle['close'])
            cross_datetime = datetime.fromtimestamp(candle_time, tz=self.ist)
            
            if candle_close > pivot1 and candle_close > pivot2:
                current_state = 'above'
            elif candle_close < pivot1 and candle_close < pivot2:
                current_state = 'below'
            else:
                current_state = 'between'
            
            # First candle
            if i == 0 and current_state in ['above', 'below'] and symbol not in self.initial_state_recorded:
                direction = "UPTREND" if current_state == 'above' else "DOWNTREND"
                
                crosses.append({
                    'Time': cross_datetime.strftime('%d-%b %H:%M IST'),
                    'Symbol': symbol,
                    'Direction': direction,
                    'Price': f"{candle_close:.2f}",
                    'Pivot1': f"{pivot1:.2f}",
                    'Pivot2': f"{pivot2:.2f}",
                    'Type': 'DAY_START'
                })
                
                self.initial_state_recorded[symbol] = True
            
            # State changes
            elif current_state in ['above', 'below'] and last_state in ['above', 'below'] and current_state != last_state:
                direction = "UPTREND" if current_state == 'above' else "DOWNTREND"
                
                crosses.append({
                    'Time': cross_datetime.strftime('%d-%b %H:%M IST'),
                    'Symbol': symbol,
                    'Direction': direction,
                    'Price': f"{candle_close:.2f}",
                    'Pivot1': f"{pivot1:.2f}",
                    'Pivot2': f"{pivot2:.2f}",
                    'Type': 'CROSS'
                })
            
            if current_state in ['above', 'below']:
                last_state = current_state
        
        return crosses
    
    def scan(self):
        if not self.calculate_all_pivots():
            return False
        
        for symbol, pivots in self.pivots.items():
            crosses = self.scan_all_crosses(symbol, pivots['pivot1'], pivots['pivot2'])
            self.all_crosses.extend(crosses)
        
        return True


# Streamlit UI
st.title("📊 Delta Exchange Spot Pivot Scanner")
st.markdown("**Real-time pivot cross detection for BTC and ETH**")

# Sidebar for API key
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Delta Exchange API Key", type="password")
    
    st.markdown("---")
    st.markdown("### 📖 How it works")
    st.markdown("""
    **Pivot Calculation:**
    - Pivot1: Yesterday 00:00-12:00 IST
    - Pivot2: Yesterday 12:00-Today 00:00 IST
    
    **Signals:**
    - 🟢 UPTREND: Price crosses above both pivots
    - 🔴 DOWNTREND: Price crosses below both pivots
    """)
    
    auto_refresh = st.checkbox("Auto-refresh every 3 minutes", value=False)

# Main content
if not api_key:
    st.info("👈 Please enter your Delta Exchange API Key in the sidebar to start")
else:
    # Scan button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🔍 Scan Now", type="primary"):
            st.session_state['scan_trigger'] = True
    with col2:
        last_scan = st.empty()
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(180)  # Wait 3 minutes
        st.rerun()
    
    # Perform scan
    if 'scan_trigger' in st.session_state or auto_refresh:
        with st.spinner("Scanning... Please wait"):
            scanner = SpotPivotScanner(api_key)
            success = scanner.scan()
            
            if success:
                now = datetime.now(pytz.timezone('Asia/Kolkata'))
                last_scan.info(f"Last scanned: {now.strftime('%d-%b %H:%M:%S IST')}")
                
                # Display pivots
                st.markdown("### 📌 Current Pivots")
                pivot_cols = st.columns(len(scanner.pivots))
                for idx, (symbol, pivots) in enumerate(scanner.pivots.items()):
                    with pivot_cols[idx]:
                        st.metric(
                            label=f"**{symbol}**",
                            value=f"P1: {pivots['pivot1']:.2f}",
                            delta=f"P2: {pivots['pivot2']:.2f}"
                        )
                
                st.markdown("---")
                
                # Display crosses
                if len(scanner.all_crosses) > 0:
                    st.markdown("### 🎯 Detected Crosses")
                    
                    df = pd.DataFrame(scanner.all_crosses)
                    
                    # Color code by direction
                    def highlight_direction(row):
                        if row['Direction'] == 'UPTREND':
                            return ['background-color: #d4edda']*len(row)
                        elif row['Direction'] == 'DOWNTREND':
                            return ['background-color: #f8d7da']*len(row)
                        return ['']*len(row)
                    
                    styled_df = df.style.apply(highlight_direction, axis=1)
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                    
                    # Summary
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        uptrends = len([c for c in scanner.all_crosses if c['Direction'] == 'UPTREND'])
                        st.metric("🟢 UPTREND Crosses", uptrends)
                    with col2:
                        downtrends = len([c for c in scanner.all_crosses if c['Direction'] == 'DOWNTREND'])
                        st.metric("🔴 DOWNTREND Crosses", downtrends)
                    with col3:
                        st.metric("📊 Total Crosses", len(scanner.all_crosses))
                    
                    # Download button
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Results (CSV)",
                        data=csv,
                        file_name=f"pivot_crosses_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No crosses detected from midnight 00:00 IST")
            else:
                st.error("❌ Failed to fetch data. Please check your API key.")
        
        if 'scan_trigger' in st.session_state:
            del st.session_state['scan_trigger']

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>Delta Exchange Spot Pivot Scanner | "
    "Times in IST | Updates every 3 minutes</div>",
    unsafe_allow_html=True
)
