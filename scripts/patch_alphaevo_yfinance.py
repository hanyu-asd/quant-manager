#!/usr/bin/env python3
import sys
import os
import pandas as pd
from datetime import datetime, timedelta

try:
    import yfinance as yf_orig
except ImportError:
    print("⚠️ yfinance 未安装，无法应用补丁")
    sys.exit(0)

_orig_download = yf_orig.download

def tickflow_download(symbols, start=None, end=None, **kwargs):
    print(f"[TickFlow替代yfinance] 获取数据: {symbols}")
    try:
        import tickflow as tf
    except ImportError:
        print("⚠️ TickFlow 未安装，降级到原始 yfinance")
        return _orig_download(symbols, start=start, end=end, **kwargs)

    if isinstance(symbols, str):
        sym_list = [symbols]
    else:
        sym_list = list(symbols)
    if end is None:
        end = datetime.now().strftime('%Y-%m-%d')
    if start is None:
        start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    all_data = {}
    for sym in sym_list:
        try:
            df = tf.free().klines.get(sym, start_date=start, end_date=end)
            if df is not None and not df.empty:
                df_renamed = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
                if 'date' in df_renamed.columns:
                    df_renamed.set_index('date', inplace=True)
                for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                    if col in df_renamed.columns:
                        df_renamed[col] = pd.to_numeric(df_renamed[col], errors='coerce')
                all_data[sym] = df_renamed
            else:
                print(f"⚠️ TickFlow 未获取到 {sym}，降级到 yfinance")
                fallback = _orig_download(sym, start=start, end=end, **kwargs)
                if fallback is not None and not fallback.empty:
                    all_data[sym] = fallback
        except Exception as e:
            print(f"⚠️ TickFlow 获取 {sym} 失败: {e}，降级到 yfinance")
            try:
                fallback = _orig_download(sym, start=start, end=end, **kwargs)
                if fallback is not None and not fallback.empty:
                    all_data[sym] = fallback
            except:
                pass

    if not all_data:
        print("⚠️ 所有数据获取失败，降级到原始 yfinance")
        return _orig_download(symbols, start=start, end=end, **kwargs)

    if len(all_data) == 1:
        return list(all_data.values())[0]
    else:
        combined = pd.concat(all_data, axis=1)
        return combined

yf_orig.download = tickflow_download
import yfinance
yfinance.download = tickflow_download
sys.modules['yfinance'] = yfinance

print("✅ AlphaEvo yfinance 补丁应用成功，优先使用 TickFlow")