#!/usr/bin/env python3
"""
AlphaEvo 包装脚本：支持 backtest / evolve / optimize 模式
通过 Monkey Patching 替换 yfinance 为 TickFlow 或 Tushare
"""
import sys
import os
import argparse
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
                # 假定列名为: date, open, high, low, close, volume
                df = df.rename(columns={
                    'open': 'Open', 'high': 'High', 'low': 'Low',
                    'close': 'Close', 'volume': 'Volume'
                })
                return df
        if USE_TUSHARE and TUSHARE_TOKEN:
            pro = ts.pro_api()
            if isinstance(symbols, list):
                symbols = ','.join(symbols)
            # 转换日期格式
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

# ----- 导入 AlphaEvo 核心 -----
from alphaevo.cli import main as alphaevo_main

def main():
    parser = argparse.ArgumentParser(description="AlphaEvo 包装运行器")
    parser.add_argument('mode', choices=['backtest', 'evolve', 'optimize'],
                        help='运行模式')
    parser.add_argument('--input', help='输入 CSV 文件路径（backtest 模式）')
    parser.add_argument('--output', help='输出 CSV 文件路径（backtest 模式）')
    parser.add_argument('--method', help='进化方法（evolve 模式）')
    parser.add_argument('--full-scan', action='store_true', help='全量扫描（optimize 模式）')
    # 其他参数直接传递给 AlphaEvo
    args, unknown = parser.parse_known_args()

    # 构造 AlphaEvo 命令行参数
    cmd_args = [args.mode]
    if args.mode == 'backtest':
        # backtest 需要指定策略文件，这里假设使用默认策略，或通过配置文件
        # 简单处理：调用 AlphaEvo 的 backtest 命令，并指定输入输出
        # 这里我们直接调用 alphaevo run 命令，但 backtest 可能是子命令
        # 根据 AlphaEvo 实际 CLI 调整，此处举例
        cmd_args.extend(['--input', args.input, '--output', args.output])
    elif args.mode == 'evolve':
        cmd_args.extend(['--method', args.method or 'llm'])
    elif args.mode == 'optimize':
        if args.full_scan:
            cmd_args.append('--full-scan')
    # 添加未知参数
    cmd_args.extend(unknown)

    # 替换 sys.argv
    sys.argv = ['alphaevo'] + cmd_args
    alphaevo_main()

if __name__ == "__main__":
    main()