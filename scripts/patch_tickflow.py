#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.getcwd())

import pandas as pd
from datetime import datetime, timedelta

try:
    import tickflow as tf
    TICKFLOW_AVAILABLE = True
except ImportError:
    TICKFLOW_AVAILABLE = False
    print("⚠️ TickFlow 未安装，降级到原始数据源")

try:
    from data_provider.base import BaseFetcher
except ImportError as e:
    print(f"⚠️ 无法导入 BaseFetcher: {e}")
    sys.exit(0)

_original_get_daily_data = BaseFetcher.get_daily_data

def _tickflow_to_dataframe(df_raw):
    if df_raw is None or df_raw.empty:
        return None
    df = df_raw.copy()
    if 'date' in df.columns:
        df.set_index('date', inplace=True)
    df.rename(columns={'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'}, inplace=True)
    if 'volume' not in df.columns:
        df['volume'] = 0
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

def _get_tickflow_daily(symbols, start_date=None, end_date=None, adjust=None):
    if not TICKFLOW_AVAILABLE:
        return None
    try:
        if isinstance(symbols, str):
            symbols = [symbols]
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        all_data = {}
        for sym in symbols:
            df = tf.free().klines.get(sym, start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                df = _tickflow_to_dataframe(df)
                if df is not None:
                    all_data[sym] = df
        if not all_data:
            return None
        if len(all_data) == 1:
            return list(all_data.values())[0]
        return all_data
    except Exception as e:
        print(f"⚠️ TickFlow 获取数据失败: {e}")
        return None

def patched_get_daily_data(self, symbols, start_date=None, end_date=None, adjust=None, **kwargs):
    tickflow_data = _get_tickflow_daily(symbols, start_date, end_date, adjust)
    if tickflow_data is not None:
        return tickflow_data
    print(f"⚠️ TickFlow 获取 {symbols} 失败，降级到原始数据源")
    return _original_get_daily_data(self, symbols, start_date, end_date, adjust, **kwargs)

BaseFetcher.get_daily_data = patched_get_daily_data
print("✅ TickFlow 补丁应用成功 (BaseFetcher.get_daily_data)")