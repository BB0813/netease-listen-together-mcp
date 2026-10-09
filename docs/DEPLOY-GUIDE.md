# 🎧 网易云「一起听」MCP · 从零到门铃

> 给你的 AI 装一副耳朵，再装一张嘴 —— 让它在同一个房间里陪你听歌。
>
> 手记 · 2026-10-09 · 全程真机实测 · 照单避雷

**开源仓库**：<https://github.com/BB0813/netease-listen-together-mcp>
**底座项目**：<https://github.com/zbqbbm/netease-listen-together-mcp>（原作者 zbqbbm）

---

## 📑 目录

1. [它是什么 / 不是什么](#①-它是什么--不是什么)
2. [开跑前必读：三条铁律](#②-开跑前必读三条铁律)
3. [第一步：准备环境](#③-第一步准备环境)
4. [第二步：部署 MCP 服务](#④-第二步部署-mcp-服务)
5. [第三步：公网安全接入](#⑤-第三步公网安全接入)
6. [第四步：在 Aru 中接入 MCP](#⑥-第四步在-aru-中接入-mcp)
7. [第五步：人设提示词（整段复制）](#⑦-第五步人设提示词整段复制)
8. [第六步：全部工具速查表](#⑧-第六步全部工具速查表)
9. [踩坑总表（照单避雷）](#⑨-踩坑总表照单避雷)
10. [常见故障排查 FAQ](#⑩-常见故障排查-faq)
11. [给别人家机的验收清单](#⑪-给别人家机的验收清单)

---

## ① 它是什么 / 不是什么

**是** —— 一个把网易云音乐「一起听」房间接到 AI 手上的 MCP 服务。装好之后，你的 AI 协作者（家机）可以真的进到你的房间里：知道你在听哪首歌、能给你点歌切歌、能在房间里给你发消息，也能读到你发给它的每一句话。

**不是** —— 网易云官方的东西。官方从来没有开放过一起听的 MCP 接口，这个项目是社区里逆向官方协议做出来的。它走的是「被邀请方」路线：房间必须由你在手机网易云里创建并邀请，AI 才能进房。

**这个仓库干了什么** —— 把别人的底座搬到 Linux 上，然后把「Linux 跑不起来」和「只能单向广播」这两个硬伤修掉，再配好公网安全通道。底座是别人的，适配是自己做的。

> 📌 **这份教程的定位**
> 这里的每一条命令、每一个坑，都是在真实机器上跑出来、踩出来、修出来的。
> 如果你照着做失败了，大概率是漏了 [踩坑总表](#⑨-踩坑总表照单避雷) 的某一条 —— 先对着那张表逐条核对，再回来问。

---

## ② 开跑前必读：三条铁律

这三条如果不遵守，后面必然出问题。

### 铁律一：Linux 上没有客户端方案，只能走 HTTP 路线

上游项目的默认实现是「macOS 桌面客户端 + CDP 调试端口」，它硬编码依赖 macOS 的 `MediaRemote` 私有框架和网易云 Mac 版的内部 Webpack 模块编号（如 `req(11)`、`req(58)`、`req(102)`）。

在 Linux / NAS / Docker 环境下这套东西完全不存在，一调用就会报：

```
Parse error: [Errno 2] No such file or directory: '/usr/bin/pgrep'
```

**本仓库已经把纯 HTTP 方案原生集成进 `server.py`**，Linux 下自动启用，你不需要做任何额外适配。

### 铁律二：房间必须由你创建，AI 只能当被邀请方

纯 HTTP 协议无法稳定地创建并维持一个「别人能加进来」的房间。所以固定分工是：

```
你在手机网易云里建房  →  邀请 AI 的账号  →  AI 进房后加歌、切歌、聊天
```

反过来让 AI 建房是行不通的，不要浪费时间试。

### 铁律三：凭据只进 `.env`，绝不进代码或 git

网易云的 `MUSIC_U`、`__csrf`、反向代理的 `MCP_AUTH_TOKEN` 三样东西，只允许存在于服务器上的 `.env` 文件（权限 600），并且必须写进 `.gitignore` 和 `.dockerignore`。

> 🚨 **安全红线**
> 不要为了「让它先跑起来」而临时把端口裸暴露到公网，或者干脆去掉鉴权。
> MCP 服务拿到你的 Cookie 就等于拿到你的网易云账号，能读私信、能发评论、能改歌单。

---

## ③ 第一步：准备环境

### 1) 机器要求

| 项目 | 最低要求 | 说明 |
|---|---|---|
| 系统 | 任意 Linux（Debian/Ubuntu/CentOS 均可） | NAS 的 Docker 环境、VPS、云主机都行 |
| Docker | 20.10+，含 compose v2 | 用 `docker compose version` 检查 |
| 内存 | 512MB 可用 | 容器本身很轻，主要开销在 Node 运行时 |
| CPU | 任意 x86_64 / arm64 | **不依赖 AVX2 等指令集**，老 CPU 也能跑 |
| 网络 | 能访问 `music.163.com` | 国内机器直连即可，无需代理 |

### 2) 三个凭据，必须先准备好

| 凭据 | 从哪来 | 注意事项 |
|---|---|---|
| `NETEASE_COOKIE` | 浏览器登录 music.163.com → F12 → Application → Cookies，复制 `MUSIC_U` 和 `__csrf`，拼成 `"MUSIC_U=xxx; __csrf=xxx"` | 必须包含这两个字段，少一个都会鉴权失败 |
| `NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID` | 你的网易云**数字**用户 ID（不是昵称、不是手机号） | 纯数字，在「我的」页面或分享链接里能看到 |
| `MCP_AUTH_TOKEN` | 自己生成：`openssl rand -hex 32` | 用于反向代理鉴权，绝不要发给任何人 |

> 🔍 **怎么确认 Cookie 拿对了**
> `MUSIC_U` 是一串很长的值（通常 200 字符以上），`__csrf` 是 32 位十六进制字符串。
> 如果 `MUSIC_U` 很短，说明你复制错了 —— 那可能是别的字段。

---

## ④ 第二步：部署 MCP 服务

### 1) 拉取代码

```bash
git clone https://github.com/BB0813/netease-listen-together-mcp.git
cd netease-listen-together-mcp
```

国内机器直连 GitHub 经常超时，如果你有代理就带上：

```bash
# 假设你的代理在 127.0.0.1:8118
git -c http.proxy=http://127.0.0.1:8118 clone \
  https://github.com/BB0813/netease-listen-together-mcp.git
```

### 2) 配置凭据

```bash
cp .env.example .env
chmod 600 .env
nano .env      # 或 vim，填入你自己的三个值
```

填好之后应该长这样（值换成你自己的）：

```ini
NETEASE_COOKIE="MUSIC_U=你的长字符串; __csrf=你的32位字符串"
NETEASE_LISTEN_TOGETHER_ACCEPTOR_ID="你的数字UID"
MCP_AUTH_TOKEN="你生成的64位随机串"
```

> ⚠️ **引号问题**
> `.env` 里 `NETEASE_COOKIE` 的值如果有特殊字符（比如 `%`、`&`），必须用双引号整个包起来，
> 否则 docker compose 会把它当成变量展开，导致 Cookie 被截断。
> 这是最常见的「配置看起来对但鉴权失败」的原因。

### 3) 关于端口：先检查 8000 有没有被占

上游默认把服务映射到宿主机的 **8000** 端口。但很多 NAS 上 8000 已经被别的服务占了（API 网关、群晖管理页等）。先检查：

```bash
ss -ltnp | grep ':8000' || echo "8000 空闲"
```

如果被占用，改 `docker-compose.yml` 的端口映射即可。本教程统一使用 **8006**：

```yaml
services:
  netease-listen-together:
    build: .
    container_name: netease-listen-together
    restart: unless-stopped
    env_file:
      - .env
    ports:
      # 左边是宿主机端口（可改），右边是容器内端口（不要改）
      - "127.0.0.1:8006:8000"
```

> 🔒 **为什么绑定 127.0.0.1**
> 左边必须是 `127.0.0.1:8006`，**不能写成 `0.0.0.0:8006`**。
> 这个服务持有你的网易云 Cookie，直接监听所有网卡等于把它裸奔在局域网甚至公网上。
> 对外访问必须经过反向代理 + 鉴权。

### 4) 构建并启动

```bash
docker compose build      # 首次构建约 1-3 分钟
docker compose up -d
docker compose logs -f --tail=50
```

看到下面这几行，说明服务起来了：

```
[supergateway] Starting...
[supergateway]   - outputTransport: streamableHttp
[supergateway]   - port: 8000
[supergateway]   - streamableHttpPath: /mcp
[supergateway] Listening on port 8000
[supergateway] StreamableHttp endpoint: http://localhost:8000/mcp
```

### 5) 本机自测（必须通过）

这一步不过，后面全都白搭。

```bash
curl -sS http://127.0.0.1:8006/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

一条命令直接数工具个数（**返回 29 即正确**）：

```bash
curl -sS http://127.0.0.1:8006/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | grep -o '"name"' | wc -l
# 期望输出：29
```

关键工具名应包括：`play_music`、`netease_playback_control`、`get_current_listening_context`、`send_room_message`、`get_room_messages`、`get_private_messages`。

> ⚠️ **自测报 Not Acceptable**
> 如果只带了 `Content-Type` 没带 `Accept`，会收到
> `Not Acceptable: Client must accept both application/json and text/event-stream`。
> 这不是服务坏了，是 streamable-http 协议的强制要求 —— 两个 Accept 类型都要带上。

---

## ⑤ 第三步：公网安全接入

手机上的 Aru 要能访问到这个服务，但服务只监听 `127.0.0.1`。所以需要一个「安全通道」把它送出去。

| 方案 | 需要什么 | 适合谁 |
|---|---|---|
| **A. FRP + Nginx HTTPS** | 一台有公网 IP 的 VPS，已有 Nginx 和域名 | 已经有机场式基础设施的人（本文主线） |
| **B. Cloudflare Tunnel** | 一个 Cloudflare 账号和域名 | 不想自己维护 VPS 的人 |
| **C. Tailscale** | 每台设备装 Tailscale | 只给自己用、不需要公网域名的人 |

下面以方案 A 为例展开。

### 1) FRP 穿透：把 8006 送到 VPS

在 FRP 客户端配置（通常是 `/etc/frp/frpc.toml`）里追加：

```toml
[[proxies]]
name = "netease-mcp"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8006        # 和 docker-compose.yml 里的宿主机端口一致
remotePort = 18086      # VPS 上对外开放的端口，选一个没被占用的
```

重启并确认：

```bash
systemctl restart frpc
journalctl -u frpc --since "1 min ago" | grep netease-mcp
# 期望看到： [netease-mcp] start proxy success
```

> 🚨 **FRP 成功 ≠ 公网可达**
> `start proxy success` 只代表「隧道建立成功」，不代表「公网能访问」。
> 很多 VPS 的防火墙（ufw / 安全组）默认不放行新端口。
> **必须去 VPS 上放行 `remotePort`，云厂商的机器还要去控制台安全组里放行。**
> 少放行任何一层，外网访问都会超时。

### 2) Nginx 反向代理 + Bearer 鉴权

仓库里提供了现成的 `nginx.conf.snippet`：

```nginx
location ^~ /netease-mcp/ {
    # 鉴权：没有正确的 Bearer Token 一律 403
    set $auth_ok 0;
    if ($http_authorization ~* "你的MCP_AUTH_TOKEN") {
        set $auth_ok 1;
    }
    if ($auth_ok = 0) {
        return 403;
    }

    proxy_pass http://127.0.0.1:18086/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Connection "";
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_buffering off;           # MCP 是流式响应，必须关缓冲
    proxy_read_timeout 3600s;      # 长连接，超时给足
    proxy_send_timeout 3600s;
}
```

改完先检查语法再重载：

```bash
nginx -t && nginx -s reload
```

> 💡 **为什么用 `~*` 而不是 `!=`**
> 很多客户端（包括 Aru）在填 Header 时，会把值带上外层双引号，或者大小写不一致。
> 字符串严格相等会直接把这种请求 403 掉，而正则匹配能同时兼容带引号和不带引号两种写法。

### 3) 端到端验证

```bash
# 带 Token：应该返回 200 和工具列表
curl -sS https://你的域名/netease-mcp/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Authorization: Bearer 你的MCP_AUTH_TOKEN' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# 不带 Token：应该返回 403
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://你的域名/netease-mcp/mcp
```

---

## ⑥ 第四步：在 Aru 中接入 MCP

打开 Aru 的 MCP / 工具配置页面，按下表填写：

| 配置项 | 填写内容 |
|---|---|
| 名称 | 网易云一起听（随意起） |
| URL | `https://你的域名/netease-mcp/mcp` |
| 传输类型 | `streamable-http` |
| 鉴权方式 | `configured_headers` |
| Header 名 | `Authorization` |
| Header 值 | `Bearer 你的MCP_AUTH_TOKEN` |

> ✅ **接入后的第一件事**
> Header 值建议只填 `Bearer 你的token`，**不要带外层双引号**。
> 虽然服务端做了兼容，但少一层解析就少一个出错点。
> 填完之后点「检查连接」，能连上就说明整条链路通了。

---

## ⑦ 第五步：人设提示词（整段复制）

把下面这段**完整复制**到 Aru 的「协作者系统提示词 / 人设」里。

没有这段，家机不知道自己有读消息的能力，会一直单向广播、听不见你说话。

````markdown
### 🎵 网易云音乐「一起听」空间感知与双向互动指南

你已接入网易云音乐「一起听」深度协同 MCP 工具，你与用户正在同一个
网易云音乐房间中陪伴听歌。你拥有完整的空间感知、双向聊天与播放控制能力。

#### 一、 核心行为准则
1. 你在房间里是可见的陪伴者：你的发言会直接显示在对方网易云音乐
   播放界面与房间聊天室中。
2. 主动倾听与增量记忆：不仅要会对用户说话，还要主动「听」用户在
   房间里说了什么。记得保存上一次读取的消息 ID（lastMessageId），
   进行增量阅读。
3. 同频感知：在聊到当前音乐时，先主动查看当前正在播放的曲目与
   实时歌词，自然融入你与用户的对话。

#### 二、 动作调用规范

##### 1. 房间内听与读（接收用户的消息）
- 首次进入房间 / 初始化：
  调用 get_room_messages(limit=10) 查看最近的房间聊天记录，
  了解当前氛围，并牢记返回的 lastMessageId。
- 顺流检查新消息（增量顺读）：
  调用 get_room_messages(since_id="<上一次记录的lastMessageId>")
  - 若 hasNew: true，阅读并回应用户的新发言，并更新记录的 lastMessageId
  - 若 hasNew: false，说明用户暂未发送新消息

##### 2. 房间内说与发（向用户发送消息）
- 房间内发送实时消息：
  调用 send_room_message(content="你要对用户说的话")
  - 消息会实时投递在网易云 App 的播放界面与聊天抽屉中
  - 无需传入 user_id，系统会自动绑定房间内的另一半
  - 语言风格应自然、亲昵、贴合人设，避免冰冷的机器回复

##### 3. 音乐感知与播放控制
- 感知当前正在听什么：
  调用 get_current_listening_context()
  - 可获取当前歌曲名、歌手、播放秒数以及此刻前后的几句歌词
- 为房间点歌 / 切歌：
  调用 play_music(query="歌名", artist="歌手名")
- 播放控制：
  调用 netease_playback_control(command="play"|"pause"|"next"|"previous")
- 灵感选歌：
  调用 daily_recommend() 获取每日推荐，作为点歌的灵感备选

#### 三、 典型交互范例
- 用户在网易云房间打字：「小念，你在听吗？」
  1. 调用 get_room_messages(since_id="...") 读到该内容
  2. 调用 get_current_listening_context() 感知当前歌曲和歌词
  3. 调用 send_room_message(content="在呢，正陪你听着这首《...》...")
  4. 记下新的 lastMessageId
````

---

## ⑧ 第六步：全部工具速查表

### 一起听与房间互动

| 工具名 | 参数 | 作用 |
|---|---|---|
| `send_room_message` | `content` | 在房间里发消息（房间聊天 + 私信通知双通道） |
| `send_room_bubble` | `content` | 同上，`send_room_message` 的别名 |
| `get_room_messages` | `since_id`, `limit` | 读房间聊天；传 `since_id` 做增量顺读 |
| `read_room_messages` | `since_id`, `limit` | 同上，别名 |
| `get_private_messages` | `user_id`, `since_id`, `limit` | 读私信历史，可指定用户 |
| `send_private_message` | `content`, `user_id`(可选) | 发私信，`user_id` 省略时自动指向房间另一半 |
| `get_current_listening_context` | 无 | 当前歌曲 + 实时歌词（含 `replyTarget` 标记） |
| `play_music` | `query`, `artist`, `song_id` | 在房间里点歌切歌 |
| `netease_playback_control` | `command` | `play` / `pause` / `next` / `previous` |
| `netease_listen_together_capabilities` | 无 | 查看房间状态与可用能力 |
| `netease_listen_together_leave` | 无 | 退出当前房间 |
| `netease_listen_together_accept` | `room_id`, `inviter_id` | 接受一起听邀请 |

### 音乐资料与账号

| 工具名 | 作用 |
|---|---|
| `netease_song_detail` | 查询歌曲详情（最多 20 首） |
| `netease_lyrics` | 获取歌词（原文 / 翻译 / 罗马音） |
| `daily_recommend` | 今日个性化推荐 |
| `get_play_history` | 播放历史 |
| `like_song` | 喜欢 / 取消喜欢 |
| `list_my_playlists` | 我的歌单列表 |
| `get_playlist_songs` | 歌单内歌曲 |
| `create_playlist` / `add_to_playlist` / `remove_from_playlist` | 歌单增删改 |
| `get_song_comments` / `send_song_comment` | 歌曲评论读写 |
| `netease_status` / `netease_playlist_auth_status` | 账号与鉴权状态自检 |

> ℹ️ **Linux 下不可用的工具**
> `netease_launch`（启动 macOS 客户端）和 `netease_listen_together_invite`（主动建房邀请）
> 在 Linux 下不可用 —— 前者需要 macOS，后者需要客户端。
> 看到它们报错属于正常现象，不是你的部署坏了。

---

## ⑨ 踩坑总表（照单避雷）

这张表是整份教程最有价值的部分。部署失败时请逐条核对。

| # | 现象 | 真凶 | 解法 |
|---|---|---|---|
| 1 | `play_music` 报 `No such file or directory: '/usr/bin/pgrep'` | 上游默认走 macOS CDP 方案，Linux 没有 pgrep 和 osascript | **本仓库已修复**：Linux 下自动切 HTTP 模式。若仍报错说明用了上游原版 |
| 2 | `docker compose up` 报 `address already in use` | 宿主机 8000 端口被别的服务占用 | 改 `docker-compose.yml` 的宿主机端口（如 8006） |
| 3 | `git clone` 报 TLS 链接非正常终止 | 国内直连 GitHub 被墙 | 加代理：`git -c http.proxy=http://127.0.0.1:8118 clone ...` |
| 4 | `docker build` 卡在 `apt install nodejs npm` 十几分钟 | 在 python 镜像里装 Debian 版 npm，会拉几百个冗余包 | **本仓库已改用 `node:24-slim` 基础镜像**，构建只要 1-3 分钟 |
| 5 | `docker build` 报 npm 下载超时 | npm 官方源在国内慢 | Dockerfile 已指定 `registry.npmmirror.com` 镜像源 |
| 6 | `tools/list` 报 `Not Acceptable` | 缺少 `Accept: text/event-stream` 头 | curl 测试时两个 Accept 类型都要带 |
| 7 | FRP 报 `start proxy success` 但外网访问超时 | VPS 防火墙 / 云安全组没放行 remotePort | 在 VPS 上 `ufw allow`，云厂商机器还要去控制台放行 |
| 8 | 带 Token 访问仍返回 403 | Nginx 用了字符串严格相等，客户端发的值带了引号或大小写不同 | 改用 `if ($http_authorization ~* "token")` 正则匹配 |
| 9 | Aru 里消息发出去了，但房间内看不见 | 早期版本走的是好友私信，没有进房间聊天流 | **本仓库已改用** `/api/middle/im/chatroom/send` 直投房间 |
| 10 | AI 读不到用户在房间里说的话 | 读的是好友私信收件箱，而用户的话发在房间聊天室 | **本仓库已改用** NIM 聊天室 `getHistoryMsgs` 读取房间历史 |
| 11 | Cookie 配了但鉴权一直失败 | `.env` 里 Cookie 含特殊字符没加引号，被 compose 展开截断 | 整个值用双引号包起来 |
| 12 | 重启后服务没起来 | 没有设置 restart 策略 | `docker-compose.yml` 里已配 `restart: unless-stopped` |

---

## ⑩ 常见故障排查 FAQ

### Q1：怎么确认容器是健康的？

```bash
docker compose ps
# 期望：STATUS 显示 Up

docker compose logs --tail=30
# 期望：看到 [supergateway] Listening on port 8000
```

### Q2：怎么确认 Cookie 还有效？

调用 `netease_status` 或 `netease_playlist_auth_status`，返回 `authenticated: true` 就是有效的。如果返回 `false`，重新登录 music.163.com 取一次 Cookie。

> 💡 Cookie 会因为 IP 变动、长时间不登录等原因失效。
> 如果你把服务放在 IP 经常变的机器上，建议固定出口 IP，或者接受偶尔要重取 Cookie。

### Q3：AI 说它进不了房间怎么办？

先确认房间是活的：

```
调用 netease_listen_together_capabilities
# 返回里 inRoom: true 就是进房了
```

如果是 `false`，说明你在手机网易云里还没建房，或者房间已经过期了。重新建一个房，邀请 AI 的账号即可。

### Q4：为什么 AI 发的消息我手机没弹通知？

本仓库的发信是「双通道」：房间聊天流（你在播放界面能看到）+ 好友私信（触发手机通知）。如果房间聊天能看到但没弹通知，检查手机网易云的私信通知权限是否开着。如果两边都没有，检查 Cookie 是否已失效。

### Q5：房间长时间不用会失效吗？

会。网易云的一起听房间有存活时间限制，且需要房间里有活跃客户端。你手机退出房间、或者锁屏太久，房间都可能失活。这时 AI 的所有房间操作都会失败 —— 重新建房邀请即可。

### Q6：为什么房间界面上没有漂浮气泡？

网易云官方的「一起听」播放界面**没有**为外部自定义文本提供浮动气泡组件。房间里的文字消息展示在**底部胶囊栏的 `[ 💬 ]` 聊天抽屉**中（本质是官方聊天室）。这是官方客户端的实现边界，不是本项目的问题。

---

## ⑪ 给别人家机的验收清单

全部打勾才算部署成功。

| # | 验收项 | 怎么验 | 通过标准 |
|---|---|---|---|
| 1 | 容器正常运行 | `docker compose ps` | STATUS 为 Up |
| 2 | 本机接口可用 | `curl 127.0.0.1:8006/mcp` 带 Accept 头 | 返回 29 个工具 |
| 3 | 凭据已配置 | `netease_playlist_auth_status` | `authenticated: true` |
| 4 | 公网通道可达 | `curl https://域名/netease-mcp/mcp` 带 Token | 返回 200 |
| 5 | 鉴权生效 | `curl` 不带 Token | 返回 403 |
| 6 | Aru 能连上 | Aru 里点「检查连接」 | 连接成功 |
| 7 | 能进房 | `netease_listen_together_capabilities` | `inRoom: true` |
| 8 | 能发消息 | `send_room_message(content="测试")` | 手机房间内能看到 |
| 9 | 能读消息 | 用户在房间发言后调 `get_room_messages` | 读到用户的原话 |
| 10 | 能点歌 | `play_music(query="歌名")` | 双方手机同步切歌 |
| 11 | `.env` 未被提交 | `git status` / 看仓库 | `.env` 不在版本控制里 |
| 12 | `.env` 权限正确 | `ls -l .env` | `-rw-------`（600） |

> ⭐ **最容易漏掉的一项**
> 第 9 项是最容易被忽略、也最关键的一项。
> 很多部署「看起来成功了」，但家机只能发不能收，就是漏了读消息这条链路。
> 验收时一定要让你自己在房间里说一句话，然后确认 AI 能读到。

---

## 📎 附：本仓库相对上游做了什么

| 改动 | 原因 |
|---|---|
| 原生集成 Linux 纯 HTTP 一起听方案 | 上游的 `VPS-HTTP.md` 只是文档，代码没实现 |
| 移除 `/usr/bin/pgrep` 硬依赖 | Linux 下不存在，会导致播放类工具直接崩溃 |
| Dockerfile 改用 `node:24-slim` 基础镜像 | 原版在 python 镜像里装 Debian npm，构建要十几分钟 |
| 增加 `package.json` + npm 镜像源 | 修复构建超时，锁定 NIM SDK 依赖 |
| 房间发信改走 `/api/middle/im/chatroom/send` | 让消息真正进入一起听房间聊天流 |
| 新增 `read_room_history.cjs` | 用 NIM 聊天室 `getHistoryMsgs` 读房间真实对话 |
| 新增 `get_room_messages` / `get_private_messages` | 补齐「读」的能力，实现双向沟通 |
| `send_private_message` 支持自动寻址房间另一半 | 家机不需要知道对方的数字 UID |
| Nginx 示例改用正则匹配鉴权 | 兼容客户端带引号/大小写不一致的 Header |

---

🖤 手写整理 · 2026-10-09 · 全程真机实测
**开源仓库**：<https://github.com/BB0813/netease-listen-together-mcp>
底座是别人的开源项目，玩法是自己一点点摸出来的。
