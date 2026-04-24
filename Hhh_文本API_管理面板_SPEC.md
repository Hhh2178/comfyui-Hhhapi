# Hhh 文本API 管理面板 SPEC

日期：2026-04-23

## 目标

把原来的“节点里手填 JSON”改成真正可操作的管理面板，完成文本服务商、模型、接口地址、密钥的可视化管理。

## 节点结构

当前只保留两个对外节点：

- `Hhh 文本API`
- `Hhh 文本API服务商管理`

其中：

- `Hhh 文本API` 只负责发起文本调用。
- `Hhh 文本API服务商管理` 负责打开管理面板和导出配置。

## 设计原则

1. 服务商敏感信息不出现在文本调用节点。
2. 用户日常使用时，只在文本节点中选择服务商和模型。
3. 服务商、模型、接口地址、密钥统一在面板中维护。
4. 服务商配置持久化到 `hhhapi_config.json`。
5. 密钥单独持久化到 `hhhapi_secrets.json`。

## 管理面板字段

### 服务商基础字段

- `服务商ID`
- `显示名称`
- `接口地址`
- `API密钥`
- `接口路径`

### 模型字段

- 模型名列表
- 支持新增模型
- 支持删除模型

## 交互流程

### 新建服务商

1. 打开管理面板
2. 点击 `新建服务商`
3. 填写服务商基础字段
4. 点击 `新增模型`
5. 至少添加一个模型
6. 点击 `保存`

### 编辑服务商

1. 在左侧选择已有服务商
2. 修改名称、地址、路径、模型
3. 如需改密钥，在 `API密钥` 中重新填写
4. 点击 `保存`

说明：

- 当 `API密钥` 留空时，不覆盖已保存密钥。
- 当 `API密钥` 有内容时，写入 secrets 文件。

### 删除服务商

1. 选择服务商
2. 点击 `删除服务商`
3. 确认删除

## 文本 API 节点行为

`Hhh 文本API` 从配置中心读取：

- 已启用服务商列表
- 当前服务商下的模型列表
- 所选服务商的基础地址
- 所选服务商的接口路径
- 所选服务商对应密钥

节点自身只保留这些业务参数：

- `服务商`
- `模型`
- `系统提示词`
- `用户提示词`
- `温度`
- `最大Token数`
- `随机种子`
- `响应格式`
- `超时秒数`
- `参考图片`

## 前端入口

管理面板前端入口有两个：

- ComfyUI 画布右键菜单：`Hhh 文本API服务商管理`
- 设置面板按钮：`Hhh 文本API服务商管理`

## 路由需求

标准后端路由：

- `GET /hhhapi/providers`
- `GET /hhhapi/providers/{provider_id}`
- `POST /hhhapi/providers`
- `DELETE /hhhapi/providers/{provider_id}`
- `POST /hhhapi/secrets/provider/{provider_id}`
- `GET /hhhapi/models`
- `GET /hhhapi/profiles`
- `GET /hhhapi/export`

当前 ComfyUI 运行环境的热加载代理只稳定代理 GET，因此前端面板实际优先使用：

- `GET /api/hhhapi/v1/providers`
- `GET /api/hhhapi/v1/provider?provider_id=...`
- `GET /api/hhhapi/v1/models?provider_id=...`
- `GET /api/hhhapi/v1/save_provider?data=...`
- `GET /api/hhhapi/v1/delete_provider_get?provider_id=...`
- `GET /api/hhhapi/v1/provider_secret_get?provider_id=...&api_key=...`
- `GET /api/hhhapi/v1/test_provider?provider_id=...&model=...&prompt=...`

说明：

- `v1` 兼容接口是为了绕过当前热加载环境中主路由半更新的问题。
- 后续如果恢复到稳定进程级加载，可以把保存和删除恢复为标准 POST/DELETE。

## 测试连接

管理面板提供 `测试连接` 按钮：

- 读取当前服务商 ID
- 读取模型列表中的第一个模型
- 从 `hhhapi_secrets.json` 获取服务商级 API Key
- 发起一次短文本请求
- 成功时显示模型返回的前 80 个字符
- 未保存 Key 时显示 `API密钥未保存`

## 数据约束

### 服务商 ID 规范

建议服务商 ID 使用 ASCII：

- 推荐：`aliyun_bailian`
- 推荐：`moonshot`
- 推荐：`openai_proxy`
- 不推荐：直接使用中文 ID

原因：

- URL 路径、路由参数、前端编码会更稳定
- 便于后续做引用、导入导出、版本迁移

### 模型名规范

- 模型名允许与平台原始模型名一致
- 保存时同时写入 `id` 和 `name`

## 当前环境结论

当前项目代码已经具备管理面板实现。ComfyUI 运行环境中的热加载插件存在不稳定现象：

- 日志出现 `dictionary changed size during iteration`
- 导致 Hhhapi 的 Python 路由会出现“部分热更新成功、部分仍是旧版本”的情况

已观察到的现象：

- `/hhhapi/export` 正常
- `/hhhapi/profiles` 正常
- `/hhhapi/providers` 曾返回 500
- `/hhhapi/providers/{provider_id}` 曾返回 404
- `/api/hhhapi/v1/providers` 正常
- `/api/hhhapi/v1/provider?provider_id=openai_compatible` 正常
- `/api/hhhapi/v1/save_provider?data=...` 正常
- `/api/hhhapi/v1/delete_provider_get?provider_id=...` 正常

这不是面板设计本身的问题，而是运行中的热加载状态不一致。

## 下一步建议

1. 当前先使用 `/api/hhhapi/v1` 兼容接口，保证刷新即可使用
2. 在空闲时做一次 ComfyUI 进程级重载，让标准路由整包重新注册
3. 补充导入/导出、批量模型编辑、测试按钮
