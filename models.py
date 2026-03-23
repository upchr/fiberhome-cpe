"""
数据模型
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class DeviceInfo:
    """设备信息"""
    model_name: str = ""
    operator_name: str = ""
    serial_number: str = ""
    hardware_version: str = ""
    # 新增字段
    product_name: str = ""
    device_model: str = ""
    uptime: str = ""
    cpu_temp: str = ""
    lan_ip: str = ""
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
            firmware_version=data.get("firmware_version", ""),
            mac_address=data.get("mac_address", ""),
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
    is_sent: bool = False  # recv 或 send
    
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


@dataclass
class WiFiInfo:
    """WiFi 信息"""
    ssid: str = ""
    password: str = ""
    enabled: bool = True
    security: str = "WPA2"
    channel: int = 0
    frequency: str = ""
    bandwidth: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WiFiInfo":
        return cls(
            ssid=data.get("ssid", ""),
            password=data.get("password", ""),
            enabled=data.get("enabled", "1") == "1",
            security=data.get("security", "WPA2"),
            channel=int(data.get("channel", 0)),
            frequency=data.get("frequency", ""),
            bandwidth=data.get("bandwidth", ""),
        )


@dataclass
class ConnectedDevice:
    """已连接设备"""
    hostname: str = ""
    mac_address: str = ""
    ip_address: str = ""
    connection_type: str = ""  # wifi, ethernet
    interface: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConnectedDevice":
        return cls(
            hostname=data.get("hostname", data.get("name", "")),
            mac_address=data.get("mac", data.get("mac_address", "")),
            ip_address=data.get("ip", data.get("ip_address", "")),
            connection_type=data.get("connection_type", ""),
            interface=data.get("interface", ""),
        )


@dataclass
class SignalInfo:
    """信号信息"""
    rsrp: int = 0  # 参考信号接收功率
    rsrq: int = 0  # 参考信号接收质量
    rssi: int = 0  # 接收信号强度指示
    sinr: int = 0  # 信噪比
    cell_id: str = ""
    plmn: str = ""
    band: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SignalInfo":
        return cls(
            rsrp=int(data.get("rsrp", 0)),
            rsrq=int(data.get("rsrq", 0)),
            rssi=int(data.get("rssi", 0)),
            sinr=int(data.get("sinr", 0)),
            cell_id=data.get("cell_id", ""),
            plmn=data.get("plmn", ""),
            band=data.get("band", ""),
        )


@dataclass
class DataUsage:
    """流量使用"""
    total_rx: int = 0  # 总接收字节
    total_tx: int = 0  # 总发送字节
    monthly_rx: int = 0  # 月接收字节
    monthly_tx: int = 0  # 月发送字节
    session_rx: int = 0  # 本次接收字节
    session_tx: int = 0  # 本次发送字节
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataUsage":
        return cls(
            total_rx=int(data.get("total_rx", 0)),
            total_tx=int(data.get("total_tx", 0)),
            monthly_rx=int(data.get("monthly_rx", 0)),
            monthly_tx=int(data.get("monthly_tx", 0)),
            session_rx=int(data.get("session_rx", 0)),
            session_tx=int(data.get("session_tx", 0)),
        )


@dataclass
class NetworkInfo:
    """网络信息"""
    connection_status: str = ""
    network_type: str = ""  # 4G, 5G, etc.
    ip_address: str = ""
    gateway: str = ""
    dns_primary: str = ""
    dns_secondary: str = ""
    apn: str = ""
    roaming: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NetworkInfo":
        return cls(
            connection_status=data.get("connection_status", ""),
            network_type=data.get("network_type", ""),
            ip_address=data.get("ip_address", ""),
            gateway=data.get("gateway", ""),
            dns_primary=data.get("dns_primary", ""),
            dns_secondary=data.get("dns_secondary", ""),
            apn=data.get("apn", ""),
            roaming=data.get("roaming", "0") == "1",
        )
