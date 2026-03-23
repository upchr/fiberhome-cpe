"""
CPE API - 烽火 5G CPE 路由器 API 客户端

功能：
- 设备信息查询
- 网络状态监控
- 短信收发管理
- WiFi 配置
- 连接设备管理
- 短信监听转发
"""

from .client import CPEClient
from .client_browser import CPEClientBrowser
from .models import DeviceInfo, SMSMessage, WiFiInfo, ConnectedDevice, SignalInfo, NetworkInfo, DataUsage
from .watcher import SMSWatcher, BarkNotifier, WebhookNotifier, FeishuNotifier, FeishuWebhookNotifier, Notifier

__version__ = "1.0.0"
__all__ = [
    "CPEClient", "CPEClientBrowser",
    "DeviceInfo", "SMSMessage", "WiFiInfo", "ConnectedDevice", "SignalInfo", "NetworkInfo", "DataUsage",
    "SMSWatcher", "BarkNotifier", "WebhookNotifier", "FeishuNotifier", "FeishuWebhookNotifier", "Notifier"
]
