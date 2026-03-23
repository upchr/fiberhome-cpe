"""
CPE API - 烽火 5G CPE 路由器 API 客户端

功能：
- 设备信息查询（温度、信号、流量等）
- 短信收发管理
- 短信监听转发
"""

from .client import CPEClient
from .models import DeviceInfo, SMSMessage
from .watcher import SMSWatcher, BarkNotifier, WebhookNotifier, FeishuNotifier, FeishuWebhookNotifier, Notifier

__version__ = "1.0.0"
__all__ = [
    "CPEClient",
    "DeviceInfo", "SMSMessage",
    "SMSWatcher", "BarkNotifier", "WebhookNotifier", "FeishuNotifier", "FeishuWebhookNotifier", "Notifier"
]
