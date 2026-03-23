"""
CPE API 客户端

参考: https://gitee.com/upchr/fiberhome-cpe-sms
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
    """烽火 5G CPE 路由器 API 客户端"""
    
    def __init__(self, base_url: str = "http://192.168.1.1"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
        })
        self._logged_in = False
        
    # ==================== 核心 API 方法 ====================
    
    def _get_sessionid(self) -> str:
        """获取 sessionid"""
        url = f"{self.base_url}/api/tmp/FHNCAPIS?ajaxmethod=get_refresh_sessionid"
        resp = self.session.get(url, timeout=30)
        return resp.json().get("sessionid", "")
    
    def _request_get(self, path: str) -> str:
        """GET 请求"""
        resp = self.session.get(f"{self.base_url}{path}", timeout=30)
        return resp.text.strip()
    
    def _request_post(self, data_obj: Any, path: str, ajaxmethod: str) -> str:
        """
        POST 请求（加密）
        
        参考 Go 实现：
        - URL: /api/tmp/FHAPIS 或 /api/sign/DO_WEB_LOGIN
        - ajaxmethod 放在请求体中，不在 URL 中
        """
        sessionid = self._get_sessionid()
        
        # 构造请求体
        body = {
            "dataObj": data_obj,
            "ajaxmethod": ajaxmethod,
            "sessionid": sessionid
        }
        body_json = json.dumps(body, ensure_ascii=False)
        
        # 加密
        encrypted = AESEncryptor.encrypt(body_json, sessionid[:16])
        
        # 发送 POST 请求
        resp = self.session.post(
            f"{self.base_url}{path}",
            data=encrypted,
            timeout=30
        )
        
        # 解密响应
        if resp.text.strip():
            if ajaxmethod == "DO_WEB_LOGIN":
                return resp.text.strip()
            try:
                return AESEncryptor.decrypt(resp.text.strip(), sessionid[:16])
            except:
                return resp.text.strip()
        return ""
    
    # ==================== 登录/登出 ====================
    
    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """登录"""
        result = self._request_post(
            {"username": username, "password": password},
            "/api/sign/DO_WEB_LOGIN",
            "DO_WEB_LOGIN"
        )
        
        parts = result.split("|")
        if len(parts) >= 2:
            status = parts[0]
            messages = {
                "0": "登录成功",
                "1": "已有用户在其他地方登录",
                "2": "连续错误登录次数达到3次，请1分钟后再试",
                "3": "管理账号已被禁用",
                "4": "用户名或密码错误",
            }
            self._logged_in = status == "0"
            return self._logged_in, messages.get(status, f"未知状态: {status}")
        return False, f"解析响应失败: {result}"
    
    def logout(self) -> bool:
        """登出"""
        try:
            self._request_post(None, "/api/sign/DO_WEB_LOGOUT", "DO_WEB_LOGOUT")
            self._logged_in = False
            return True
        except:
            return False
    
    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return self._request_get("/api/tmp/IS_LOGGED_IN") == "1"
    
    def heartbeat(self) -> bool:
        """心跳"""
        return self._request_get("/api/tmp/heartbeat") == "true"
    
    # ==================== 设备信息 ====================
    
    def get_device_info(self) -> DeviceInfo:
        """获取设备基本信息"""
        result = self._request_post(None, "/api/tmp/FHNCAPIS", "get_device_info")
        if result:
            try:
                return DeviceInfo.from_dict(json.loads(result))
            except:
                pass
        return DeviceInfo()
    
    def get_temperature(self) -> Dict[str, float]:
        """获取温度"""
        result = self._request_post({
            "Modem5GTemperature": "X_FH_MobileNetwork.Temperature.Modem5GTemperature",
            "Modem4GTemperature": "X_FH_MobileNetwork.Temperature.Modem4GTemperature"
        }, "/api/tmp/FHAPIS", "get_value_by_xmlnode")
        
        data = json.loads(result) if result else {}
        result_dict = {}
        for key, xml_key in [("5g", "Modem5GTemperature"), ("4g", "Modem4GTemperature")]:
            if data.get(xml_key):
                try:
                    result_dict[key] = int(data[xml_key]) / 1000
                except:
                    pass
        return result_dict
    
    def get_system_usage(self) -> Dict[str, float]:
        """获取系统使用率"""
        result = self._request_post({
            "CPUUsage": "DeviceInfo.ProcessStatus.CPUUsage",
            "MemoryTotal": "DeviceInfo.MemoryStatus.Total",
            "MemoryFree": "DeviceInfo.MemoryStatus.Free"
        }, "/api/tmp/FHAPIS", "get_value_by_xmlnode")
        
        data = json.loads(result) if result else {}
        result_dict = {}
        if data.get("CPUUsage"):
            try:
                result_dict["cpu"] = float(data["CPUUsage"])
            except:
                pass
        if data.get("MemoryTotal") and data.get("MemoryFree"):
            try:
                result_dict["memory"] = (int(data["MemoryTotal"]) - int(data["MemoryFree"])) / int(data["MemoryTotal"]) * 100
            except:
                pass
        return result_dict
    
    def get_uptime(self) -> Dict[str, int]:
        """获取运行时间"""
        result = self._request_post({"UpTime": "DeviceInfo.UpTime"}, "/api/tmp/FHAPIS", "get_value_by_xmlnode")
        data = json.loads(result) if result else {}
        if data.get("UpTime"):
            try:
                seconds = int(data["UpTime"])
                return {"days": seconds // 86400, "hours": (seconds % 86400) // 3600, "minutes": (seconds % 3600) // 60, "seconds": seconds % 60}
            except:
                pass
        return {}
    
    def get_device_info_formatted(self) -> str:
        """
        获取格式化的设备信息
        
        Returns:
            格式化的设备信息文本
        """
        # 获取基本信息
        device_info = self.get_device_info()
        
        # 获取详细信息
        details = self.get_device_details()
        
        # 温度
        temp_5g = details.get("Modem5GTemperature", "0")
        temp_str = ""
        if temp_5g:
            try:
                temp_c = int(temp_5g) / 1000
                temp_str = f"{temp_c:.1f} ℃"
            except:
                pass
        
        # 运行时间
        uptime = self.get_uptime()
        uptime_str = ""
        if uptime:
            uptime_str = f"{uptime.get('days', 0)}天 {uptime.get('hours', 0)}小时 {uptime.get('minutes', 0)}分钟 {uptime.get('seconds', 0)}秒"
        
        # 构造格式化文本
        lines = [
            "📋 **基本信息**",
            f"• 产品名称: 5G CPE",
            f"• 设备型号: {device_info.model_name or details.get('ModelName', '-')}",
            f"• 序列号: {details.get('SerialNumber', '-')}",
            f"• MAC 地址: {device_info.mac_address or '-'}",
            "",
            "📦 **版本信息**",
            f"• 软件版本: {details.get('SoftwareVersion', '-')}",
            f"• 硬件版本: {details.get('HardwareVersion', '-')}",
            "",
            "📊 **状态信息**",
            f"• 运行时间: {uptime_str or '-'}",
            f"• CPU 温度: {temp_str or '-'}",
        ]
        
        return "\n".join(lines)
    
    def get_device_details(self) -> Dict[str, Any]:
        """获取设备详细信息"""
        result = self._request_post({
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
        }, "/api/tmp/FHAPIS", "get_value_by_xmlnode")
        return json.loads(result) if result else {}
    
    def get_sim_info(self) -> Dict[str, Any]:
        """获取 SIM 卡信息"""
        result = self._request_post({
            "SIMStatus": "X_FH_MobileNetwork.SIM.1.SIMStatus",
            "IMEI": "X_FH_MobileNetwork.SIM.1.IMEI",
            "IMSI": "X_FH_MobileNetwork.SIM.1.IMSI",
            "NetworkMode": "X_FH_MobileNetwork.SIM.1.NetworkMode",
            "CarrierName": "X_FH_MobileNetwork.SIM.1.CarrierName"
        }, "/api/tmp/FHAPIS", "get_value_by_xmlnode")
        return json.loads(result) if result else {}
    
    def get_signal_info(self) -> Dict[str, Any]:
        """获取信号信息"""
        result = self._request_post({
            "RSRP": "X_FH_MobileNetwork.RadioSignalParameter.RSRP",
            "RSSI": "X_FH_MobileNetwork.RadioSignalParameter.RSSI",
            "SINR": "X_FH_MobileNetwork.RadioSignalParameter.SINR",
            "RSRQ": "X_FH_MobileNetwork.RadioSignalParameter.RSRQ",
            "BAND": "X_FH_MobileNetwork.RadioSignalParameter.BAND",
            "PCI": "X_FH_MobileNetwork.RadioSignalParameter.PCI",
            "SSB_RSRP": "X_FH_MobileNetwork.RadioSignalParameter.SSB_RSRP"
        }, "/api/tmp/FHAPIS", "get_value_by_xmlnode")
        return json.loads(result) if result else {}
    
    def get_traffic_stats(self) -> Dict[str, Any]:
        """获取流量统计"""
        result = self._request_post({
            "TodayTotalTxBytes": "X_FH_MobileNetwork.TrafficStats.TodayTotalTxBytes",
            "TodayTotalRxBytes": "X_FH_MobileNetwork.TrafficStats.TodayTotalRxBytes",
            "MonthTxBytes": "X_FH_MobileNetwork.TrafficStats.MonthTxBytes",
            "MonthRxBytes": "X_FH_MobileNetwork.TrafficStats.MonthRxBytes"
        }, "/api/tmp/FHAPIS", "get_value_by_xmlnode")
        return json.loads(result) if result else {}
    
    # ==================== 短信管理（参考 Go 实现）====================
    
    def get_new_sms_flag(self) -> bool:
        """
        检查是否有新短信
        
        参考 Go 实现：GET 请求
        URL: /api/tmp/FHAPIS?ajaxmethod=get_new_sms
        """
        try:
            result = self._request_get("/api/tmp/FHAPIS?ajaxmethod=get_new_sms")
            data = json.loads(result)
            return data.get("new_sms_flag", "false") == "true"
        except Exception as e:
            logger.debug(f"get_new_sms_flag 失败: {e}")
            return False
    
    def get_sms_list(self) -> List[SMSMessage]:
        """
        获取短信列表
        
        参考 Go 实现：POST 请求
        URL: /api/tmp/FHAPIS
        ajaxmethod: get_sms_data
        """
        try:
            result = self._request_post(None, "/api/tmp/FHAPIS", "get_sms_data")
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
        """
        标记短信为已读
        
        参考 Go 实现：
        URL: /api/tmp/FHAPIS
        ajaxmethod: set_value_by_xmlnode
        """
        try:
            data = {
                "url": {
                    f"smsIsopend{sms_id}": f"InternetGatewayDevice.X_FH_MobileNetwork.SMS_Recv.SMS_RecvMsg.{sms_id}.isOpened"
                },
                "value": {
                    f"smsIsopend{sms_id}": "1"
                }
            }
            self._request_post(data, "/api/tmp/FHAPIS", "set_value_by_xmlnode")
            return True
        except Exception as e:
            logger.error(f"标记短信已读失败: {e}")
            return False
    
    # ==================== 上下文管理器 ====================
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()
        return False
