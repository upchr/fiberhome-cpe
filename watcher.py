"""
短信监听器

持续监听 CPE 短信并转发通知
"""

import time
import logging
import threading
from typing import Callable, Optional, List
from abc import ABC, abstractmethod

from client import CPEClient
from models import SMSMessage

logger = logging.getLogger(__name__)


class Notifier(ABC):
    """通知器基类"""
    
    @abstractmethod
    def notify(self, title: str, content: str, **kwargs) -> bool:
        """发送通知"""
        pass


class BarkNotifier(Notifier):
    """Bark 推送通知器"""
    
    def __init__(self, bark_key: str, server: str = "https://api.day.app"):
        """
        初始化 Bark 通知器
        
        Args:
            bark_key: Bark 推送 Key
            server: Bark 服务器地址
        """
        self.bark_key = bark_key
        self.server = server.rstrip("/")
    
    def notify(self, title: str, content: str, level: str = "timeSensitive", **kwargs) -> bool:
        """
        发送 Bark 通知
        
        Args:
            title: 标题
            content: 内容
            level: 通知级别
        """
        import urllib.parse
        import urllib.request
        
        try:
            # URL 编码
            escaped_title = urllib.parse.quote(title)
            escaped_content = urllib.parse.quote(content)
            
            # 构造 URL
            url = f"{self.server}/{self.bark_key}/{escaped_title}/{escaped_content}?level={level}"
            
            # 发送请求
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = resp.read().decode('utf-8')
                logger.debug(f"Bark 通知结果: {result}")
                return True
        except Exception as e:
            logger.error(f"Bark 通知失败: {e}")
            return False


class WebhookNotifier(Notifier):
    """Webhook 通知器"""
    
    def __init__(self, webhook_url: str, method: str = "POST"):
        """
        初始化 Webhook 通知器
        
        Args:
            webhook_url: Webhook URL
            method: HTTP 方法
        """
        self.webhook_url = webhook_url
        self.method = method.upper()
    
    def notify(self, title: str, content: str, **kwargs) -> bool:
        """发送 Webhook 通知"""
        import json
        import urllib.request
        
        try:
            data = json.dumps({
                "title": title,
                "content": content,
                **kwargs
            }).encode('utf-8')
            
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method=self.method
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = resp.read().decode('utf-8')
                logger.debug(f"Webhook 通知结果: {result}")
                return True
        except Exception as e:
            logger.error(f"Webhook 通知失败: {e}")
            return False


class FeishuNotifier(Notifier):
    """飞书消息通知器（应用机器人）"""
    
    def __init__(self, app_id: str, app_secret: str, receive_id: str, receive_id_type: str = "open_id"):
        """
        初始化飞书通知器（应用机器人方式）
        
        Args:
            app_id: 飞书应用 ID
            app_secret: 飞书应用密钥
            receive_id: 接收者 ID
            receive_id_type: 接收者 ID 类型 (open_id, user_id, chat_id)
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.receive_id = receive_id
        self.receive_id_type = receive_id_type
        self._tenant_access_token: Optional[str] = None
        self._token_expire_time: float = 0
    
    def _get_tenant_access_token(self) -> str:
        """获取 tenant_access_token"""
        import json
        import urllib.request
        
        # 检查是否需要刷新 token
        if self._tenant_access_token and time.time() < self._token_expire_time:
            return self._tenant_access_token
        
        try:
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            data = json.dumps({
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }).encode('utf-8')
            
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                
                if result.get("code") == 0:
                    self._tenant_access_token = result["tenant_access_token"]
                    # 提前 5 分钟过期
                    self._token_expire_time = time.time() + result.get("expire", 7200) - 300
                    return self._tenant_access_token
                else:
                    raise Exception(f"获取 token 失败: {result.get('msg')}")
                    
        except Exception as e:
            logger.error(f"获取飞书 token 失败: {e}")
            raise
    
    def notify(self, title: str, content: str, **kwargs) -> bool:
        """
        发送飞书消息
        
        Args:
            title: 消息标题（用作卡片标题）
            content: 消息内容
        """
        import json
        import urllib.request
        
        try:
            token = self._get_tenant_access_token()
            
            # 构造消息内容（使用文本消息）
            message_content = json.dumps({
                "text": f"【{title}】\n\n{content}"
            }, ensure_ascii=False)
            
            # 构造请求体
            data = json.dumps({
                "receive_id": self.receive_id,
                "msg_type": "text",
                "content": message_content
            }, ensure_ascii=False).encode('utf-8')
            
            url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={self.receive_id_type}"
            
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                
                if result.get("code") == 0:
                    logger.debug(f"飞书消息发送成功")
                    return True
                else:
                    logger.error(f"飞书消息发送失败: {result.get('msg')}")
                    return False
                    
        except Exception as e:
            logger.error(f"飞书通知失败: {e}")
            return False


class FeishuWebhookNotifier(Notifier):
    """飞书 Webhook 机器人通知器"""
    
    def __init__(self, webhook_url: str):
        """
        初始化飞书 Webhook 机器人通知器
        
        Args:
            webhook_url: Webhook URL，格式如 https://open.feishu.cn/open-apis/bot/v2/hook/xxx
        """
        self.webhook_url = webhook_url
    
    def notify(self, title: str, content: str, **kwargs) -> bool:
        """
        发送飞书 Webhook 消息
        
        Args:
            title: 消息标题
            content: 消息内容
        """
        import json
        import urllib.request
        
        try:
            # 构造文本消息
            message_text = f"【{title}】\n\n{content}"
            
            data = json.dumps({
                "msg_type": "text",
                "content": {
                    "text": message_text
                }
            }, ensure_ascii=False).encode('utf-8')
            
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                
                if result.get("StatusCode") == 0 or result.get("code") == 0:
                    logger.debug(f"飞书 Webhook 消息发送成功")
                    return True
                else:
                    logger.error(f"飞书 Webhook 消息发送失败: {result}")
                    return False
                    
        except Exception as e:
            logger.error(f"飞书 Webhook 通知失败: {e}")
            return False


class SMSWatcher:
    """
    短信监听器
    
    持续监听 CPE 短信并转发通知
    
    使用方法:
        watcher = SMSWatcher(
            host="http://192.168.1.1",
            username="admin",
            password="password",
            notifiers=[BarkNotifier("your-bark-key")]
        )
        watcher.start()
    """
    
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        notifiers: Optional[List[Notifier]] = None,
        check_interval: float = 3.0,
        on_sms: Optional[Callable[[SMSMessage], None]] = None,
        on_logout: Optional[Callable[[], None]] = None,
        wait_after_logout: float = 600.0
    ):
        """
        初始化短信监听器
        
        Args:
            host: CPE 地址
            username: 用户名
            password: 密码
            notifiers: 通知器列表
            check_interval: 检查间隔（秒）
            on_sms: 收到新短信时的回调函数
            on_logout: 被登出时的回调函数
            wait_after_logout: 被登出后等待时间（秒）
        """
        self.host = host
        self.username = username
        self.password = password
        self.notifiers = notifiers or []
        self.check_interval = check_interval
        self.on_sms = on_sms
        self.on_logout = on_logout
        self.wait_after_logout = wait_after_logout
        
        self._client = CPEClient(host)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_login_time: Optional[float] = None
        self._processed_sms_ids: set = set()  # 已处理的短信 ID
    
    def add_notifier(self, notifier: Notifier):
        """添加通知器"""
        self.notifiers.append(notifier)
    
    def _send_notification(self, sms: SMSMessage):
        """发送通知"""
        title = f"短信来自 {sms.phone}"
        content = sms.content
        
        for notifier in self.notifiers:
            try:
                notifier.notify(title, content, time=sms.time)
                logger.info(f"已发送通知: {title}")
            except Exception as e:
                logger.error(f"发送通知失败: {e}")
    
    def _handle_new_sms(self, sms_list: List[SMSMessage]):
        """处理新短信"""
        for sms in sms_list:
            # 检查是否已处理
            if sms.id in self._processed_sms_ids:
                continue
            
            logger.info(f"新短信: [{sms.time}] {sms.phone}: {sms.content[:50]}...")
            
            # 标记为已处理
            self._processed_sms_ids.add(sms.id)
            
            # 发送通知
            self._send_notification(sms)
            
            # 调用回调
            if self.on_sms:
                try:
                    self.on_sms(sms)
                except Exception as e:
                    logger.error(f"回调函数执行失败: {e}")
    
    def _run(self):
        """运行监听循环"""
        # 首次启动时，处理未读短信并记录所有短信 ID
        try:
            if self._client.login(self.username, self.password)[0]:
                sms_list = self._client.get_sms_list()
                
                # 找出未读短信（接收的且未读的）
                unread_sms = [sms for sms in sms_list if not sms.is_read and not sms.is_sent]
                
                # 发送未读短信通知
                if unread_sms:
                    logger.info(f"发现 {len(unread_sms)} 条未读短信")
                    self._handle_new_sms(unread_sms)
                
                # 记录所有短信 ID（避免重复通知）
                for sms in sms_list:
                    if sms.id:
                        self._processed_sms_ids.add(sms.id)
                
                logger.info(f"已记录 {len(self._processed_sms_ids)} 条短信 ID")
                self._client.logout()
        except Exception as e:
            logger.warning(f"初始化短信缓存失败: {e}")
        
        while self._running:
            try:
                # 登录
                if not self._client.is_logged_in():
                    logger.info("尝试登录...")
                    success, message = self._client.login(self.username, self.password)
                    
                    if not success:
                        logger.warning(f"登录失败: {message}")
                        time.sleep(self.wait_after_logout)
                        continue
                    
                    self._last_login_time = time.time()
                    logger.info("登录成功")
                
                # 检查心跳
                heartbeat_ok = self._client.heartbeat()
                logger.debug(f"心跳结果: {heartbeat_ok}")
                
                if not heartbeat_ok:
                    logger.warning("心跳失败，可能被登出")
                    
                    # 调用回调
                    if self.on_logout:
                        self.on_logout()
                    
                    # 判断是否需要等待
                    if self._last_login_time:
                        elapsed = time.time() - self._last_login_time
                        # 如果是会话过期（4-5分钟），立即重新登录
                        if 4 * 60 < elapsed < 5 * 60:
                            logger.info("会话过期，立即重新登录")
                        else:
                            logger.info(f"被其他用户登出，等待 {self.wait_after_logout} 秒后重试")
                            time.sleep(self.wait_after_logout)
                    
                    continue
                
                # 检查新短信（直接获取短信列表）
                sms_list = self._client.get_sms_list()
                if sms_list:
                    # 过滤出未处理的短信
                    new_sms = [sms for sms in sms_list if sms.id and sms.id not in self._processed_sms_ids]
                    if new_sms:
                        self._handle_new_sms(new_sms)
                
                # 等待下次检查
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"监听出错: {e}")
                time.sleep(5)
    
    def start(self, blocking: bool = True):
        """
        启动监听
        
        Args:
            blocking: 是否阻塞当前线程
        """
        self._running = True
        
        if blocking:
            self._run()
        else:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
    
    def stop(self):
        """停止监听"""
        self._running = False
        
        if self._thread:
            self._thread.join(timeout=5)
        
        try:
            self._client.logout()
        except:
            pass
        
        logger.info("已停止监听")
    
    def __enter__(self):
        self.start(blocking=False)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
