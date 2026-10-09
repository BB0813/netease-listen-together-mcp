const https = require('https');

global.window = global;
global.document = {
  createElement: () => ({ style: {} }),
  addEventListener: () => {},
  removeEventListener: () => {}
};
try { delete global.navigator; } catch (e) {}
Object.defineProperty(global, 'navigator', {
  value: { userAgent: 'Node' },
  writable: true,
  configurable: true
});
global.WebSocket = require('ws');

const SDK = require('@yxim/nim-web-sdk');
const NIM = SDK.NIM;
const Chatroom = SDK.Chatroom;
const APP_KEY = '3a6a3e48f6854dfa4e4464f3bdaec3b4';

function getCsrf(cookie) {
  for (const part of (cookie || '').split(';')) {
    const p = part.trim();
    if (p.startsWith('__csrf=')) return p.slice(7);
  }
  return '';
}

function neteasePost(path, form, cookie) {
  const csrf = getCsrf(cookie);
  const postData = new URLSearchParams({ ...form, csrf_token: csrf }).toString();
  const options = {
    hostname: 'music.163.com',
    port: 443,
    path: path + '?csrf_token=' + encodeURIComponent(csrf),
    method: 'POST',
    headers: {
      'User-Agent': 'Mozilla/5.0',
      'Referer': 'https://music.163.com/',
      'Cookie': cookie,
      'Content-Type': 'application/x-www-form-urlencoded',
      'Content-Length': Buffer.byteLength(postData)
    }
  };
  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); } catch (e) { resolve({ code: -1, raw: data }); }
      });
    });
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

async function sendBubble(text, cookie) {
  if (!text) throw new Error('消息内容不能为空');
  if (!cookie) throw new Error('NETEASE_COOKIE 未配置');

  // 1. 获取一起听房间状态与 chatRoomId
  const statusRes = await neteasePost('/api/listen/together/status/get', {}, cookie);
  const roomData = statusRes?.data || {};
  if (!roomData.inRoom || !roomData.roomInfo?.chatRoomId) {
    throw new Error('当前未加入「一起听」房间，无法发送房间气泡');
  }
  const chatroomId = String(roomData.roomInfo.chatRoomId);
  const roomId = String(roomData.roomInfo.roomId);

  // 2. 获取云信 IM token
  const imRes = await neteasePost('/api/middle/im/token/get', {}, cookie);
  const imData = imRes?.data || {};
  const account = String(imData.accId || imData.uid || '');
  const token = String(imData.token || '');
  if (!account || !token) {
    throw new Error('获取网易云信 IM Token 失败');
  }

  // 3. 连接云信 NIM 并加入聊天室发送气泡消息
  return new Promise((resolve, reject) => {
    let finished = false;
    const timeout = setTimeout(() => {
      if (!finished) {
        finished = true;
        reject(new Error('发送房间气泡超时 (15s)'));
      }
    }, 15000);

    const nim = NIM.getInstance({
      appKey: APP_KEY,
      account,
      token,
      debug: false,
      onconnect() {
        nim.getChatroomAddress({
          chatroomId,
          done(err, addr) {
            if (err) {
              cleanup(err);
              return;
            }
            const chatroom = Chatroom.getInstance({
              appKey: APP_KEY,
              account,
              token,
              chatroomId,
              chatroomAddresses: addr.address,
              debug: false,
              onconnect() {
                chatroom.sendText({
                  text,
                  done(sendErr, msg) {
                    if (sendErr) {
                      cleanup(sendErr);
                    } else {
                      cleanup(null, {
                        success: true,
                        roomId,
                        chatroomId,
                        content: text,
                        messageId: msg?.idClient,
                        message: '房间气泡文字发送成功！已在网易云 App 一起听播放界面显示。'
                      });
                    }
                  }
                });
              },
              onerror(cErr) { cleanup(cErr); }
            });

            function cleanup(err, result) {
              if (finished) return;
              finished = true;
              clearTimeout(timeout);
              try { chatroom.disconnect(); } catch (e) {}
              try { nim.disconnect(); } catch (e) {}
              if (err) reject(err);
              else resolve(result);
            }
          }
        });
      },
      onerror(nErr) {
        if (!finished) {
          finished = true;
          clearTimeout(timeout);
          reject(nErr);
        }
      }
    });
  });
}

let inputData = '';
process.stdin.on('data', chunk => inputData += chunk);
process.stdin.on('end', async () => {
  try {
    const parsed = JSON.parse(inputData || '{}');
    const text = parsed.text || '';
    const cookie = process.env.NETEASE_COOKIE || '';
    const res = await sendBubble(text, cookie);
    console.log(JSON.stringify(res));
    process.exit(0);
  } catch (err) {
    console.log(JSON.stringify({
      success: false,
      error: err.message || String(err),
      message: '发送房间气泡失败: ' + (err.message || String(err))
    }));
    process.exit(0);
  }
});
