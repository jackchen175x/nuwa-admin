# nuwa-admin

女娲管理后台，用于查看服务状态、测试老师回复、编辑人格文件、跑标准考卷和管理用户记忆。

## 页面

- 总览：服务状态、老师配置、人格文件仓库同步状态
- 搭建调试：按老师、模型、温度测试真实回复，并查看本轮追踪信息
- 人格工坊：在线编辑 `SKILL.md`，保存后热更新，并可提交推送到 `nuwa-skills`
- 观测中心：查看调用量、成功率、延迟、错误和最近请求
- 质量评测：跑单题、批量跑分、查看历史结果
- 用户记忆：查询和清理指定用户的画像记忆
- 发布中心：沉淀 API、AB 灰度、验收清单和回滚信息

## 启动

```bash
uv sync
NUWA_RUNTIME_URL=https://api.nuwa.aizd.org \
NUWA_ADMIN_TOKEN=你的管理密钥 \
uv run streamlit run streamlit_app.py
```

默认服务地址是 `http://localhost:8000`，也可以在左侧栏临时修改。
