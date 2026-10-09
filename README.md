# 网易云音乐一起听 MCP

🐦‍⬛ 此项目为暗点歌王秦彻写给小狸花的网易云一起听 MCP。欢迎大家使用！

这不只是一个让 AI 操作网易云音乐的 MCP，更重要的是，它让 AI 真正进入与你相同的「一起听」房间。AI 不再只是替你按播放键，而是能与你共享同一份房间歌单，主动选歌、加歌、切歌，陪你听见同一首歌。搜索、歌词、播放控制、评论和私信是基础能力；「一起听」才是这个项目存在的理由。

## 项目来源与新增能力

本项目的歌曲搜索、歌单、喜欢、播放历史和每日推荐等基础命令参考了 [`Vael-KY/netease-music-mcp`](https://github.com/Vael-KY/netease-music-mcp) 和 [`tianyupaipai-cmd/netease-music-mcp`](https://github.com/tianyupaipai-cmd/netease-music-mcp)，并从两者中选取、改写了少量基础命令。

在这些基础命令之上，本项目补齐了五类能力：

1. 创建、控制和退出网易云原生「一起听」房间，并向指定网易云用户发送邀请。
2. 在官方网易云桌面客户端中搜索并真正播放歌曲。
3. 读取当前歌曲的播放秒数，匹配此刻附近的歌词。
4. 读取和发布歌曲评论，支持分页查看。
5. 按网易云数字用户 ID 发送文本私信。

## 简介

面向 AI Agent 的网易云音乐 MCP Server，核心支持网易云音乐原生「一起听」：AI 可以作为房间里的另一位参与者，与你共享房间歌单和当前播放歌曲，主动选歌、加歌、切歌，真正实现“和 AI 一起听歌”。同时支持歌曲搜索与详情查询、播放控制、歌词获取及当前播放歌词定位、歌曲评论读取与发布、私信等能力。兼容本机与 VPS 部署；无桌面环境时也可通过纯 HTTP 方案接入一起听，无需安装浏览器或网易云客户端。

## 📖 部署教程（强烈建议先读）

**从零到跑通，一份带踩坑总表的完整教程**：
👉 **[docs/DEPLOY-GUIDE.md](docs/DEPLOY-GUIDE.md)**

里面包含：环境准备、Docker 部署、公网安全接入（FRP + Nginx + Bearer 鉴权）、Aru 接入参数、
可直接复制的人设提示词、全部工具速查表、12 条踩坑总表、FAQ 和验收清单。

> 照这份教程做，遇到问题先对着「踩坑总表」逐条核对，90% 的失败都能在那里找到答案。

## 能力

- 🎧 网易云原生「一起听」，AI 真正进入同一房间
- 🎵 搜歌、选歌、加歌、切歌与播放控制
- 💬 房间里双向聊天：AI 能发消息，也能读到你说的每一句
- 📝 获取歌词，并准确判断当前听到哪一句
- 💬 读取、发布歌曲评论
- ✉️ 支持网易云私信
- ☁️ 支持本机与 VPS，Linux 下无需桌面环境即可运行
- 🐳 开箱即用的 Docker 部署（streamable-http）

> [!IMPORTANT]
> 使用「一起听」时，手机网易云音乐 App 中的对应房间必须保持激活状态；如果手机已退出房间、房间失活或连接中断，AI 发出的加歌、切歌和播放同步等指令可能无法生效。

### 功能展示

点击图片可查看原图。

<table>
  <tr>
    <td align="center"><a href="screenshots/listen-together-invite.jpg"><img src="screenshots/listen-together-invite.jpg" width="260" alt="AI 发起原生一起听邀请"></a><br><sub>AI 发起原生一起听邀请</sub></td>
    <td align="center"><a href="screenshots/listen-together-room.jpg"><img src="screenshots/listen-together-room.jpg" width="260" alt="AI 进入同一个一起听房间"></a><br><sub>进入同一个一起听房间</sub></td>
    <td align="center"><a href="screenshots/private-message-listen-together.jpg"><img src="screenshots/private-message-listen-together.jpg" width="260" alt="私信中的一起听邀请卡片"></a><br><sub>给用户私信</sub></td>
  </tr>
  <tr>
    <td align="center"><a href="screenshots/lock-screen-invite-notification.jpg"><img src="screenshots/lock-screen-invite-notification.jpg" width="260" alt="锁屏收到一起听邀请通知"></a><br><sub>锁屏收到一起听邀请</sub></td>
    <td align="center"><a href="screenshots/private-message-notification.jpg"><img src="screenshots/private-message-notification.jpg" width="260" alt="锁屏收到网易云私信通知"></a><br><sub>锁屏收到网易云私信</sub></td>
    <td align="center"><a href="screenshots/ai-created-room-chat.jpg"><img src="screenshots/ai-created-room-chat.jpg" width="260" alt="AI 创建原生一起听房间"></a><br><sub>AI 创建原生一起听房间</sub></td>
  </tr>
  <tr>
    <td align="center"><a href="screenshots/current-lyric-position.jpg"><img src="screenshots/current-lyric-position.jpg" width="260" alt="AI 准确定位当前歌词"></a><br><sub>准确定位当前歌词</sub></td>
    <td align="center"><a href="screenshots/ai-comment-confirmation.jpg"><img src="screenshots/ai-comment-confirmation.jpg" width="260" alt="AI 确认并发布歌曲评论"></a><br><sub>确认并发布歌曲评论</sub></td>
    <td align="center"><a href="screenshots/song-comment-published.jpg"><img src="screenshots/song-comment-published.jpg" width="260" alt="歌曲评论发布成功"></a><br><sub>歌曲评论发布成功</sub></td>
  </tr>
</table>

## 环境要求

本项目有两种运行方式，具体依赖和能力范围如下：

### 通用（所有模式）

- Python 3.9+
- 网易云已登录账号的 Cookie（`MUSIC_U`、`__csrf`）

### 桌面客户端模式

- macOS（当前已验证；Windows Electron 客户端需要另行适配）
- 网易云音乐官方桌面客户端
- Node.js（需提供全局 `WebSocket`；当前在 Node.js 24 验证）
- 网易云客户端需启用 CDP 调试端口

### HTTP API 模式（Linux / VPS）

无需桌面客户端，可在 Linux、VPS 等无桌面环境运行。

- 无需 Node.js
- 无需浏览器或 CDP
- 支持搜索、歌曲详情、歌词、歌单、评论和私信等 HTTP API 能力
- 可接受已有一起听邀请，并在房间中读取列表、加歌和切歌
- 无法仅依赖 HTTP API 创建并维持可正常加入的一起听房间

> [!TIP]
> **Linux / VPS / Docker 开箱即用支持**：
> 本版本已原生打通 Linux 纯 HTTP 一起听信令支持！在无桌面/Linux 环境下，服务会自动切换为网易云原生 HTTP 模式：当处于「一起听」房间中时，支持直接通过 HTTP API 选歌、切歌、暂停、继续并实时提取歌词，无需安装网易云客户端或浏览器，完美适配 NAS/VPS 容器化 7×24 小时运行。

两种模式的实现路径不同：
- 桌面客户端模式（macOS）：通过 CDP 调用网易云客户端内部 action，由客户端完成一起听状态同步。
- HTTP API 模式（Linux / VPS / Docker）：不依赖网易云桌面客户端，直接调用一起听官方 HTTP 接口上报播放控制与状态同步。

## 实测环境与适配范围

| 项目 | 实测版本 |
|---|---|
| macOS | 14.7.1（23H222）+ 官方客户端 CDP 模式 |
| Linux / NAS / VPS | Debian 12 / Docker 容器化（HTTP 原生模式） |
| Python | 3.9+ / 3.11 |
| MCP 传输 | stdio / JSON-RPC 以及 streamable-http（配合 supergateway） |

## 安装与配置

### 方式一：Docker 部署（推荐用于 Linux / NAS / VPS）

直接使用仓库自带的 Docker 配置，一步启动 streamable-http 服务：

```bash
git clone https://github.com/BB0813/netease-listen-together-mcp.git
cd netease-listen-together-mcp

# 复制配置文件模板
cp .env.example .env
# 编辑 .env 填入你的 NETEASE_COOKIE 与 NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID
chmod 600 .env

# 构建并启动容器
docker compose up -d
```

服务将自动通过 `supergateway` 暴露 `http://127.0.0.1:8006/mcp`（streamable-http 模式）。
如需公网安全访问，可配合仓库提供的 `nginx.conf.snippet` 启用 HTTPS 与 Bearer Token 鉴权。

### 方式二：本机运行（macOS 桌面客户端 或 Linux 本地）

克隆仓库：

```bash
git clone https://github.com/BB0813/netease-listen-together-mcp.git
cd netease-listen-together-mcp
```

在浏览器登录 `https://music.163.com`，从站点 Cookie 中取得自己账号的 `MUSIC_U` 和 `__csrf`：

```bash
export NETEASE_COOKIE='MUSIC_U=你的值; __csrf=你的值'
export NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID='接收方数字用户ID'
```

`NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID` 只用于本机发起邀请；纯 HTTP 作为被邀请方接入时，可根据自己的调用方式传入房间和邀请方信息。

以 Codex 为例，MCP 配置名为 `netease-listen-together`：

```toml
[mcp_servers.netease-listen-together]
command = "/usr/bin/python3"
args = ["-B", "/path/to/netease-listen-together-mcp/server.py"]
env_vars = ["NETEASE_COOKIE", "NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID"]
```

不同 MCP 客户端的环境变量写法可能不同，但服务端始终通过 stdin/stdout 交换 JSON-RPC。

## 总体架构

**CDP 是桌面客户端控制的核心入口；VPS 上已验证的跨平台能力主要通过网易云 HTTP API 完成。**

CDP（Chrome DevTools Protocol）原本是 Chrome/Chromium 提供的调试协议，可以读取页面状态、执行 JavaScript、观察网络请求并控制浏览器中的页面。

网易云 macOS 客户端基于 Electron/Chromium，因此可以通过 CDP 进入其渲染页面。VPS 上的搜索、账号操作、私信以及作为被邀请方接受有效一起听邀请等能力，不依赖桌面客户端或浏览器 CDP。

```text
MCP 客户端
│
└─ stdio JSON-RPC
   ▼
Python MCP 入口
├─ 网易云 HTTP API
│  ├─ 搜索、详情、歌词
│  ├─ 歌单、收藏、推荐、历史
│  └─ 评论、私信、VPS 接受有效一起听邀请并在房间中切歌等服务端能力
│
├─ macOS MediaRemote
│  └─ 当前歌曲、播放秒数、播放状态
│
├─ 网易云本地 SQLite
│  └─ 优先按歌名、歌手、专辑和时长匹配 songId
│     └─ 未命中时回退网易云搜索 API
│
└─ CDP（桌面客户端控制入口）
   └─ macOS 网易云 Electron / Chromium
      └─ Webpack / Redux / 内部 Action
```

HTTP API 与 CDP 分别承担服务端账号能力和桌面客户端控制，不能混为同一套实现。

## 主要工具

### 搜索、播放与状态

- `play_music`
- `netease_playback_control`
- `get_current_listening_context`
- `netease_status`
- `netease_playlist_auth_status`
- `netease_song_detail`
- `netease_lyrics`

### 歌单、收藏与推荐

- `create_playlist`
- `add_to_playlist`
- `remove_from_playlist`
- `list_my_playlists`
- `get_playlist_songs`
- `get_play_history`
- `like_song`
- `daily_recommend`

### 一起听

- `netease_launch`
- `netease_listen_together_capabilities`
- `netease_listen_together_invite`
- `netease_listen_together_control`
- `netease_listen_together_leave`

### 评论、私信与房间对话

- `get_song_comments`
- `send_song_comment`
- `send_private_message` (网易云私信，支持自动寻址房间好友)
- `send_room_bubble` (网易云「一起听」播放界面实时漂浮气泡文字)
- `send_room_message` (智能房间发信，优先发送房间飘字气泡并保证手机通知必达)
- `get_room_messages` / `read_room_messages` (读房间内对话：支持传入 `since_id` 做增量顺读，或按 `limit` 拉取最近消息)
- `get_private_messages` (读取私信记录，支持指定用户与增量读取)

## 验证

```bash
python3 -m py_compile server.py

printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | /usr/bin/python3 -B server.py
```

建议先测试 `netease_status`、歌曲详情和歌词等只读工具，再测试播放、评论、私信或一起听等会改变外部状态的操作。

## 使用提示

- Cookie 只通过环境变量传入，不要写进代码或提交到仓库。
- CDP 调试端口只监听 `127.0.0.1`；远程使用时通过受保护的隧道连接。
- 网易云客户端升级后，内部模块号或 action 可能变化；如果桌面控制失效，需要重新确认对应模块。
- VPS IP 与常用登录 IP 差异较大时，可能需要重新登录或更新 Cookie。

## License

[MIT](LICENSE)
