#!/usr/bin/env python3
import sys
import os

# 将当前工作目录（daily_stock_analysis 根目录）添加到模块搜索路径
sys.path.insert(0, os.getcwd())

import pandas as pd
from datetime import datetime, timedelta

# ---------- 1. 检查 TickFlow 是否可用 ----------
try:
    import tickflow as tf
    TICKFLOW_AVAILABLE = True
except ImportError:
    TICKFLOW_AVAILABLE = False
    print("⚠️ TickFlow 未安装，将使用原始数据源")

# ---------- 2. 导入需要修补的数据源类 ----------
try:
    from data_provider.tencent_fetcher import TencentFetcher
    from data_provider.efinance_fetcher import EfinanceFetcher
except ImportError as e:
    print(f"⚠️ 无法导入数据源模块: {e}")
    sys.exit(0)  # 安全退出，不影响流水线

# ---------- 3. 辅助函数：查找类中可能的方法名 ----------
def find_method(cls, possible_names):
    for name in possible_names:
        if hasattr(cls, name) and callable(getattr(cls, name)):
            return name
    return None

# 定义可能的方法名列表（按常见顺序）
possible_methods = ['get_realtime_quotes', 'get_realtime', 'fetch_realtime', 'get_quotes']

tencent_method = find_method(TencentFetcher, possible_methods)
efinance_method = find_method(EfinanceFetcher, possible_methods)

if not tencent_method or not efinance_method:
    print(f"⚠️ 未找到合适的方法 (Tencent: {tencent_method}, Efinance: {efinance_method})，跳过补丁")
    sys.exit(0)  # 安全退出

# 保存原始方法
_original_tencent = getattr(TencentFetcher, tencent_method)
_original_efinance = getattr(EfinanceFetcher, efinance_method)

# ---------- 4. 数据转换函数 ----------
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
    """尝试从 TickFlow 免费接口获取指定标的的最近交易日日K数据"""
    if not TICKFLOW_AVAILABLE:
        return None
    today = datetime.now().strftime('%Y-%m-%d')
    # 尝试今天及前4天（以防今天数据未更新）
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

# ---------- 5. 补丁函数 ----------
def patched_get_realtime(self, symbols):
    data = get_tickflow_realtime(symbols)
    return data if data is not None else _original_tencent(self, symbols)

def patched_efinance_realtime(self, symbols):
    data = get_tickflow_realtime(symbols)
    return data if data is not None else _original_efinance(self, symbols)

# ---------- 6. 应用补丁 ----------
setattr(TencentFetcher, tencent_method, patched_get_realtime)
setattr(EfinanceFetcher, efinance_method, patched_efinance_realtime)

print(f"✅ TickFlow 补丁应用成功 (替换了 {tencent_method} 和 {efinance_method})")