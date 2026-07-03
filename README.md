# 量化投研管理系统

基于 daily_stock_analysis + AlphaSift + AlphaEvo 的统一管理仓库。

## 流水线流程（每日盘后）
1. **大盘复盘** → 生成当日盘面信号
2. **策略自动选择** → 根据信号选择最优策略
3. **AlphaSift 选股** → 使用选定策略生成候选池
4. **AlphaEvo 回测校验** → 计算止盈止损
5. **daily_stock_analysis 分析推送** → AI 报告 + 多渠道推送
6. **AlphaEvo 策略进化**（周五/月首）→ 轻量进化或全量重构

## 触发方式
- 自动：工作日北京时间 16:00
- 手动：Actions 页面点击 "Run workflow"

## 配置 Secrets
参考 [GitHub Secrets 清单](#) 配置所有密钥。