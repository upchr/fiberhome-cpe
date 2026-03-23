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
        self.session.headers.update({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/json; charset=utf-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.base_url}/main.html",
            "Origin": self.base_url
        })
        self._logged_in = False
        
    def _get_sessionid(self) -> str:
        """获取新的 sessionid"""
        url = f"{self.base_url}/api/tmp/FHNCAPIS?ajaxmethod=get_refresh_sessionid"
        resp = self.session.get(url, timeout=30)
        data = resp.json()
        return data.get("sessionid", "")
    
    def _api_get(self, path: str) -> str:
        """
        发送 GET 请求
        
        Args:
            path: API 路径，如 "IS_LOGGED_IN" 或 "heartbeat"
        """
        url = f"{self.base_url}/api/tmp/{path}"
        resp = self.session.get(url, timeout=30)
        return resp.text.strip()
    
    def _api_post_nocheck(self, method_name: str, data: Any = None) -> Dict[str, Any]:
        """
        发送 POST 请求到 FHNCAPIS（不需要验证）
        
        Args:
            method_name: API 方法名
            data: 请求数据
        """
        sessionid = self._get_sessionid()
        
        body = {
            "dataObj": data,
            "ajaxmethod": method_name,
            "sessionid": sessionid
        }
        body_json = json.dumps(body, ensure_ascii=False)
        encrypted = AESEncryptor.encrypt(body_json, sessionid[:16])
        
        url = f"{self.base_url}/api/tmp/FHNCAPIS?ajaxmethod={method_name}"
        resp = self.session.post(url, data=encrypted, timeout=30)
        
        if resp.text.strip():
            try:
                decrypted = AESEncryptor.decrypt(resp.text.strip(), sessionid[:16])
                return json.loads(decrypted)
            except:
                pass
        return {}
    
    def _api_post_encrypted(self, method_name: str, data: Dict[str, str]) -> Dict[str, Any]:
        """
        发送加密的 POST 请求到 FHAPIS
        
        用于获取敏感数据（温度、信号、SIM 信息等）
        
        Args:
            method_name: API 方法名，如 "get_value_by_xmlnode"
            data: XML 路径字典，如 {"Temperature": "X_FH_MobileNetwork.Temperature.Modem5GTemperature"}
            
        Returns:
            解密后的响应数据
        """
        sessionid = self._get_sessionid()
        
        body = {
            "dataObj": data,
            "ajaxmethod": method_name,
            "sessionid": sessionid
        }
        body_json = json.dumps(body, ensure_ascii=False)
        encrypted = AESEncryptor.encrypt(body_json, sessionid[:16])
        
        url = f"{self.base_url}/api/tmp/FHAPIS?_={int(time.time() * 1000)}"
        resp = self.session.post(url, data=encrypted, timeout=30)
        
        if resp.text.strip():
            try:
                decrypted = AESEncryptor.decrypt(resp.text.strip(), sessionid[:16])
                return json.loads(decrypted)
            except Exception as e:
                logger.error(f"解密失败: {e}")
        return {}
    
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
        sessionid = self._get_sessionid()
        if not sessionid:
            return False, "获取 sessionid 失败"
        
        body = {
            "dataObj": {"username": username, "password": password},
            "ajaxmethod": "DO_WEB_LOGIN",
            "sessionid": sessionid
        }
        body_json = json.dumps(body, ensure_ascii=False)
        encrypted = AESEncryptor.encrypt(body_json, sessionid[:16])
        
        url = f"{self.base_url}/api/sign/DO_WEB_LOGIN?_={int(time.time() * 1000)}"
        resp = self.session.post(url, data=encrypted, timeout=30)
        
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
            result = self._api_get("IS_LOGGED_IN")
            return result == "1"
        except:
            return False
    
    def heartbeat(self) -> bool:
        """发送心跳"""
        try:
            result = self._api_get("heartbeat")
            return result == "true"
        except:
            return False
    
    # ==================== 设备信息 ====================
    
    def get_device_info(self) -> DeviceInfo:
        """获取设备基本信息"""
        try:
            data = self._api_post_nocheck("get_device_info")
            return DeviceInfo.from_dict(data)
        except Exception as e:
            logger.error(f"获取设备信息失败: {e}")
        return DeviceInfo()
    
    def get_device_details(self) -> Dict[str, Any]:
        """
        获取设备详细信息（温度、CPU、内存、运行时间等）
        
        Returns:
            {
                "Modem5GTemperature": "35513",  # 需除以 1000
                "Modem4GTemperature": "36904",  # 需除以 1000
                "SerialNumber": "MTRTGJ401781ACAB20",
                "SoftwareVersion": "RP0204",
                "HardwareVersion": "WKE2.094.408A01",
                "CPUUsage": "29",
                "MemoryTotal": "1048576",
                "MemoryFree": "458334",
                "UpTime": "1469051"  # 秒
            }
        """
        xml_paths = {
            "Modem5GTemperature": "X_FH_MobileNetwork.Temperature.Modem5GTemperature",
            "Modem4GTemperature": "X_FH_MobileNetwork.Temperature.Modem4GTemperature",
            "SerialNumber": "DeviceInfo.SerialNumber",
            "SoftwareVersion": "DeviceInfo.SoftwareVersion",
            "HardwareVersion": "DeviceInfo.HardwareVersion",
            "ModelName": "DeviceInfo.ModelName",
            "Manufacturer": "DeviceInfo.Manufacturer",
            "CPUUsage": "DeviceInfo.ProcessStatus.CPUUsage",
            "MemoryTotal": "DeviceInfo.MemoryStatus.Total",
            "MemoryFree": "DeviceInfo.MemoryStatus.Free",
            "UpTime": "DeviceInfo.UpTime"
        }
        
        try:
            return self._api_post_encrypted("get_value_by_xmlnode", xml_paths)
        except Exception as e:
            logger.error(f"获取设备详细信息失败: {e}")
            return {}
    
    def get_temperature(self) -> Dict[str, float]:
        """
        获取温度信息
        
        Returns:
            {"5g": 35.5, "4g": 36.9} 温度单位：摄氏度
        """
        data = self.get_device_details()
        result = {}
        
        for key, xml_key in [("5g", "Modem5GTemperature"), ("4g", "Modem4GTemperature")]:
            val = data.get(xml_key)
            if val:
                try:
                    result[key] = int(val) / 1000
                except:
                    pass
        
        return result
    
    def get_system_usage(self) -> Dict[str, float]:
        """
        获取系统使用率
        
        Returns:
            {"cpu": 29.0, "memory": 56.29} 单位：百分比
        """
        data = self.get_device_details()
        result = {}
        
        cpu = data.get("CPUUsage")
        if cpu:
            try:
                result["cpu"] = float(cpu)
            except:
                pass
        
        mem_total = data.get("MemoryTotal")
        mem_free = data.get("MemoryFree")
        if mem_total and mem_free:
            try:
                result["memory"] = (int(mem_total) - int(mem_free)) / int(mem_total) * 100
            except:
                pass
        
        return result
    
    def get_uptime(self) -> Dict[str, int]:
        """
        获取运行时间
        
        Returns:
            {"days": 17, "hours": 0, "minutes": 4, "seconds": 11, "total_seconds": 1469051}
        """
        data = self.get_device_details()
        
        uptime = data.get("UpTime")
        if uptime:
            try:
                seconds = int(uptime)
                return {
                    "days": seconds // 86400,
                    "hours": (seconds % 86400) // 3600,
                    "minutes": (seconds % 3600) // 60,
                    "seconds": seconds % 60,
                    "total_seconds": seconds
                }
            except:
                pass
        
        return {}
    
    # ==================== SIM 卡信息 ====================
    
    def get_sim_info(self) -> Dict[str, Any]:
        """
        获取 SIM 卡信息
        
        Returns:
            {
                "SIMStatus": "1",  # 1=正常
                "IMEI": "868927053245678",
                "IMSI": "460011234567890",
                "NetworkMode": "3",  # 1=3G, 2=4G, 3=5G
                "CarrierName": "中国移动",
                "PhoneNumber": "13800138000",
                "RegisterStatus": "1"  # 1=已注册
            }
        """
        xml_paths = {
            "SIMStatus": "X_FH_MobileNetwork.SIM.1.SIMStatus",
            "IMEI": "X_FH_MobileNetwork.SIM.1.IMEI",
            "IMSI": "X_FH_MobileNetwork.SIM.1.IMSI",
            "NetworkMode": "X_FH_MobileNetwork.SIM.1.NetworkMode",
            "CarrierName": "X_FH_MobileNetwork.SIM.1.CarrierName",
            "PhoneNumber": "X_FH_MobileNetwork.SIM.1.PhoneNumber",
            "RegisterStatus": "X_FH_MobileNetwork.SIM.1.RegisterStatus",
            "RoamingConnectStatus": "X_FH_MobileNetwork.SIM.1.RoamingConnectStatus"
        }
        
        try:
            return self._api_post_encrypted("get_value_by_xmlnode", xml_paths)
        except Exception as e:
            logger.error(f"获取 SIM 信息失败: {e}")
            return {}
    
    # ==================== 信号信息 ====================
    
    def get_signal_info(self) -> Dict[str, Any]:
        """
        获取信号信息
        
        Returns:
            {
                "RSRP": "-85",  # dBm
                "RSSI": "-65",  # dBm
                "SINR": "15",   # dB
                "RSRQ": "-10",  # dB
                "BAND": "41",   # 频段
                "PCI": "123",   # 物理小区ID
                "WorkMode": "SA",  # 工作模式
                ...
            }
        """
        xml_paths = {
            "RSRP": "X_FH_MobileNetwork.RadioSignalParameter.RSRP",
            "RSSI": "X_FH_MobileNetwork.RadioSignalParameter.RSSI",
            "SINR": "X_FH_MobileNetwork.RadioSignalParameter.SINR",
            "RSRQ": "X_FH_MobileNetwork.RadioSignalParameter.RSRQ",
            "BAND": "X_FH_MobileNetwork.RadioSignalParameter.BAND",
            "PCI": "X_FH_MobileNetwork.RadioSignalParameter.PCI",
            "WorkMode": "X_FH_MobileNetwork.RadioSignalParameter.WorkMode",
            "SSB_RSRP": "X_FH_MobileNetwork.RadioSignalParameter.SSB_RSRP",
            "SSB_SINR": "X_FH_MobileNetwork.RadioSignalParameter.SSB_SINR",
            "NR_Band": "X_FH_MobileNetwork.RadioSignalParameter.NR_Band",
            "NR_Power": "X_FH_MobileNetwork.RadioSignalParameter.NR_Power",
            "LTE_Power": "X_FH_MobileNetwork.RadioSignalParameter.LTE_Power",
            "NetworkMode": "X_FH_MobileNetwork.SIM.1.NetworkMode"
        }
        
        try:
            return self._api_post_encrypted("get_value_by_xmlnode", xml_paths)
        except Exception as e:
            logger.error(f"获取信号信息失败: {e}")
            return {}
    
    # ==================== 网络流量 ====================
    
    def get_traffic_stats(self) -> Dict[str, Any]:
        """
        获取流量统计
        
        Returns:
            {
                "TodayTotalTxBytes": "1234567890",  # 今日发送字节
                "TodayTotalRxBytes": "9876543210",  # 今日接收字节
                "MonthTxBytes": "12345678901234",   # 本月发送字节
                "MonthRxBytes": "98765432109876"    # 本月接收字节
            }
        """
        xml_paths = {
            "TodayTotalTxBytes": "X_FH_MobileNetwork.TrafficStats.TodayTotalTxBytes",
            "TodayTotalRxBytes": "X_FH_MobileNetwork.TrafficStats.TodayTotalRxBytes",
            "TodayTotalBytes": "X_FH_MobileNetwork.TrafficStats.TodayTotalBytes",
            "MonthTxBytes": "X_FH_MobileNetwork.TrafficStats.MonthTxBytes",
            "MonthRxBytes": "X_FH_MobileNetwork.TrafficStats.MonthRxBytes",
            "MonthTotalBytes": "X_FH_MobileNetwork.TrafficStats.MonthTotalBytes"
        }
        
        try:
            return self._api_post_encrypted("get_value_by_xmlnode", xml_paths)
        except Exception as e:
            logger.error(f"获取流量统计失败: {e}")
            return {}
    
    # ==================== 短信管理 ====================
    
    def get_new_sms_flag(self) -> bool:
        """检查是否有新短信"""
        try:
            url = f"{self.base_url}/api/tmp/FHNCAPIS?ajaxmethod=get_new_sms"
            resp = self.session.get(url, timeout=30)
            data = resp.json()
            return data.get("new_sms_flag", "false") == "true"
        except:
            return False
    
    def get_sms_list(self) -> List[SMSMessage]:
        """获取短信列表"""
        try:
            sessionid = self._get_sessionid()
            
            body = {
                "dataObj": None,
                "ajaxmethod": "get_sms_data",
                "sessionid": sessionid
            }
            encrypted = AESEncryptor.encrypt(json.dumps(body), sessionid[:16])
            
            url = f"{self.base_url}/api/tmp/FHAPIS?_={int(time.time() * 1000)}"
            resp = self.session.post(url, data=encrypted, timeout=30)
            
            if resp.text.strip():
                decrypted = AESEncryptor.decrypt(resp.text.strip(), sessionid[:16])
                data = json.loads(decrypted)
                
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
            # 使用 set_value_by_xmlnode API
            sessionid = self._get_sessionid()
            
            body = {
                "dataObj": {
                    "url": {
                        f"sms{sms_id}": f"InternetGatewayDevice.X_FH_MobileNetwork.SMS_Recv.SMS_RecvMsg.{sms_id}.isOpened"
                    },
                    "value": {
                        f"sms{sms_id}": "1"
                    }
                },
                "ajaxmethod": "set_value_by_xmlnode",
                "sessionid": sessionid
            }
            encrypted = AESEncryptor.encrypt(json.dumps(body), sessionid[:16])
            
            url = f"{self.base_url}/api/tmp/FHAPIS?_={int(time.time() * 1000)}"
            self.session.post(url, data=encrypted, timeout=30)
            return True
        except Exception as e:
            logger.error(f"标记短信已读失败: {e}")
            return False
    
    # ==================== 系统操作 ====================
    
    def reboot(self) -> bool:
        """重启路由器"""
        try:
            # 重启需要特殊的 API
            sessionid = self._get_sessionid()
            
            body = {
                "dataObj": None,
                "ajaxmethod": "reboot_device",
                "sessionid": sessionid
            }
            encrypted = AESEncryptor.encrypt(json.dumps(body), sessionid[:16])
            
            url = f"{self.base_url}/api/tmp/FHAPIS?_={int(time.time() * 1000)}"
            self.session.post(url, data=encrypted, timeout=30)
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
