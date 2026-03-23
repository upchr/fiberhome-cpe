"""
CPE API 客户端

实现烽火 5G CPE 路由器的完整 API 调用
"""

import requests
import json
import time
import logging
from typing import Dict, Any, List, Tuple

from crypto import AESEncryptor
from models import DeviceInfo, SMSMessage

logger = logging.getLogger(__name__)


class CPEClient:
    """
    烽火 5G CPE 路由器 API 客户端
    
    API 类型说明：
    - FHNCAPIS: 不需要验证，用于 get_device_info
    - FHAPIS: 需要验证，用于 get_value_by_xmlnode（温度、信号等敏感数据）
    
    使用方法:
        client = CPEClient("http://192.168.1.1")
        client.login("admin", "password")
        
        temp = client.get_temperature()
        print(f"5G 温度: {temp['5g']}°C")
        
        client.logout()
    """
    
    def __init__(self, base_url: str = "http://192.168.1.1"):
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
        
    # ==================== 核心 API 方法 ====================
    
    def _get_sessionid(self) -> str:
        """获取新的 sessionid"""
        url = f"{self.base_url}/api/tmp/FHNCAPIS?ajaxmethod=get_refresh_sessionid"
        resp = self.session.get(url, timeout=30)
        return resp.json().get("sessionid", "")
    
    def _api_get(self, path: str) -> str:
        """GET 请求（心跳、登录状态）"""
        return self.session.get(f"{self.base_url}/api/tmp/{path}", timeout=30).text.strip()
    
    def _api_nocheck(self, method: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        FHNCAPIS - 不需要验证的 API
        用于 get_device_info
        """
        sid = self._get_sessionid()
        body = {"dataObj": data, "ajaxmethod": method, "sessionid": sid}
        encrypted = AESEncryptor.encrypt(json.dumps(body, ensure_ascii=False), sid[:16])
        
        url = f"{self.base_url}/api/tmp/FHNCAPIS?ajaxmethod={method}"
        resp = self.session.post(url, data=encrypted, timeout=30)
        
        if resp.text.strip():
            try:
                decrypted = AESEncryptor.decrypt(resp.text.strip(), sid[:16])
                return json.loads(decrypted)
            except:
                pass
        return {}
    
    def _api_encrypted(self, method: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        FHAPIS - 需要验证的加密 API
        用于 get_value_by_xmlnode（温度、信号、SIM信息等）
        """
        sid = self._get_sessionid()
        body = {"dataObj": data, "ajaxmethod": method, "sessionid": sid}
        encrypted = AESEncryptor.encrypt(json.dumps(body, ensure_ascii=False), sid[:16])
        
        url = f"{self.base_url}/api/tmp/FHAPIS?_={int(time.time() * 1000)}"
        resp = self.session.post(url, data=encrypted, timeout=30)
        
        if resp.text.strip():
            try:
                decrypted = AESEncryptor.decrypt(resp.text.strip(), sid[:16])
                return json.loads(decrypted)
            except Exception as e:
                logger.debug(f"解密失败: {e}")
        return {}
    
    # ==================== 登录/登出 ====================
    
    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """登录路由器"""
        sid = self._get_sessionid()
        if not sid:
            return False, "获取 sessionid 失败"
        
        body = {"dataObj": {"username": username, "password": password}, "ajaxmethod": "DO_WEB_LOGIN", "sessionid": sid}
        encrypted = AESEncryptor.encrypt(json.dumps(body, ensure_ascii=False), sid[:16])
        resp = self.session.post(f"{self.base_url}/api/sign/DO_WEB_LOGIN?_={int(time.time() * 1000)}", data=encrypted, timeout=30)
        
        parts = resp.text.strip().split("|")
        if len(parts) >= 2:
            status = parts[0]
            messages = {"0": "登录成功", "1": "已有用户在其他地方登录", "2": "连续错误登录次数达到3次，请1分钟后再试", "3": "管理账号已被禁用", "4": "用户名或密码错误"}
            self._logged_in = status == "0"
            return self._logged_in, messages.get(status, f"未知状态: {status}")
        return False, f"解析响应失败: {resp.text}"
    
    def logout(self) -> bool:
        """登出路由器"""
        try:
            self.session.post(f"{self.base_url}/api/sign/DO_WEB_LOGOUT?_={int(time.time() * 1000)}", timeout=30)
            self._logged_in = False
            return True
        except:
            return False
    
    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return self._api_get("IS_LOGGED_IN") == "1"
    
    def heartbeat(self) -> bool:
        """发送心跳"""
        return self._api_get("heartbeat") == "true"
    
    # ==================== 设备信息 ====================
    
    def get_device_info(self) -> DeviceInfo:
        """获取设备基本信息（型号、MAC 地址等）"""
        data = self._api_nocheck("get_device_info")
        return DeviceInfo.from_dict(data)
    
    def get_temperature(self) -> Dict[str, float]:
        """获取温度，返回 {"5g": 35.5, "4g": 36.9} 单位：摄氏度"""
        data = self._api_encrypted("get_value_by_xmlnode", {
            "Modem5GTemperature": "X_FH_MobileNetwork.Temperature.Modem5GTemperature",
            "Modem4GTemperature": "X_FH_MobileNetwork.Temperature.Modem4GTemperature"
        })
        result = {}
        for key, xml_key in [("5g", "Modem5GTemperature"), ("4g", "Modem4GTemperature")]:
            if data.get(xml_key):
                try:
                    result[key] = int(data[xml_key]) / 1000
                except:
                    pass
        return result
    
    def get_system_usage(self) -> Dict[str, float]:
        """获取系统使用率，返回 {"cpu": 29.0, "memory": 56.29} 单位：百分比"""
        data = self._api_encrypted("get_value_by_xmlnode", {
            "CPUUsage": "DeviceInfo.ProcessStatus.CPUUsage",
            "MemoryTotal": "DeviceInfo.MemoryStatus.Total",
            "MemoryFree": "DeviceInfo.MemoryStatus.Free"
        })
        result = {}
        if data.get("CPUUsage"):
            try:
                result["cpu"] = float(data["CPUUsage"])
            except:
                pass
        if data.get("MemoryTotal") and data.get("MemoryFree"):
            try:
                result["memory"] = (int(data["MemoryTotal"]) - int(data["MemoryFree"])) / int(data["MemoryTotal"]) * 100
            except:
                pass
        return result
    
    def get_uptime(self) -> Dict[str, int]:
        """获取运行时间，返回 {"days": 17, "hours": 0, "minutes": 4, "seconds": 11}"""
        data = self._api_encrypted("get_value_by_xmlnode", {"UpTime": "DeviceInfo.UpTime"})
        if data.get("UpTime"):
            try:
                seconds = int(data["UpTime"])
                return {"days": seconds // 86400, "hours": (seconds % 86400) // 3600, "minutes": (seconds % 3600) // 60, "seconds": seconds % 60, "total_seconds": seconds}
            except:
                pass
        return {}
    
    def get_device_details(self) -> Dict[str, Any]:
        """获取设备详细信息（温度、序列号、版本、CPU、内存、运行时间）"""
        return self._api_encrypted("get_value_by_xmlnode", {
            "Modem5GTemperature": "X_FH_MobileNetwork.Temperature.Modem5GTemperature",
            "Modem4GTemperature": "X_FH_MobileNetwork.Temperature.Modem4GTemperature",
            "SerialNumber": "DeviceInfo.SerialNumber",
            "SoftwareVersion": "DeviceInfo.SoftwareVersion",
            "HardwareVersion": "DeviceInfo.HardwareVersion",
            "ModelName": "DeviceInfo.ModelName",
            "CPUUsage": "DeviceInfo.ProcessStatus.CPUUsage",
            "MemoryTotal": "DeviceInfo.MemoryStatus.Total",
            "MemoryFree": "DeviceInfo.MemoryStatus.Free",
            "UpTime": "DeviceInfo.UpTime"
        })
    
    # ==================== SIM 卡信息 ====================
    
    def get_sim_info(self) -> Dict[str, Any]:
        """获取 SIM 卡信息，NetworkMode: 1=3G, 2=4G, 3=5G"""
        return self._api_encrypted("get_value_by_xmlnode", {
            "SIMStatus": "X_FH_MobileNetwork.SIM.1.SIMStatus",
            "IMEI": "X_FH_MobileNetwork.SIM.1.IMEI",
            "IMSI": "X_FH_MobileNetwork.SIM.1.IMSI",
            "NetworkMode": "X_FH_MobileNetwork.SIM.1.NetworkMode",
            "CarrierName": "X_FH_MobileNetwork.SIM.1.CarrierName",
            "PhoneNumber": "X_FH_MobileNetwork.SIM.1.PhoneNumber",
            "RegisterStatus": "X_FH_MobileNetwork.SIM.1.RegisterStatus"
        })
    
    # ==================== 信号信息 ====================
    
    def get_signal_info(self) -> Dict[str, Any]:
        """获取信号信息，RSRP/RSSI 单位：dBm，SINR 单位：dB"""
        return self._api_encrypted("get_value_by_xmlnode", {
            "RSRP": "X_FH_MobileNetwork.RadioSignalParameter.RSRP",
            "RSSI": "X_FH_MobileNetwork.RadioSignalParameter.RSSI",
            "SINR": "X_FH_MobileNetwork.RadioSignalParameter.SINR",
            "RSRQ": "X_FH_MobileNetwork.RadioSignalParameter.RSRQ",
            "BAND": "X_FH_MobileNetwork.RadioSignalParameter.BAND",
            "PCI": "X_FH_MobileNetwork.RadioSignalParameter.PCI",
            "SSB_RSRP": "X_FH_MobileNetwork.RadioSignalParameter.SSB_RSRP",
            "NR_Band": "X_FH_MobileNetwork.RadioSignalParameter.NR_Band",
            "NR_Power": "X_FH_MobileNetwork.RadioSignalParameter.NR_Power",
            "LTE_Power": "X_FH_MobileNetwork.RadioSignalParameter.LTE_Power"
        })
    
    # ==================== 流量统计 ====================
    
    def get_traffic_stats(self) -> Dict[str, Any]:
        """获取流量统计，单位：字节"""
        return self._api_encrypted("get_value_by_xmlnode", {
            "TodayTotalTxBytes": "X_FH_MobileNetwork.TrafficStats.TodayTotalTxBytes",
            "TodayTotalRxBytes": "X_FH_MobileNetwork.TrafficStats.TodayTotalRxBytes",
            "MonthTxBytes": "X_FH_MobileNetwork.TrafficStats.MonthTxBytes",
            "MonthRxBytes": "X_FH_MobileNetwork.TrafficStats.MonthRxBytes"
        })
    
    # ==================== 短信管理 ====================
    
    def get_sms_list(self) -> List[SMSMessage]:
        """获取短信列表"""
        data = self._api_encrypted("get_sms_data")
        messages = []
        for session_id, session_data in data.items():
            if isinstance(session_data, dict):
                phone = session_data.get("session_phone", "")
                for msg_id, msg_data in session_data.items():
                    if isinstance(msg_data, dict) and "msg_content" in msg_data:
                        messages.append(SMSMessage.from_dict(msg_data, phone))
        return messages
    
    def get_unread_sms(self) -> List[SMSMessage]:
        """获取未读短信"""
        return [sms for sms in self.get_sms_list() if not sms.is_read and not sms.is_sent]
    
    def has_new_sms(self) -> bool:
        """检查是否有新短信（通过比较短信数量）"""
        # get_new_sms API 返回 403，改用获取短信列表判断
        sms_list = self.get_sms_list()
        return len(sms_list) > 0
    
    # ==================== 上下文管理器 ====================
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()
        return False
