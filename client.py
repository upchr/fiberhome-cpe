"""
CPE API 客户端

实现烽火 5G CPE 路由器的完整 API 调用
"""

import requests
import json
import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urljoin

from crypto import AESEncryptor
from models import (
    DeviceInfo, SMSMessage, WiFiInfo, ConnectedDevice, 
    SignalInfo, DataUsage, NetworkInfo
)

logger = logging.getLogger(__name__)


class CPEClient:
    """
    烽火 5G CPE 路由器 API 客户端
    
    使用方法:
        client = CPEClient("http://192.168.1.1")
        client.login("admin", "password")
        
        # 获取设备信息
        info = client.get_device_info()
        
        # 获取短信
        sms_list = client.get_sms_list()
        
        # 登出
        client.logout()
    """
    
    def __init__(self, base_url: str = "http://192.168.1.1"):
        """
        初始化客户端
        
        Args:
            base_url: 路由器地址，如 http://192.168.1.1
        """
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._logged_in = False
        
    def _get_sessionid(self) -> str:
        """获取新的 sessionid"""
        url = f"{self.base_url}/api/tmp/FHNCAPIS?ajaxmethod=get_refresh_sessionid"
        resp = self.session.get(url, timeout=30)
        data = resp.json()
        return data.get("sessionid", "")
    
    def _api_get(self, method_name: str, no_check: bool = False) -> str:
        """
        发送 GET 请求到 API
        
        Args:
            method_name: API 方法名
            no_check: 是否使用不检查的 API 路径
        """
        path = f"/api/tmp/FH{'NC' if no_check else ''}APIS?ajaxmethod={method_name}"
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, timeout=30)
        return resp.text.strip()
    
    def _api_post(self, method_name: str, data: Any = None) -> str:
        """
        发送加密的 POST 请求到 API
        
        Args:
            method_name: API 方法名
            data: 请求数据
        """
        # 获取新的 sessionid
        sessionid = self._get_sessionid()
        
        # 构造请求体
        body = {
            "dataObj": data,
            "ajaxmethod": method_name,
            "sessionid": sessionid
        }
        body_json = json.dumps(body, ensure_ascii=False)
        
        # 加密
        encrypted = AESEncryptor.encrypt(body_json, sessionid[:16])
        
        # 发送请求
        url = f"{self.base_url}/api/tmp/FHAPIS?ajaxmethod={method_name}"
        resp = self.session.post(url, data=encrypted, headers={
            "Content-Type": "application/json"
        }, timeout=30)
        
        # 解密响应
        if resp.text.strip():
            try:
                return AESEncryptor.decrypt(resp.text.strip(), sessionid[:16])
            except Exception as e:
                logger.debug(f"解密失败: {e}")
                return resp.text.strip()
        return ""
    
    # ==================== 登录/登出 ====================
    
    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """
        登录路由器
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            (是否成功, 消息)
        """
        # 获取 sessionid
        sessionid = self._get_sessionid()
        if not sessionid:
            return False, "获取 sessionid 失败"
        
        # 构造请求体
        body = {
            "dataObj": {"username": username, "password": password},
            "ajaxmethod": "DO_WEB_LOGIN",
            "sessionid": sessionid
        }
        body_json = json.dumps(body, ensure_ascii=False)
        
        # 加密并发送
        encrypted = AESEncryptor.encrypt(body_json, sessionid[:16])
        url = f"{self.base_url}/api/sign/DO_WEB_LOGIN?_={int(time.time() * 1000)}"
        resp = self.session.post(url, data=encrypted, headers={
            "Content-Type": "application/json"
        }, timeout=30)
        
        result = resp.text.strip()
        parts = result.split("|")
        
        if len(parts) >= 2:
            status = parts[0]
            
            error_messages = {
                "0": "登录成功",
                "1": "已有用户在其他地方登录",
                "2": "连续错误登录次数达到3次，请1分钟后再试",
                "3": "管理账号已被禁用",
                "4": "用户名或密码错误",
                "5": "未知错误"
            }
            
            self._logged_in = status == "0"
            return self._logged_in, error_messages.get(status, f"未知状态: {status}")
        
        return False, f"解析响应失败: {result}"
    
    def logout(self) -> bool:
        """登出路由器"""
        try:
            url = f"{self.base_url}/api/sign/DO_WEB_LOGOUT?_={int(time.time() * 1000)}"
            self.session.post(url, timeout=30)
            self._logged_in = False
            return True
        except:
            return False
    
    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            url = f"{self.base_url}/api/tmp/IS_LOGGED_IN"
            resp = self.session.get(url, timeout=30)
            return resp.text.strip() == "1"
        except:
            return False
    
    def heartbeat(self) -> bool:
        """发送心跳"""
        try:
            url = f"{self.base_url}/api/tmp/heartbeat"
            resp = self.session.get(url, timeout=30)
            return resp.text.strip() == "true"
        except:
            return False
    
    # ==================== 设备信息 ====================
    
    def get_device_info(self) -> DeviceInfo:
        """获取设备信息"""
        try:
            result = self._api_get("get_device_info", no_check=True)
            if result:
                data = json.loads(result)
                return DeviceInfo.from_dict(data)
        except Exception as e:
            logger.error(f"获取设备信息失败: {e}")
        return DeviceInfo()
    
    def get_cpe_status(self) -> Dict[str, Any]:
        """
        获取 CPE 完整状态信息
        
        返回设备信息页面的所有数据，包括：
        - 产品名称、型号、序列号
        - 软件版本、硬件版本
        - 运行时间、CPU 温度
        - LAN IP 等
        """
        try:
            result = self._api_get("get_device_info", no_check=True)
            if result:
                return json.loads(result)
        except Exception as e:
            logger.error(f"获取 CPE 状态失败: {e}")
        return {}
    
    def get_runtime(self) -> str:
        """
        获取设备运行时间
        
        Returns:
            运行时间字符串，如 "16天 22小时 12分钟 42秒"
        """
        try:
            result = self._api_get("get_device_info", no_check=True)
            if result:
                data = json.loads(result)
                # 运行时间可能在 uptime 或 runtime 字段
                return data.get("uptime", data.get("runtime", ""))
        except Exception as e:
            logger.error(f"获取运行时间失败: {e}")
        return ""
    
    def get_cpu_temperature(self) -> str:
        """
        获取 CPU 温度
        
        Returns:
            CPU 温度字符串，如 "35.5 ℃"
        """
        try:
            result = self._api_get("get_device_info", no_check=True)
            if result:
                data = json.loads(result)
                return data.get("cpu_temp", data.get("temperature", ""))
        except Exception as e:
            logger.error(f"获取 CPU 温度失败: {e}")
        return ""
    
    # ==================== 网络状态 ====================
    
    def get_signal_info(self) -> SignalInfo:
        """获取信号信息"""
        try:
            result = self._api_post("get_signal_info")
            data = json.loads(result)
            return SignalInfo.from_dict(data)
        except Exception as e:
            logger.error(f"获取信号信息失败: {e}")
            return SignalInfo()
    
    def get_network_info(self) -> NetworkInfo:
        """获取网络信息"""
        try:
            result = self._api_post("get_network_info")
            data = json.loads(result)
            return NetworkInfo.from_dict(data)
        except Exception as e:
            logger.error(f"获取网络信息失败: {e}")
            return NetworkInfo()
    
    # ==================== 短信管理 ====================
    
    def get_new_sms_flag(self) -> bool:
        """检查是否有新短信"""
        try:
            result = self._api_get("get_new_sms")
            data = json.loads(result)
            return data.get("new_sms_flag", "false") == "true"
        except:
            return False
    
    def get_sms_list(self) -> List[SMSMessage]:
        """获取短信列表"""
        try:
            result = self._api_post("get_sms_data")
            data = json.loads(result)
            
            messages = []
            for session_id, session_data in data.items():
                if isinstance(session_data, dict):
                    phone = session_data.get("session_phone", "")
                    for msg_id, msg_data in session_data.items():
                        if isinstance(msg_data, dict) and "msg_content" in msg_data:
                            messages.append(SMSMessage.from_dict(msg_data, phone))
            
            return messages
        except Exception as e:
            logger.error(f"获取短信列表失败: {e}")
            return []
    
    def get_unread_sms(self) -> List[SMSMessage]:
        """获取未读短信"""
        all_sms = self.get_sms_list()
        return [sms for sms in all_sms if not sms.is_read and not sms.is_sent]
    
    def mark_sms_read(self, sms_id: str) -> bool:
        """标记短信为已读"""
        try:
            data = {
                "url": {
                    f"smsIsopend{sms_id}": f"InternetGatewayDevice.X_FH_MobileNetwork.SMS_Recv.SMS_RecvMsg.{sms_id}.isOpened"
                },
                "value": {
                    f"smsIsopend{sms_id}": "1"
                }
            }
            self._api_post("set_value_by_xmlnode", data)
            return True
        except Exception as e:
            logger.error(f"标记短信已读失败: {e}")
            return False
    
    # ==================== WiFi 管理 ====================
    
    def get_wifi_info(self) -> WiFiInfo:
        """获取 WiFi 信息"""
        try:
            result = self._api_post("get_wifi_info")
            data = json.loads(result)
            return WiFiInfo.from_dict(data)
        except Exception as e:
            logger.error(f"获取 WiFi 信息失败: {e}")
            return WiFiInfo()
    
    # ==================== 连接设备 ====================
    
    def get_connected_devices(self) -> List[ConnectedDevice]:
        """获取已连接设备列表"""
        try:
            result = self._api_post("get_station_list")
            data = json.loads(result)
            
            devices = []
            if isinstance(data, dict) and "data" in data:
                for item in data["data"]:
                    devices.append(ConnectedDevice.from_dict(item))
            elif isinstance(data, list):
                for item in data:
                    devices.append(ConnectedDevice.from_dict(item))
            
            return devices
        except Exception as e:
            logger.error(f"获取连接设备失败: {e}")
            return []
    
    # ==================== 系统操作 ====================
    
    def reboot(self) -> bool:
        """重启路由器"""
        try:
            self._api_post("reboot_device")
            return True
        except Exception as e:
            logger.error(f"重启失败: {e}")
            return False
    
    # ==================== 上下文管理器 ====================
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()
        return False
