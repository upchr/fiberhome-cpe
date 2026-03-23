# CPE API - 烽火 5G CPE 路由器 API 客户端

[English](#english) | [中文](#中文)

## 中文

### 功能

- ✅ 登录认证（AES 加密）
- ✅ 心跳保活
- ✅ 短信监听与转发
- ✅ 多通知渠道支持
  - 飞书 Webhook 机器人（推荐）
  - 飞书应用机器人
  - Bark（iOS 推送）
  - 自定义 Webhook

### 安装

```bash
pip install -r requirements.txt
```

### 配置

1. 复制配置模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件：
```bash
# CPE 配置
CPE_HOST=http://192.168.1.1
CPE_USERNAME=admin
CPE_PASSWORD=your-password

# 飞书 Webhook（推荐）
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
```

### 使用

**命令行启动：**
```bash
python3 sms_forwarder.py
```

**代码调用：**
```python
from cpe_api import CPEClient, SMSWatcher, FeishuWebhookNotifier

# 简单使用
client = CPEClient("http://192.168.1.1")
client.login("admin", "password")

# 检查新短信
if client.get_new_sms_flag():
    for sms in client.get_unread_sms():
        print(f"[{sms.phone}] {sms.content}")

client.logout()

# 持续监听
watcher = SMSWatcher(
    host="http://192.168.1.1",
    username="admin",
    password="password",
    notifiers=[FeishuWebhookNotifier("your-webhook-url")]
)
watcher.start()
```

### 获取飞书 Webhook

1. 打开飞书群组
2. 群设置 → 群机器人 → 添加机器人 → 自定义机器人
3. 复制 Webhook URL

---

## English

A Python client for Fiberhome 5G CPE routers with SMS forwarding support.

### Features

- AES encrypted authentication
- Heartbeat keep-alive
- SMS monitoring and forwarding
- Multiple notification channels

### Installation

```bash
pip install -r requirements.txt
```

### Usage

```python
from cpe_api import CPEClient

client = CPEClient("http://192.168.1.1")
client.login("admin", "password")

# Check for new SMS
if client.get_new_sms_flag():
    for sms in client.get_unread_sms():
        print(f"[{sms.phone}] {sms.content}")

client.logout()
```

### License

MIT
