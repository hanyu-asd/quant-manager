#!/usr/bin/env python3
import sys
import os

# 关键：将当前工作目录（即 daily_stock_analysis 根目录）添加到 Python 模块搜索路径
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
    from data_provider.tencent_fetcher import TencentFetcher
    from data_provider.efinance_fetcher import EfinanceFetcher
except ImportError as e:
    print(f"⚠️ 无法导入数据源模块: {e}")
    sys.exit(1)

# 保存原始方法
_original_tencent = TencentFetcher.get_realtime_quotes
_original_efinance = EfinanceFetcher.get_realtime_quotes

def _tickflow_to_realtime(symbol, row):
    close = row.get('close', 0)
    pre_close = row.get('pre_close', close)
    change_pct = ((close - pre_close) / pre_close * 100) if pre_close else 0.0
    return {
        'code': symbol,
        'name': symbol,
        'price': close,
        'open': row.get('open', close),
        'high': row.get('high', close),
        'low': row.get('low', close),
        'volume': row.get('volume', 0),
        'amount': row.get('volume', 0) * close,
        'change_pct': change_pct,
        'pre_close': pre_close,
        'change': change_pct,
        'turnover_rate': 0.0,
        'pe_ratio': 0.0,
        'pb_ratio': 0.0,
    }

def get_tickflow_realtime(symbols):
    if not TICKFLOW_AVAILABLE:
        return None
    today = datetime.now().strftime('%Y-%m-%d')
    dates = [today] + [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 5)]
    result = []
    for sym in symbols:
        data = None
        for d in dates:
            try:
                df = tf.free().klines.get(sym, start_date=d, end_date=d)
                if df is not None and not df.empty:
                    data = df.iloc[-1]
                    break
            except Exception:
                continue
        if data is not None:
            result.append(_tickflow_to_realtime(sym, data))
        else:
            print(f"⚠️ TickFlow 未获取到 {sym} 的数据")
    return result if result else None

def patched_get_realtime(self, symbols):
    data = get_tickflow_realtime(symbols)
    return data if data is not None else _original_tencent(self, symbols)

def patched_efinance_realtime(self, symbols):
    data = get_tickflow_realtime(symbols)
    return data if data is not None else _original_efinance(self, symbols)

TencentFetcher.get_realtime_quotes = patched_get_realtime
EfinanceFetcher.get_realtime_quotes = patched_efinance_realtime

print("✅ TickFlow 补丁应用成功（优先使用免费日K数据）")