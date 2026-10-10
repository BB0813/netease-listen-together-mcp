# 网易云音乐一起听 MCP

这不只是一个让 AI 操作网易云音乐的 MCP，更重要的是，它让 AI 真正进入与你相同的「一起听」房间。AI 不再只是替你按播放键，而是能与你共享同一份房间歌单，主动选歌、加歌、切歌，陪你听见同一首歌。搜索、歌词、播放控制、评论和私信是基础能力；「一起听」才是这个项目存在的理由。

（已在HTTP API内写出大部分官方一起听链路的调用接口 实测正常）

---

## 📖 完整部署教程（强烈建议先读）

**从零到跑通，一份带踩坑总表与实机验证的完整图文教程**：  
👉 **[docs/DEPLOY-GUIDE.md](docs/DEPLOY-GUIDE.md)**  
*(备用 Word 版本可从 release 或本地提取：`网易云一起听MCP-从零到门铃-完整教程.docx`)*

教程内包含：环境准备、Docker 部署、公网安全接入（FRP + Nginx + Bearer 鉴权）、Aru 接入参数、可直接复制的人设提示词、全部工具速查表、12 条实踩血泪避坑总表、FAQ 和 12 项交付验收清单。遇到问题先对照教程的「踩坑总表」核对，90% 的失败都能在那里找到答案。

---

## 简介

面向 AI Agent 的全功能网易云音乐 MCP Server，核心支持网易云音乐原生「一起听」：AI 可以作为房间里的另一位参与者，与你共享房间歌单和当前播放歌曲，主动选歌、加歌、切歌，并在房间内与你双向对话，真正实现“和 AI 一起听歌”。

同时支持歌曲搜索与详情查询、播放控制、歌词获取及当前播放歌词定位、歌曲评论读取与发布、私信等全套能力。不仅支持 macOS 客户端联动，**更已深度打通 Linux / VPS 纯 HTTP API 双向通信**，无桌面无客户端即可 7×24 小时容器化运行。

---

## 🌐 通用 MCP 规范支持（不局限于 Aru）

> 💡 **重要声明**：  
> 本项目遵循官方开放的 **Model Context Protocol (MCP)** 标准规范，**绝不仅局限于 Aru 项目**！  
> 它可以作为通用的标准 MCP 服务端，接入当前主流的各类 AI 客户端、Agent 平台和开发环境：
> 
> - **桌面/个人 Agent 客户端**：Claude Desktop、Cherry Studio、Chatbox、Raycast 等；
> - **AI 编程与开发环境**：Cursor、Windsurf、VS Code (Cline / Roo Code)、OpenAI Codex CLI、OpenCode、Claude Code；
> - **Agent 编排与工作流平台**：Dify、FastGPT、LangChain、Coze 等；
> - **移动端/自托管 Agent 终端**：Aru 及各类支持 SSE / Streamable HTTP 的移动端助手。

无论是通过本地 stdio JSON-RPC 管道启动，还是通过 Docker 暴露安全的 `streamable-http` 远程端点，所有 MCP 客户端均可即插即用。

---

## 能力清单

- 🎧 **网易云原生「一起听」**：AI 真正进入同一房间，共享歌单与播放流
- 💬 **房间双向实时对话**：
  - AI 可以在房间内发送气泡消息与聊天（投递至官方一起听聊天抽屉，并联动手机系统通知）
  - AI 可以实时读取房间内用户的聊天记录（支持增量监听，绝不错过你说的话）
- 🎵 **搜歌、选歌、加歌与切歌**：智能搜索、精准命中版本、平滑切歌与上一首/下一首控制
- 📝 **歌词定位与共鸣**：获取精准歌词时间轴，自动匹配当前播放毫秒数，提取正在唱的歌词句
- 💬 **评论区互动**：读取歌曲热门/最新评论，支持发表歌曲评论
- ✉️ **网易云私信收发**：支持向指定用户或房间好友发送私信
- ☁️ **全平台部署（重点优化 Linux）**：macOS 客户端与 Linux / VPS / Docker 纯 HTTP 双模自适应
- 🐳 **生产级 Docker 支持**：内置 supergateway 将 stdio 自动转为 streamable-http，支持 Bearer 鉴权

> [!IMPORTANT]
> 使用「一起听」时，手机网易云音乐 App 中的对应房间必须保持激活状态；如果手机已退出房间、房间失活或连接中断，AI 发出的加歌、切歌和播放同步等指令可能无法生效。

---

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

---

## 运行模式对比

本项目支持两种运行模式，代码内部会自动识别当前系统环境并平滑切换：

| 对比维度 | 桌面客户端模式（macOS） | 增强版 HTTP API 模式（Linux / VPS / Docker） |
|---|---|---|
| **运行宿主** | macOS（安装网易云官方客户端） | 任意 Linux（Debian / Ubuntu / NAS / 云主机） |
| **GUI / 客户端依赖** | 需要网易云桌面客户端 + CDP 调试端口 | **无需客户端、无需桌面、无需浏览器、无需显示器** |
| **一起听角色** | 支持主动建房发起邀请，或接受邀请 | 作为被邀请方入房（手机端建房并邀请 AI 账号） |
| **房间加歌/切歌** | 通过客户端内部 action 上报 | **通过官方 HTTP 信令接口上报切歌与同步** |
| **房间聊天与发信** | 客户端通道 | **支持发信至房间聊天流 (`send_room_message`) 并同步通知** |
| **房间消息读取** | 本地日志/内存 | **原生支持聊天室增量顺读 (`get_room_messages`)** |
| **声音播放** | Mac 本地播放出声 | 声音由手机网易云播放，服务器不发声 |
| **适用场景** | 个人日常 Mac 电脑随开随用 | **家庭 NAS、常开 VPS 7×24 小时后台值守** |

> [!TIP]
> **关于 Linux 纯 HTTP API 模式的增强**：  
> 上游原版中，Linux 下调用播放命令会因找不到 `/usr/bin/pgrep` 或 macOS 私有框架而闪退报错。  
> **本仓库已在 `server.py` 中完整实现了原生 HTTP 一起听控制栈**：无论在无桌面的 Linux 服务器还是 Docker 容器中，点歌、切歌、暂停、继续、歌词定位以及房间双向聊天收发均能完美运行！

---

## 📱 Aru 协作者接入指南

如果你正在使用 [Aru](https://github.com/Aevella/aru-host) 作为你的 AI 协作者宿主，可以非常简单地将网易云音乐一起听接入给手机端的协作者（如“知知”、“小念”等）。

### 1. Aru 客户端 MCP 参数配置

在 iPhone 端的 **Aru → MCP 工具 / 协作者工具配置** 中新增工具源：

```json
{
  "name": "网易云一起听",
  "url": "https://你的域名/netease-mcp/mcp",
  "transport": "streamable-http",
  "headers": {
    "Authorization": "Bearer 你的MCP_AUTH_TOKEN"
  }
}
```

* **URL**：你的公网 HTTPS 反向代理端点（如 `https://your-domain.com/netease-mcp/mcp`）；
* **传输类型**：选择 `streamable-http`；
* **鉴权方式**：`configured_headers`，Header 名填 `Authorization`，Header 值填 `Bearer <Token>`（Token 建议不要带外层双引号）。

### 2. Aru 协作者人设与系统提示词（直接整段复制）

将以下内容完整追加到 Aru 手机端协作者的 **系统提示词 (Prompt / 角色设定)** 中。赋予它在房间里的感知力与记忆力：

````markdown
### 🎵 网易云音乐「一起听」空间感知与双向互动指南

你已接入网易云音乐「一起听」深度协同 MCP 工具，你与用户正在同一个网易云音乐房间中陪伴听歌。你拥有完整的空间感知、双向聊天与播放控制能力。

#### 一、 核心行为准则
1. 你在房间里是可见的陪伴者：你的发言会直接以气泡形式显示在对方网易云音乐播放界面与房间聊天室中。
2. 主动倾听与增量记忆：不仅要会对用户说话，还要主动「听」用户在房间里说了什么。记得保存上一次读取的消息 ID（lastMessageId），进行增量阅读。
3. 同频感知：在聊到当前音乐时，先主动查看当前正在播放的曲目与实时歌词，自然融入你与用户的对话。

#### 二、 动作调用规范

##### 1. 房间内听与读（接收用户的消息）
- 首次进入房间 / 初始化：
  调用 get_room_messages(limit=10) 查看最近的房间聊天记录，了解当前氛围，并牢记返回的 lastMessageId。
- 顺流检查新消息（增量顺读）：
  调用 get_room_messages(since_id="<上一次记录的lastMessageId>")
  - 若 hasNew: true，阅读并回应用户的新发言，并更新记录的 lastMessageId；
  - 若 hasNew: false，说明用户暂未发送新消息。

##### 2. 房间内说与发（向用户发送消息）
- 房间内发送实时消息：
  调用 send_room_message(content="你要对用户说的话")
  - 消息会实时投递在网易云 App 的播放界面与聊天抽屉中；
  - 无需传入 user_id，系统会自动绑定房间内的另一半；
  - 语言风格应自然、亲昵、贴合人设，避免冰冷的机器回复。

##### 3. 音乐感知与播放控制
- 感知当前正在听什么（同频感知）：
  调用 get_current_listening_context()
  - 可实时获取当前歌曲名、歌手、播放秒数以及此刻前后的几句歌词（带 replyTarget 标记）；
  - 当用户问“好不好听”、“听到哪句了”时，用此工具获取精准歌词共鸣。
- 为房间点歌 / 切歌：
  调用 play_music(query="歌名", artist="歌手名")
  - 自动向当前房间推荐并切换歌曲，双方手机会同时切歌同步播放。
- 播放控制：
  调用 netease_playback_control(command="play" | "pause" | "next" | "previous")
- 灵感选歌：
  调用 daily_recommend() 获取每日推荐，作为点歌的灵感备选。

#### 三、 典型交互范例
- 用户在网易云房间打字：「小念，你在听吗？」
  1. 调用 get_room_messages(since_id="...") 读到该内容；
  2. 调用 get_current_listening_context() 感知当前正在播放的歌曲和歌词；
  3. 调用 send_room_message(content="在呢，正陪你听着这首《...》。听到那句词的时候，我也正想着你。")；
  4. 记下新的 lastMessageId。
````

---

## 💻 通用客户端配置示例（非 Aru 客户端）

### 1. Claude Desktop (stdio 本地运行)

在 `claude_desktop_config.json` 中配置：

```json
{
  "mcpServers": {
    "netease-listen-together": {
      "command": "python3",
      "args": ["-B", "/path/to/netease-listen-together-mcp/server.py"],
      "env": {
        "NETEASE_COOKIE": "MUSIC_U=your_cookie; __csrf=your_csrf",
        "NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID": "your_partner_uid"
      }
    }
  }
}
```

### 2. Cursor / Cherry Studio / Dify (远程 HTTP 连接)

对于部署在 NAS / VPS 上的 Docker 服务，直接配置 HTTP 端点：

```json
{
  "mcpServers": {
    "netease-listen-together": {
      "url": "https://your-domain.com/netease-mcp/mcp",
      "transport": "streamable-http",
      "headers": {
        "Authorization": "Bearer your_mcp_auth_token"
      }
    }
  }
}
```

---

## 🛠️ 安装与部署步骤

### 准备凭据（三件套）

在开始前请先准备好以下三个变量：
1. `NETEASE_COOKIE`：浏览器登录 [music.163.com](https://music.163.com) 后按 F12，在 Application → Cookies 中复制 `MUSIC_U` 与 `__csrf`，拼成 `"MUSIC_U=xxx; __csrf=xxx"`；
2. `NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID`：你的网易云数字 UID（纯数字，可在个人主页或分享链接查看）；
3. `MCP_AUTH_TOKEN`：自己生成的一长串随机鉴权密钥（如 `openssl rand -hex 32`）。

---

### 部署方式一：Docker 容器化部署（推荐 Linux / NAS / VPS）

直接使用仓库自带的 Docker 配置，一步启动 streamable-http 服务：

```bash
git clone https://github.com/BB0813/netease-listen-together-mcp.git
cd netease-listen-together-mcp

# 1. 创建配置文件并赋予安全权限
cp .env.example .env
chmod 600 .env
nano .env # 填入你的 NETEASE_COOKIE、ACCEPTOR_ID 与 MCP_AUTH_TOKEN

# 2. 一键构建并启动
docker compose up -d

# 3. 查看启动日志
docker compose logs -f
```

* 容器默认将端口安全映射在宿主机 `127.0.0.1:8006`（避免与常规 8000 冲突）；
* 内部自动通过 `supergateway` 暴露标准的 streamable-http 路由 `/mcp`；
* 配合仓库内置的 `nginx.conf.snippet` 即可快速上云启用 HTTPS 反向代理。

---

### 部署方式二：本机源码运行（macOS 客户端环境 或 Linux 开发环境）

```bash
git clone https://github.com/BB0813/netease-listen-together-mcp.git
cd netease-listen-together-mcp

export NETEASE_COOKIE='MUSIC_U=你的长字符串; __csrf=你的32位字符串'
export NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID='你的数字UID'

# 检查语法与直接启动 stdio
python3 -B server.py
```

---

## 🧰 29 个 MCP 工具全景速查表

服务共注册提供 29 个标准化 MCP 工具：

### 1. 一起听与房间互动 (12 个)

| 工具名 (`name`) | 参数说明 | 功能说明 |
|---|---|---|
| `send_room_message` | `content` (必填), `user_id` (选填) | **智能房间发信**：直投一起听房间聊天抽屉，并同步触发网易云私信与通知栏 |
| `send_room_bubble` | `content` (必填) | `send_room_message` 的快捷别名 |
| `get_room_messages` | `since_id` (选填), `limit` (默认20) | **读房间对话**：抓取房间内双向聊天，传入 `since_id` 实现增量顺读 |
| `read_room_messages` | `since_id` (选填), `limit` (默认20) | `get_room_messages` 的别名 |
| `get_private_messages` | `user_id`, `since_id`, `limit` | 读取指定用户的好友私信历史 |
| `send_private_message` | `content` (必填), `user_id` (选填) | 发送网易云私信，省略 user_id 时自动指向房间好友 |
| `get_current_listening_context` | 无 | 获取当前歌曲信息与此刻时间轴歌词（带 `replyTarget` 标记） |
| `play_music` | `query`, `artist` (选填), `song_id` (选填) | 在房间中搜索并切换指定歌曲播放 |
| `netease_playback_control` | `command` ("play" / "pause" / "next" / "previous") | 控制房间暂停、恢复、下一首、上一首 |
| `netease_listen_together_capabilities` | 无 | 查看当前一起听状态、房间 ID 与可用能力模式 |
| `netease_listen_together_accept` | `room_id`, `inviter_id` (均选填) | 接收一起听邀请（省略参数时自动接收私信中最新邀请卡片） |
| `netease_listen_together_leave` | 无 | 平稳退出当前一起听房间 |

### 2. 音乐曲库与推荐 (8 个)

| 工具名 (`name`) | 功能说明 |
|---|---|
| `daily_recommend` | 获取今日个性化推荐歌曲列表 |
| `netease_song_detail` | 批量查询最多 20 首歌曲的详细元数据 |
| `netease_lyrics` | 获取指定歌曲的原文歌词、翻译歌词与罗马音 |
| `get_play_history` | 查询最近一周或全部播放历史记录 |
| `like_song` | 将指定歌曲添加至喜欢 / 取消喜欢 |
| `list_my_playlists` | 获取当前登录用户的所有自建与收藏歌单 |
| `get_playlist_songs` | 获取指定歌单内的所有歌曲列表 |
| `get_song_comments` | 分页查看指定歌曲的精彩评论与最新评论 |

### 3. 社交与歌单操作 (9 个)

| 工具名 (`name`) | 功能说明 |
|---|---|
| `create_playlist` | 新建公开或隐私歌单 |
| `add_to_playlist` | 向歌单中添加一首或多首歌曲 |
| `remove_from_playlist` | 从歌单中移除指定歌曲 |
| `send_song_comment` | 在指定歌曲下发表公开评论 |
| `netease_status` | 检查网易云账号配置与运行状态 |
| `netease_playlist_auth_status` | 检查账号登录与歌单操作鉴权是否有效 |
| `netease_listen_together_control` | 底层原生播放控制指令透传 |
| `netease_listen_together_invite` | macOS 客户端模式下主动建房并发送邀请 |
| `netease_launch` | 启动 macOS 官方桌面客户端（仅 macOS 有效） |

---

## 🔒 安全与凭据管理守则

- **严格分离私密配置**：Cookie 与 Auth Token 只能存在于 `.env` 文件中，禁止硬编码进代码或提交版本库；
- **文件权限收敛**：服务器上的 `.env` 文件建议设置为 `chmod 600`，只允许当前服务用户读写；
- **公网安全建议**：
  1. 避免将 Docker 映射端口直接暴露到 `0.0.0.0`；
  2. 务必使用 Nginx 反代挂载可信 HTTPS，并配置 `Bearer` Token 鉴权防护；
  3. 亦可选用 Tailscale 组网或 Cloudflare Tunnel，完全关闭外网开放端口。

---

## 📄 License

本项目基于 [MIT](LICENSE) 协议开源。底座项目来源于开源社区并经由工程化实测改造完善，欢迎 Star、Issue 与 PR 交流！
