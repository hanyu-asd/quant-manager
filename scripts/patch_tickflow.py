#!/usr/bin/env python3
import sys
import os
import inspect

# 将当前工作目录加入模块搜索路径
sys.path.insert(0, os.getcwd())

try:
    from data_provider import base
except ImportError as e:
    print(f"⚠️ 无法导入 data_provider.base: {e}")
    sys.exit(0)

print("🔍 扫描 data_provider 中所有 Fetcher 类的可调用方法：")
fetcher_classes = []
for name, obj in inspect.getmembers(base):
    if name.endswith('Fetcher') and inspect.isclass(obj):
        fetcher_classes.append((name, obj))
        methods = []
        for attr in dir(obj):
            if callable(getattr(obj, attr)) and not attr.startswith('_'):
                methods.append(attr)
        print(f"\n📦 {name}:")
        if methods:
            for m in methods:
                print(f"    {m}")
        else:
            print("    (无可调用方法)")

if not fetcher_classes:
    print("⚠️ 未找到任何 Fetcher 类，可能 data_provider 结构已变化。")

print("\n✅ 调试信息已打印。请将以上输出复制给开发者，以便确定需要替换的方法名。")
sys.exit(0)  # 安全退出，不阻断流水线