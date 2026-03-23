# CPE API - 烽火 5G CPE 路由器 API

FastAPI 服务 + 短信监控转发

## 功能

- 📡 设备信息 API（温度、信号、流量等）
- 📩 短信管理 API
- 🔄 后台短信监控转发

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env 填写配置
```

### 3. 启动服务

```bash
# 开发模式
python3 -m uvicorn main:app --reload

# 生产模式
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. 访问 API 文档

打开 http://localhost:8000/docs

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/device/info` | GET | 获取设备信息 |
| `/api/device/info/formatted` | GET | 获取格式化设备信息 |
| `/api/device/temperature` | GET | 获取温度 |
| `/api/device/usage` | GET | 获取系统使用率 |
| `/api/device/uptime` | GET | 获取运行时间 |
| `/api/sms/list` | GET | 获取短信列表 |
| `/api/sms/unread` | GET | 获取未读短信 |
| `/api/watcher/status` | GET | 获取监控状态 |
| `/api/watcher/start` | POST | 启动短信监控 |
| `/api/watcher/stop` | POST | 停止短信监控 |

## 配置说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CPE_HOST` | CPE 地址 | `http://192.168.1.1` |
| `CPE_USERNAME` | 用户名 | `admin` |
| `CPE_PASSWORD` | 密码 | - |
| `CHECK_INTERVAL` | 检查间隔（秒） | `3.0` |
| `AUTO_START_WATCHER` | 启动时自动开启监控 | `false` |
| `BARK_KEY` | Bark 推送 Key | - |
| `FEISHU_WEBHOOK` | 飞书 Webhook URL | - |
| `WEBHOOK_URL` | 自定义 Webhook URL | - |

## 示例

### 获取设备信息

```bash
curl http://localhost:8000/api/device/info
```

响应：
```json
{
  "success": true,
  "message": "获取成功",
  "data": {
    "product_name": "5G CPE",
    "model_name": "LG6121F",
    "serial_number": "MTRTGJ401781ACAB20",
    "temperature": {"5g": 36.2, "unit": "℃"}
  }
}
```

### 获取格式化设备信息

```bash
curl http://localhost:8000/api/device/info/formatted
```

响应：
```json
{
  "success": true,
  "data": "📋 **基本信息**\n• 产品名称: 5G CPE\n• 设备型号: LG6121F\n..."
}
```

## 作为库使用

```python
from cpe_api import CPEClient, SMSWatcher, FeishuWebhookNotifier

# 获取设备信息
client = CPEClient("http://192.168.1.1")
client.login("admin", "password")

temp = client.get_temperature()
print(f"5G 温度: {temp['5g']}°C")

client.logout()

# 短信监控
watcher = SMSWatcher(
    host="http://192.168.1.1",
    username="admin",
    password="password",
    notifiers=[FeishuWebhookNotifier("your-webhook-url")]
)
watcher.start()
```
