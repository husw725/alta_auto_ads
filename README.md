# Auto Meta ADS Skill - 自动投流系统

🚀 **基于 Mobvista XMP 的 Meta 广告自动投流解决方案**

---

## 📖 简介

这是一个完整的自动投流系统，用于：
1. 从 Mobvista XMP 中自动查找剧集素材
2. 根据需求智能选择视频
3. 通过 Meta Ads API 自动创建广告 Campaign
4. 支持自然语言指令

---

## 📁 目录结构

```
skills/auto-meta-ads-skill/
├── README.md                    # 本文件
├── app.py                       # Streamlit Web 界面 ⭐
├── config/
│   └── config.json              # 配置文件
├── core/
│   ├── campaign_manager.py      # Campaign 创建器
│   ├── video_selector.py        # 视频选择器
│   └── copywriter.py            # 文案生成器
├── utils/
│   ├── natural_language_parser.py  # 自然语言解析
│   └── video_link_validator.py   # 视频链接验证
├── tests/
│   ├── test_campaign.py         # Campaign 测试
│   └── test_selector.py         # 选择器测试
├── auto_select.py               # 主程序（现有）
├── check_video_link.py          # 视频链接验证（现有）
├── find_video.py                # 视频查找（现有）
├── select_option1.py            # 选项选择（现有）
├── test_complex.py              # 综合测试（现有）
└── list_dramas.py               # 列表剧集（现有）
```

---

## 🚀 快速开始

### 方式 0: Streamlit Web 界面 ⭐ 推荐

启动 Web 界面：

```bash
cd skills/auto-meta-ads-skill
streamlit run app.py
```

访问：`http://localhost:8501`

**功能**：
- 💬 对话式交互
- 📹 视频选择
- 🚀 Campaign 创建（可选）
- ⚙️ 侧边栏配置

### 方式 1: 命令行直接调用

```bash
# 自动选择视频
python auto_select.py

# 验证视频链接
python check_video_link.py

# 列出所有剧集
python list_dramas.py
```

### 方式 2: Python 脚本

```python
from auto_select import AutoMetaADS

auto_ads = AutoMetaADS()

# 处理用户请求
success, result = auto_ads.process_request(
    "我要投 FFAS-新版到美国地区",
    enable_campaign=True
)

if success:
    print(f"✅ 视频链接：{result['video_link']}")
    print(f"📁 剧集：{result['drama']}")
    print(f"🗣️ 语言：{result['language']}")
```

---

## 🎯 核心功能

### 1. 视频自动选择

从 XMP 中智能查找视频：

**选择逻辑**：
- 精确匹配剧集名 → 模糊匹配 → 语义匹配
- 查找语言文件夹（英语/日语/德语等）
- 查找设计师文件夹或随机选择
- 查找最近日期文件夹或随机选择
- 返回真实视频链接（file_url）

### 2. Campaign 创建

自动创建完整的 Meta Ads Campaign：

**创建的组件**：
1. 上传视频 → 获取 video_id
2. 抓取封面图 → 获取 thumbnail
3. 创建 Campaign → campaign_id
4. 创建 AdSet → adset_id
5. 生成文案 → 多个创意版本
6. 创建 Ad → ad_id
7. 获取预览链接 → 预览效果

### 3. 自然语言解析

支持自然语言指令：

**支持的指令格式**：
- `我要投 [剧名] 到 [地区]`
- `[剧名] 的 [语言] 视频`
- `[剧名] 设计师 [设计师名]`
- `[剧名] 今天/最近`

### 4. 文案生成

自动生成多版本广告文案：
- Primary Text（正文）
- Headline（标题）
- Angle（角度/创意方向）
- Multiple Variants（多版本）

---

## ⚙️ 安装与配置

### 1. 环境要求

```bash
Python 3.8+
pip install streamlit requests python-dotenv
```

### 2. 配置文件

配置文件位于 `config/config.json`，已包含：
- Meta Ads API 配置（Access Token、Ad Account 等）
- XMP API 配置（Client ID、Client Secret）
- 默认参数（预算、CPI、国家）

---

## 📊 工作流程

```
用户指令 → 自然语言解析 → 剧集匹配
    ↓
语言文件夹查找 → 设计师/视频选择
    ↓
视频链接获取 → (可选)Campaign 创建
    ↓
预览链接生成 → 返回结果
```

### 详细步骤

1. **解析用户指令**
   - 提取剧名、地区、语言、设计师、日期
   - 地区→语言自动映射

2. **查找剧集**
   - 精确匹配 → 模糊匹配 → 语义匹配
   - 处理多个匹配结果

3. **查找语言文件夹**
   - 在剧集中查找指定语言
   - 失败则提示可用语言列表

4. **选择视频/设计师**
   - 优先选择：指定日期 → 设计师目录 → 随机选择
   - 语言目录下直接有视频则直接使用

5. **获取视频链接**
   - 从 XMP 获取真实 file_url
   - 验证链接可用性

6. **创建 Campaign（可选）**
   - 上传视频 → 获取封面
   - 创建 Campaign → AdSet → Ad
   - 生成多版本文案
   - 获取预览链接

---

## 🧪 测试

### 运行测试用例

```bash
# 测试基础功能
python tests/test_selector.py

# 测试 Campaign 创建
python tests/test_campaign.py

# 综合测试
python test_complex.py
```

### 测试数据

```python
test_inputs = [
    "我要投 the CEO and the country girl 到美国",
    "我要投 FFAS 这部剧 到美国地区",
    "我要投卸甲后我名动京城这部剧",
    "卸甲后我名动京城的德语视频",
]
```

---

## 🔧 常见问题

### Q: 视频链接获取失败？

**A**: 检查 XMP 下载器是否正确获取 `file_url` 字段，可能需要调整字段映射。

### Q: Campaign 创建失败？

**A**: 
- 检查 API 权限是否足够
- 确认 Ad Account 和 Pixel 配置正确
- 验证 Access Token 未过期

### Q: 自然语言解析不准确？

**A**: 
- 确保剧名在 XMP 中存在
- 使用更明确的指令格式
- 检查地区 - 语言映射表

---

## 📝 日志与调试

### 日志级别

```python
# 基础日志
print("=" * 60)
print("🤖 处理用户请求")
print("=" * 60)

# 详细步骤日志
print(f"📁 Step 2: 查找语言文件夹 '{target_lang}'")
print(f"✅ 选中语言：{parsed['language']} (ID: {lang_folder_id})")
```

### 调试模式

```python
# 启用详细日志
auto_ads.enable_debug()

# 查看完整请求日志
print(result['logs'])
```

---

## 🔄 版本更新

### v1.0 (当前版本)
- ✅ 基础视频选择功能
- ✅ Campaign 自动创建
- ✅ 自然语言解析
- ✅ 文案生成
- ✅ 预览链接获取
- ✅ Streamlit Web 界面

### 计划更新
- 🔜 A/B 测试自动轮询
- 🔜 效果数据自动分析
- 🔜 多账号支持
- 🔜 效果数据可视化

---

## 👥 贡献指南

欢迎提交 PR！主要修改点：
1. 新增地区/语言映射
2. 优化选择算法
3. 增加测试用例
4. 文档完善

---

## 📄 许可证

本项目仅供内部使用，未经许可不得外传。

---

*最后更新：2026-03-10*