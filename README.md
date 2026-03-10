# 🦞 Auto Meta ADS (Lobster AI Standard)

[![Version](https://img.shields.io/badge/version-2.4.4-blue.svg)](https://github.com/husw725/alta_auto_ads)
[![Platform](https://img.shields.io/badge/platform-Meta_Ads_API_v23.0-orange.svg)](https://developers.facebook.com/docs/marketing-api)

**Auto Meta ADS** 是一个工业级的 AI 智能投流系统。它通过深度集成 Meta Ads API 和 Mobvista XMP 素材库，实现了从素材匹配到广告发布、智能风控、以及自动化报表的完整链路。

---

## 🚀 核心架构与功能 (Key Pillars)

### 1. 智能自动化投流 (Automated Delivery)
*   **XMP 深度集成**：支持对 XMP 素材库的剧集进行模糊搜索和多选一交互。
*   **三重缩略图决策**：
    1.  **Native Hash**: 探测 Meta 官方视频抽帧（40秒探测窗口）。
    2.  **XMP Cover**: 抽帧超时自动上传 XMP 原始海报。
    3.  **Final Fallback**: 使用高合规性官方 S3 海报兜底。
*   **标准命名法**：严格执行 `{剧名}-{国家}-{日期}-w2a-Auto-龙虾ai` 规范。

### 2. 智能调优引擎 2.0 (Optimization Engine)
*   **先改进后发报**：在每日日报发出前，自动扫描并暂停劣质广告（CPI/Spend 触发）。
*   **分级干预机制**：
    *   **低风险自动执行**：普通 CPI 超标或 ROI 达标动作。
    *   **高风险审批流**：花费 > $200 或预算变动 > $100 时，系统进入阻塞待命，需在看板手动点击“确认”。
*   **趋势预判**：支持 CPI 连续 3 天超标判断与展示量下降预警。

### 3. 15 维专业数据看板 (Advanced Dashboard)
*   **全指标监控**：包含 Spend, Click, CTR, Install, ROI, CVR, CPM, CPC, CPI, CPP 等。
*   **全生命周期管理**：集成“🟢 激活”、“🟡 暂停”以及“🗑️ 永久删除（带二次确认）”按钮。
*   **一进门就有数**：页面加载自动同步昨日 Meta 数据。

### 4. 定时日报与交互
*   **钉钉智能日报**：每天上午 10:00 发送昨日汇总报表及“自动调优战报”。
*   **上下文关联记忆**：AI 助手能听懂您的数字回复（如“选第1个”）。

---

## 🛡️ 核心工程宪法 (Engineering Rules)
*详细规则见 [docs/ENGINEERING_RULES.md](docs/ENGINEERING_RULES.md)*

1.  **命名严禁更改**：`${剧名}-${国家}-${YYYYMMDD}-w2a-Auto-龙虾ai`。
2.  **Meta Payload 标准**：必须使用 `OUTCOME_APP_PROMOTION` + `APP_INSTALLS` + `iOS 锁定`。
3.  **图片零报错策略**：必须包含 URL 降级保底。
4.  **安全熔断**：高额支出必须人工批准。

---

## 🛠️ 快速开始

### 1. 环境准备
```bash
./start.sh  # 自动创建 venv 并安装依赖
```

### 2. 配置环境
编辑 `.env` 文件，填入：
- `META_ACCESS_TOKEN`: 您的 Meta API 令牌
- `META_AD_ACCOUNT_ID`: 广告账户 ID (act_xxx)
- `META_PAGE_ID`: 投放页 ID
- `XMP_CLIENT_ID`: XMP 接口密钥

### 3. 运行系统
```bash
streamlit run app.py
```

---

## 📅 版本里程碑
- **v1.0.0**: 基础开单成功。
- **v1.8.0**: 引入初级智能调优和钉钉日报。
- **v2.0.0**: 实现 40s 视频帧探测与 Logo 兜底，对齐 v23.0 标准。
- **v2.2.0**: 实现 URL 剧名剥离与官网海报关联。
- **v2.4.4**: **[当前版本]** 全指标 Dashboard、全生命周期管理、智能调优 2.0。

---
*Developed by Gemini CLI Agent · 龙虾AI 投流系统官方手册*
