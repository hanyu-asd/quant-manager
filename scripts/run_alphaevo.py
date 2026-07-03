#!/usr/bin/env python3
"""
AlphaEvo 包装脚本：支持 backtest / evolve / optimize 模式
通过 Monkey Patching 替换 yfinance 为 TickFlow 或 Tushare
"""
import sys
import os
import pandas as pd

# ----- 数据源适配层 -----
try:
    import tickflow as tf
    USE_TICKFLOW = True
except ImportError:
    USE_TICKFLOW = False

try:
    import tushare as ts
    USE_TUSHARE = True
except ImportError:
    USE_TUSHARE = False

TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN")
if TUSHARE_TOKEN and USE_TUSHARE:
    ts.set_token(TUSHARE_TOKEN)

class FakeYFinance:
    @staticmethod
    def download(symbols, start=None, end=None, **kwargs):
        print(f"[FakeYFinance] 获取数据: {symbols}, {start} - {end}")
        if USE_TICKFLOW:
            data = tf.get_daily(symbols, start_date=start, end_date=end)
            if data is not None and not data.empty:
                df = pd.DataFrame(data)
                df = df.rename(columns={
                    'open': 'Open', 'high': 'High', 'low': 'Low',
                    'close': 'Close', 'volume': 'Volume'
                })
                return df
        if USE_TUSHARE and TUSHARE_TOKEN:
            pro = ts.pro_api()
            if isinstance(symbols, list):
                symbols = ','.join(symbols)
            s = start.replace('-', '') if start else None
            e = end.replace('-', '') if end else None
            df = pro.daily(ts_code=symbols, start_date=s, end_date=e)
            if df is not None and not df.empty:
                df = df.rename(columns={
                    'open': 'Open', 'high': 'High', 'low': 'Low',
                    'close': 'Close', 'vol': 'Volume'
                })
                return df
        raise RuntimeError("无法获取数据，请确保安装 tickflow 或配置 TUSHARE_TOKEN")

# 替换 yfinance
sys.modules['yfinance'] = FakeYFinance

# ----- 导入 AlphaEvo 并调用入口函数 -----
def run_alphaevo():
    # 尝试多种常见的入口点
    candidates = [
        ('alphaevo.cli', 'main'),
        ('alphaevo.cli', 'cli'),
        ('alphaevo', 'main'),
        ('alphaevo.__main__', 'main'),
    ]
    for module_name, func_name in candidates:
        try:
            mod = __import__(module_name, fromlist=[func_name])
            func = getattr(mod, func_name, None)
            if callable(func):
                func()
                return
        except (ImportError, AttributeError):
            continue

    # 如果都不行，尝试直接调用 alphaevo 包（可能作为脚本）
    try:
        import alphaevo
        if hasattr(alphaevo, '__main__') and callable(alphaevo.__main__):
            alphaevo.__main__()
            return
    except AttributeError:
        pass

    raise RuntimeError("无法找到 AlphaEvo 的入口函数，请检查安装")

if __name__ == "__main__":
    # 保留原始命令行参数，交给入口函数处理
    run_alphaevo()