# 网易云音乐一起听 MCP

通过 MCP 控制网易云音乐 macOS 官方客户端，并提供歌曲搜索、播放、歌词、歌单、评论、私信和原生“一起听”房间能力。

> 本项目使用网易云音乐未公开的 HTTP API、Electron/CDP 接口和客户端内部模块，可能随客户端升级失效。请仅操作自己的账号，并自行承担账号风控风险。

## 能力

- 搜索并在官方客户端播放歌曲，控制播放、暂停、上一首和下一首。
- 读取当前歌曲、附近歌词、歌曲详情和评论。
- 管理歌单、喜欢、播放历史和每日推荐。
- 发布评论、发送文本私信。
- 在 macOS 官方客户端创建原生一起听房间、发送邀请、同步播放命令并退出房间。

## 运行边界

- **macOS 发起方**：需要网易云音乐官方客户端、CDP 和客户端内部 IM/RTC 会话。
- **纯 HTTP / VPS**：搜索、歌词、歌单、评论和私信等功能可跨平台使用；一起听目前只能接受一个已经有效的邀请，不能仅靠 REST API 创建可加入的房间。
- CDP 几乎可以完整控制客户端，远程调试端口必须只监听 `127.0.0.1`，不要暴露到公网。

## 环境要求

- macOS（一起听发起与桌面播放功能）
- 网易云音乐 macOS 官方客户端；当前实现实测版本为 `3.1.8.3368`
- Python 3.9+
- Node.js 22+（用于 CDP WebSocket 调用）
- 两个网易云账号：发起账号和接收邀请账号

Python 部分仅使用标准库：

```bash
python3 -m pip install -r requirements.txt
```

## 配置

在浏览器登录 `https://music.163.com`，从站点 Cookie 中取得自己的 `MUSIC_U` 和 `__csrf`：

```bash
export NETEASE_COOKIE='MUSIC_U=你的值; __csrf=你的值'
export NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID='接收方数字用户ID'
```

不要把 Cookie、用户 ID、日志或本地数据库提交到仓库。`MUSIC_U` 泄漏等同于登录会话泄漏。

Codex MCP 配置示例见 [`examples/codex-config.toml`](examples/codex-config.toml)，配置名为 `netease-listen-together`：

```toml
[mcp_servers.netease-listen-together]
command = "/usr/bin/python3"
args = ["-B", "/path/to/netease-listen-together-mcp/server.py"]
env_vars = ["NETEASE_COOKIE", "NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID"]
```

## 工作原理

```text
MCP 客户端
  └─ stdio JSON-RPC
      ├─ 网易云 HTTP API：账号、歌曲、歌词、歌单、评论和私信
      ├─ macOS MediaRemote / 本地 SQLite：当前播放信息与 songId 匹配
      └─ CDP → 网易云 Electron → Webpack/Redux/IM/RTC：播放和一起听
```

一起听发起流程：

```text
检查当前歌曲和房间状态
→ 必要时清理失效旧房间
→ 通过 CDP dispatch startListenTogether
→ 等待 roomInfo、waiting 状态和客户端 heartbeat
→ 调用邀请接口
→ 房间命令经官方客户端同步给另一端
```

单独调用 `room/create`、HTTP heartbeat 和邀请接口可能全部返回 `200`，但房间仍处于 `NOT_CONNECTED`，接收方无法加入；真实房间还需要官方客户端的 IM/RTC 实时连接。

## 运行与验证

```bash
python3 -m py_compile server.py
python3 -m unittest -v

printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | /usr/bin/python3 -B server.py
```

建议先调用只读工具 `netease_status`，再测试歌曲详情和歌词，最后测试播放、评论或一起听等有副作用的操作。

## 安全说明

- 所有凭据仅通过环境变量注入；仓库不提供默认账号、接收 UID 或房间号。
- 评论、私信、歌单修改和邀请均属于外部写操作，应在用户明确授权后调用。
- 客户端升级后，Webpack 模块号和内部 action 可能变化，需要重新验证。
- VPS IP 与常用登录 IP 差异较大时，可能触发登录失效或风控。

## Credits

- 一起听、桌面播放、当前歌词与评论实现：秦彻
- 基础命令参考：[`Vael-KY/netease-music-mcp`](https://github.com/Vael-KY/netease-music-mcp)、[`tianyupaipai-cmd/netease-music-mcp`](https://github.com/tianyupaipai-cmd/netease-music-mcp)
