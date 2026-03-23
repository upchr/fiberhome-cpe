"""
数据模型
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class DeviceInfo:
    """设备信息"""
    model_name: str = ""
    operator_name: str = ""
    serial_number: str = ""
    hardware_version: str = ""
    firmware_version: str = ""
    mac_address: str = ""
    imei: str = ""
    imsi: str = ""
    i18n: str = "zh"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceInfo":
        return cls(
            model_name=data.get("model_name", ""),
            operator_name=data.get("operator_name", ""),
            serial_number=data.get("serial_number", ""),
            firmware_version=data.get("firmware_version", data.get("software_version", "")),
            mac_address=data.get("mac_address", data.get("brmac", "")),
            imei=data.get("imei", ""),
            imsi=data.get("imsi", ""),
            i18n=data.get("i18n", "zh"),
        )


@dataclass
class SMSMessage:
    """短信消息"""
    id: str = ""
    phone: str = ""
    content: str = ""
    time: str = ""
    is_read: bool = False
    is_sent: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], phone: str = "") -> "SMSMessage":
        return cls(
            id=data.get("childnode", ""),
            phone=phone,
            content=data.get("msg_content", ""),
            time=data.get("time", ""),
            is_read=data.get("isOpened", "0") == "1",
            is_sent=data.get("rcvorsend", "recv") == "send",
        )
