# 🦞 二级优化：1-1-5 素材赛马模型执行清单

> **目标**：实现一个 Campaign 下挂载 1 个 AdSet，并同时投出 5 个不重复视频素材的“赛马”模式，大幅提升测剧效率。

## 📋 任务列表

### Phase 1: 素材端升级 (Material Picker)
- [x] **[Task 1.1]** 修改 `video_selector.py`：实现不重复 5 视频随机采样逻辑。
- [x] **[Task 1.2]** 健壮性处理：处理目录视频少于 5 个的情况（有多少取多少）。
- [x] **[Task 1.3]** 返回结构优化：将单素材对象升级为素材列表对象。

### Phase 2: 投放核心重构 (Campaign Engine)
- [x] **[Task 2.1]** 修改 `campaign_manager.py`：重写 `create_campaign` 支持 `video_list` 传入。
- [x] **[Task 2.2]** 批量上传逻辑：实现视频、海报、AdCreative 的循环异步/顺序创建。
- [x] **[Task 2.3]** 命名规范升级：为每个 Ad 增加区分性索引后缀。

### Phase 3: UI/UX 适配 (Frontend)
- [ ] **[Task 3.1]** 修改 `app.py`：AI 助手支持展示 5 个待投视频的预览信息。
- [ ] **[Task 3.2]** 预览增强：看板预览窗口支持翻页或平铺展示系列下的全部 5 个广告。
- [ ] **[Task 3.3]** 确认流优化：确保点击“确认投流”后，系统能流畅反馈批量创建的进度。

### Phase 4: 调优逻辑进化 (Advanced Rules)
- [ ] **[Task 4.1]** 内部竞争逻辑：增加“末位淘汰”规则（如自动暂停 AdSet 内 CPI 最差的 Ad）。

---
*Created by Lobster AI Master · Phase 3 启动中*
