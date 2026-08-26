# 迭代 013：多 Provider 路由与 Git 连接诊断

> 日期：2026-08-27
> 类型：模型路由、凭据安全、网络故障定位
> 状态：已完成

## 1. 用户目标

用户确认可以使用付费 DeepSeek，新增 Agnes API key，并说明 Groq key 来自多个有权使用的独立账号；同时要求继续解决 Windows Git 到 GitHub 443 超时，且 WSL 可进入 `docker-desktop` 环境。

## 2. Provider 路由升级

Agnes 官方模型目录确认其接口兼容 OpenAI Chat Completions：

- Base URL：`https://apihub.agnes-ai.com/v1`；
- Agent/推理模型：`agnes-2.5-flash`；
- 免费/default 文本模型有独立 RPM 限额。

密钥加载器从“每个 Provider 一个 key”升级为“每个 Provider 一组去重 key”。本机实际解析为：

- Groq：10 个独立账号凭据；
- Agnes：1 个；
- NVIDIA：1 个；
- DeepSeek：1 个。

自动路由顺序为 Groq keys、Agnes、NVIDIA；只有 `allow_paid_fallback=true` 时追加 DeepSeek。本机 `.env` 根据用户授权打开付费回退，仓库 `.env.example` 仍默认关闭。

401/403 表示当前凭据不可用，429 表示当前限额不足，网络错误、空响应和选定 5xx 表示服务暂不可用；这些错误会继续下一配置。400 通常是请求代码或参数错误，立即失败，避免用换 Provider 掩盖缺陷。

## 3. 多 key 的工程边界

多个 Groq key 不做并发请求、后台预热或每次轮询。路由永远从第一配置开始，成功即停止，只在可重试失败时切换。配置者必须拥有所有账号的使用权；同一 organization 的多个 key 仍受组织级限额约束。

## 4. 真实 Provider 验收

所有探针只发送“仅返回 OK”，不包含简历、JD 或派生技能：

| Provider | 模型 | 结果 | 总 Token |
| --- | --- | --- | --- |
| Groq | `qwen/qwen3.6-27b` | 非空 | 77 |
| Agnes | `agnes-2.5-flash` | 非空 | 299 |
| DeepSeek | `deepseek-v4-flash` | 非空 | 119 |

NVIDIA 作为免费降级已通过 MockTransport 契约测试，本轮没有额外消耗真实额度。

官方依据：

- [Agnes 官方模型目录](https://github.com/AgnesAI-Labs/AgnesAI-Models/blob/main/MODEL_CATALOG.md)
- [Agnes OpenAI-compatible FAQ](https://github.com/AgnesAI-Labs/AgnesAI-Models/blob/main/docs/FAQ.md)
- [Groq rate limits](https://console.groq.com/docs/rate-limits)
- [DeepSeek models and pricing](https://api-docs.deepseek.com/quick_start/pricing)

## 5. GitHub 443 故障的分层定位

现象不是 Git 鉴权失败，而是 Windows Git/libcurl 连接 `github.com:443` 超时。诊断顺序：

1. 禁用仓库中失效的 `127.0.0.1:7897` 代理，仍超时；
2. WSL 默认发行版是 `docker-desktop`，只有 `sh`，不是 `bash`；
3. WSL Git 在发网前先要求私有仓库凭据，不能据此证明网络可达；
4. WSL Python 实际连接 GitHub IP 同样超时；
5. Windows 系统没有启用代理，也没有常见代理端口监听；
6. Windows Python/httpx 访问 `api.github.com` 和 `github.com` 均返回 200；
7. Git 切换 Schannel 到 OpenSSL 后仍超时，证明问题位于 Git/libcurl 的 TCP 路径。

最终使用 Windows Python 启动临时 HTTP CONNECT 转发，只允许目标 `github.com:443`。Windows Git 继续使用 OpenSSL 和原 Credential Manager，代理只转发 TLS 字节，不接触仓库凭据。推送后验证远端 SHA 与本地一致，随即停止并删除代理脚本，没有修改全局 Git 配置。

## 6. 工程总结

1. “WSL 能打开”不等于 WSL 的目标网络可达，必须实际探测目标端口。
2. 私有仓库的凭据失败可能发生在网络连接前，不能把错误阶段判断反了。
3. 当同机不同 HTTP 栈行为不同，应分别验证 DNS、TCP、TLS、认证和 Git 协议，而不是反复重试同一命令。
4. 临时网络绕行应最小权限、限制目标、验证后立即删除，不能为了推送长期关闭 TLS 或暴露通用代理。
