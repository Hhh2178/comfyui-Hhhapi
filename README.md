# Hhhapi

通用 ComfyUI 文本 API 节点包，当前阶段专注文本模型：

- OpenAI Chat Completions 兼容文本模型
- 供应商和模型配置持久化
- 供应商级 API Key 保存与前端掩码
- 服务商、接口地址、模型的新增、修改、删除
- 独立前端管理面板
- MiniMax 图片理解通道
- 思考链独立输出
- 繁忙错误自动重试（最多 3 次）

仓库地址：

- [GitHub](https://github.com/Hhh2178/comfyui-Hhhapi)

## 节点

- `Hhh 文本API`
- `Hhh 文本API服务商管理`

## 安装

### 方式 1：手动安装

将仓库克隆到 ComfyUI 的 `custom_nodes` 目录：

```bash
git clone https://github.com/Hhh2178/comfyui-Hhhapi.git
```

如果你的 ComfyUI Python 环境没有安装依赖，再执行：

```bash
pip install -r requirements.txt
```

### 方式 2：通过 ComfyUI Manager

当前仓库已经补齐面向 Registry/Manager 的元信息。  
如果后续提交到 ComfyUI Manager 列表或发布到 Comfy Registry，就可以直接在 Manager 中检索安装。

## 基础使用

1. 刷新 ComfyUI 前端。
2. 在画布右键菜单中打开 `Hhh 文本API服务商管理`。
3. 新建服务商，填写服务商 ID、显示名称、接口地址、接口路径、API 密钥。
4. 在面板中新增一个或多个模型并保存。
5. 添加 `Hhh 文本API`。
6. 在节点顶部选择 `服务商` 和 `模型`。
7. 填写 `系统提示词` 和 `用户提示词`。
8. 运行工作流，读取 `文本` 输出。

`Hhh 文本API` 不显示 API 密钥和接口地址；这些只在 `Hhh 文本API服务商管理` 中维护。

## Hhh 文本API参数

| 参数 | 说明 |
| --- | --- |
| `服务商` | 从服务商管理配置中选择，例如 `openai_compatible`、`deepseek`。 |
| `模型` | 当前服务商下可用的文本模型。 |
| `系统提示词` | system prompt，用来定义角色和规则。 |
| `用户提示词` | user prompt，实际要发送的问题或任务。 |
| `温度` | 控制随机性。越低越稳定，越高越发散。 |
| `最大Token数` | 最大输出 token 数。 |
| `随机种子` | 支持 seed 的服务商会使用；`-1` 表示不传。 |
| `响应格式` | `文本` 或 `JSON对象`。JSON 对象需要模型和服务商支持。 |
| `超时秒数` | API 请求超时时间。 |
| `参考图片` | 可选。给支持视觉输入的文本模型使用。 |

输出：

| 输出 | 说明 |
| --- | --- |
| `文本` | 模型返回的主要文本。 |
| `响应JSON` | 归一化响应和原始响应。 |
| `用量JSON` | token 用量，如果服务商返回 usage。 |
| `思考链` | 模型的 reasoning / think 内容。没有思考链时为空字符串。 |

节点右上角会显示当前实际调用通道：

- `文本通道`
- `视觉文本通道`
- `MiniMax识图通道`

## Hhh 文本API服务商管理

推荐使用真正的管理面板，不再通过节点手填 JSON。

打开方式：

- 在 ComfyUI 画布右键菜单中选择 `Hhh 文本API服务商管理`
- 或在设置里点击 `Hhh 文本API服务商管理`

管理面板支持：

- 新建服务商
- 修改服务商名称
- 修改接口地址
- 修改接口路径
- 保存 API 密钥
- 测试连接
- 新增/删除模型
- 删除服务商

模型能力配置支持：

- `视觉`
- `JSON`
- `思考链`
- `MiniMax识图`

密钥只会保存到 `hhhapi_secrets.json`，不会写入 `hhhapi_config.json`。

建议：

- `服务商ID` 使用英文 ID，例如 `aliyun_bailian`、`moonshot`、`openai_proxy`。
- `显示名称` 再使用中文，例如 `阿里云百炼`、`月之暗面`。
- `接口地址` 只填基础地址，例如 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
- `接口路径` 默认用 `/chat/completions`，只有供应商协议不同才改。

## 当前运行方式

- 管理面板当前优先使用 `/api/hhhapi/panel/...` 独立接口，避开部分热更新环境下旧路由残留的问题。
- 文本节点前端仍使用 `/api/hhhapi/v1/...` 获取服务商和模型列表。
- `测试连接` 会使用已保存的 API 密钥，对选中服务商和第一个模型发起一次短文本请求。

## MiniMax 图片理解

MiniMax 接入时分成两类：

- 不接图片：走普通文本聊天通道
- 接入图片且模型能力包含 `MiniMax识图`：自动切换到 MiniMax 官方图片理解通道

这样可以避免把 MiniMax 的图片理解错误地塞进普通 OpenAI 兼容图片输入协议。

如果遇到下列繁忙类错误，节点会自动重试，最多 3 次：

- `429`
- `529`
- `rate limit`
- `服务繁忙`
- `访问繁忙`
- `稍后重试`

## 当前已知问题

- 你当前这台 ComfyUI 的 `comfyui_lg_hotreload` 插件正在高频热更新很多节点，并在日志中出现 `dictionary changed size during iteration`。
- 这会导致 `Hhhapi` 的 Python 路由偶尔只热加载一部分，出现前端 JS 已更新、但 `/hhhapi/providers` 和 `/hhhapi/models` 仍然跑旧逻辑的情况。
- 已通过独立面板接口和兼容接口组合方式绕过这个问题。
- 如果个别旧节点仍表现异常，通常刷新前端并重新创建节点即可恢复。

## 当前设计原则

- `Hhh 文本API` 只负责调用文本模型，不暴露接口地址和 API 密钥。
- `Hhh 文本API服务商管理` 负责服务商、模型、接口地址和 API 密钥的维护。
- 文本 API 节点运行时会根据所选服务商和模型，从配置文件读取接口地址，从密钥文件读取 API Key。
- 图像模型后续按平台做专用节点，不放进当前通用文本 API 节点。

## 配置文件

首次加载会自动生成：

- `hhhapi_config.json`
- `hhhapi_secrets.json`

`hhhapi_config.json` 存储供应商、模型、profile。  
`hhhapi_secrets.json` 存储 API Key，不建议提交或分享。
