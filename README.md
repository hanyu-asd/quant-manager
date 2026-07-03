# 量化投研管理系统

基于 daily_stock_analysis + AlphaSift + AlphaEvo 的统一管理仓库。

## 流水线流程（每日盘后）
1. 大盘复盘（通过 TickFlow Monkey Patching 获取数据）
2. 策略自动选择（根据盘面信号）
3. AlphaSift 选股
4. AlphaEvo 回测校验（含降级）
5. daily_stock_analysis 完整分析推送
6. AlphaEvo 策略进化（每周五 / 每月1号）

## 触发方式
- 自动：工作日北京时间 16:00
- 手动：Actions 页面点击 "Run workflow"

## 配置 Secrets
参考 [GitHub Secrets 清单](#) 配置所有密钥。