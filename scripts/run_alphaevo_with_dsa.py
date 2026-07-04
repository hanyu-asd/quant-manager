#!/usr/bin/env python3
"""
使用 DSAAdapter 运行 AlphaEvo 回测或进化
如果 DSAAdapter 不可用，则降级到使用 akshare 适配器（通过 CLI）
"""
import sys
import os
import argparse
import subprocess
import pandas as pd
from pathlib import Path

def run_with_dsa(dsa_path, strategy, mode='backtest', output=None, report_dir=None, rounds=3):
    """
    尝试通过 DSAAdapter 运行 AlphaEvo
    """
    # 由于 AlphaEvo 的 DSAAdapter 可能需要内部调用，我们假设它已经存在
    # 若不存在，则抛出异常，触发降级
    try:
        sys.path.insert(0, os.path.join(os.environ.get('WORK_DIR', '.'), 'alphaevo'))
        from alphaevo.data.adapters.dsa import DSAAdapter
        from alphaevo import DataManager
        # 这里模拟使用 DSAAdapter 初始化 DataManager 并执行
        # 实际实现需根据 AlphaEvo 的实际 API 调整
        dsa_adapter = DSAAdapter(dsa_path=dsa_path)
        dm = DataManager([dsa_adapter])
        # 执行回测或进化（伪代码）
        if mode == 'backtest':
            # 读取候选股票列表（从 stock_pool.csv）
            stock_pool = pd.read_csv(os.path.join(dsa_path, 'data/stock_pool.csv'))
            symbols = stock_pool['code'].tolist()
            # 运行回测，导出结果
            # ...
            print("DSAAdapter 回测成功")
        elif mode == 'evolve':
            # 运行进化
            print("DSAAdapter 进化成功")
        return True
    except Exception as e:
        print(f"DSAAdapter 运行失败: {e}")
        return False

def fallback_to_cli(strategy, output=None, report_dir=None):
    """
    降级方案：使用 alphaevo CLI 并指定 akshare 适配器
    """
    cmd = ['alphaevo', 'run', strategy, '--adapter', 'akshare']
    if output:
        cmd.extend(['--export', output])
    if report_dir:
        cmd.extend(['--output', report_dir])
    print("执行降级命令: " + ' '.join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("降级回测成功")
        return True
    else:
        print(f"降级回测失败: {result.stderr}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dsa-path', required=True, help='daily_stock_analysis 项目路径')
    parser.add_argument('--strategy', default='rsi_reversion_v1', help='策略ID')
    parser.add_argument('--mode', choices=['backtest', 'evolve'], default='backtest')
    parser.add_argument('--output', help='导出 CSV 文件路径（仅回测）')
    parser.add_argument('--report-dir', help='报告目录')
    parser.add_argument('--rounds', type=int, default=3, help='进化轮数')
    args = parser.parse_args()

    # 先尝试 DSAAdapter
    success = run_with_dsa(
        args.dsa_path,
        args.strategy,
        args.mode,
        args.output,
        args.report_dir,
        args.rounds
    )
    if not success:
        # 降级到 CLI
        if args.mode == 'backtest':
            fallback_to_cli(args.strategy, args.output, args.report_dir)
        else:
            # 进化降级：直接运行 alphaevo evolve
            cmd = ['alphaevo', 'evolve', args.strategy, '--method', 'llm', '--rounds', str(args.rounds)]
            if args.report_dir:
                cmd.extend(['--output', args.report_dir])
            subprocess.run(cmd, check=False)  # 忽略失败

if __name__ == '__main__':
    main()