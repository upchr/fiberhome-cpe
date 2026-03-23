"""
FastAPI 应用

提供 CPE 设备信息 API，后台持续监控短信
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import threading
import os

from client import CPEClient
from watcher import SMSWatcher, BarkNotifier, WebhookNotifier, FeishuNotifier, FeishuWebhookNotifier

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# 尝试加载 dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# FastAPI 应用
app = FastAPI(
    title="CPE API",
    description="烽火 5G CPE 路由器 API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置
CPE_HOST = os.getenv("CPE_HOST", "http://192.168.1.1")
CPE_USERNAME = os.getenv("CPE_USERNAME", "admin")
CPE_PASSWORD = os.getenv("CPE_PASSWORD", "")
CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "3.0"))

# 短信监控器
watcher: Optional[SMSWatcher] = None


# ==================== 数据模型 ====================

class DeviceInfoResponse(BaseModel):
    """设备信息响应"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class TemperatureResponse(BaseModel):
    """温度响应"""
    success: bool
    data: Optional[Dict[str, float]] = None


class SystemUsageResponse(BaseModel):
    """系统使用率响应"""
    success: bool
    data: Optional[Dict[str, float]] = None


class UptimeResponse(BaseModel):
    """运行时间响应"""
    success: bool
    data: Optional[Dict[str, int]] = None


class SMSResponse(BaseModel):
    """短信响应"""
    success: bool
    count: int
    data: List[Dict[str, Any]]


class SMSWatcherStatus(BaseModel):
    """短信监控状态"""
    running: bool
    host: str
    check_interval: float


# ==================== API 路由 ====================

@app.get("/")
async def root():
    """根路径"""
    return {"name": "CPE API", "version": "1.0.0", "docs": "/docs"}


@app.get("/api/device/info", response_model=DeviceInfoResponse)
async def get_device_info():
    """
    获取设备信息
    
    返回格式化的设备信息文本
    """
    if not CPE_PASSWORD:
        raise HTTPException(status_code=500, detail="未配置 CPE_PASSWORD")
    
    client = CPEClient(CPE_HOST)
    success, msg = client.login(CPE_USERNAME, CPE_PASSWORD)
    
    if not success:
        return DeviceInfoResponse(success=False, message=f"登录失败: {msg}")
    
    try:
        # 获取基本信息
        device_info = client.get_device_info()
        
        # 获取详细信息
        details = client.get_device_details()
        
        # 温度
        temp_5g = details.get("Modem5GTemperature", "0")
        temp_c = 0
        if temp_5g:
            try:
                temp_c = int(temp_5g) / 1000
            except:
                pass
        
        # 运行时间
        uptime = client.get_uptime()
        
        data = {
            # 基本信息
            "product_name": "5G CPE",
            "model_name": device_info.model_name or details.get("ModelName", ""),
            "serial_number": details.get("SerialNumber", ""),
            "mac_address": device_info.mac_address or "",
            # 版本信息
            "software_version": details.get("SoftwareVersion", ""),
            "hardware_version": details.get("HardwareVersion", ""),
            # 状态信息
            "uptime": uptime,
            "temperature": {
                "5g": temp_c,
                "unit": "℃"
            }
        }
        
        return DeviceInfoResponse(success=True, message="获取成功", data=data)
    
    except Exception as e:
        logger.error(f"获取设备信息失败: {e}")
        return DeviceInfoResponse(success=False, message=f"获取失败: {str(e)}")
    
    finally:
        client.logout()


@app.get("/api/device/info/formatted")
async def get_device_info_formatted():
    """
    获取格式化的设备信息
    
    返回 Markdown 格式的设备信息
    """
    if not CPE_PASSWORD:
        raise HTTPException(status_code=500, detail="未配置 CPE_PASSWORD")
    
    client = CPEClient(CPE_HOST)
    success, msg = client.login(CPE_USERNAME, CPE_PASSWORD)
    
    if not success:
        raise HTTPException(status_code=401, detail=f"登录失败: {msg}")
    
    try:
        info = client.get_device_info_formatted()
        return {"success": True, "data": info}
    
    except Exception as e:
        logger.error(f"获取设备信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        client.logout()


@app.get("/api/device/temperature", response_model=TemperatureResponse)
async def get_temperature():
    """获取温度"""
    if not CPE_PASSWORD:
        raise HTTPException(status_code=500, detail="未配置 CPE_PASSWORD")
    
    client = CPEClient(CPE_HOST)
    success, msg = client.login(CPE_USERNAME, CPE_PASSWORD)
    
    if not success:
        return TemperatureResponse(success=False)
    
    try:
        temp = client.get_temperature()
        return TemperatureResponse(success=True, data=temp)
    
    finally:
        client.logout()


@app.get("/api/device/usage", response_model=SystemUsageResponse)
async def get_system_usage():
    """获取系统使用率"""
    if not CPE_PASSWORD:
        raise HTTPException(status_code=500, detail="未配置 CPE_PASSWORD")
    
    client = CPEClient(CPE_HOST)
    success, msg = client.login(CPE_USERNAME, CPE_PASSWORD)
    
    if not success:
        return SystemUsageResponse(success=False)
    
    try:
        usage = client.get_system_usage()
        return SystemUsageResponse(success=True, data=usage)
    
    finally:
        client.logout()


@app.get("/api/device/uptime", response_model=UptimeResponse)
async def get_uptime():
    """获取运行时间"""
    if not CPE_PASSWORD:
        raise HTTPException(status_code=500, detail="未配置 CPE_PASSWORD")
    
    client = CPEClient(CPE_HOST)
    success, msg = client.login(CPE_USERNAME, CPE_PASSWORD)
    
    if not success:
        return UptimeResponse(success=False)
    
    try:
        uptime = client.get_uptime()
        return UptimeResponse(success=True, data=uptime)
    
    finally:
        client.logout()


@app.get("/api/sms/list", response_model=SMSResponse)
async def get_sms_list(limit: int = 20):
    """
    获取短信列表
    
    Args:
        limit: 返回数量限制，默认 20
    """
    if not CPE_PASSWORD:
        raise HTTPException(status_code=500, detail="未配置 CPE_PASSWORD")
    
    client = CPEClient(CPE_HOST)
    success, msg = client.login(CPE_USERNAME, CPE_PASSWORD)
    
    if not success:
        raise HTTPException(status_code=401, detail=f"登录失败: {msg}")
    
    try:
        sms_list = client.get_sms_list()
        
        data = [
            {
                "id": sms.id,
                "phone": sms.phone,
                "content": sms.content,
                "time": sms.time,
                "is_read": sms.is_read,
                "is_sent": sms.is_sent
            }
            for sms in sms_list[:limit]
        ]
        
        return SMSResponse(success=True, count=len(data), data=data)
    
    finally:
        client.logout()


@app.get("/api/sms/unread", response_model=SMSResponse)
async def get_unread_sms():
    """获取未读短信"""
    if not CPE_PASSWORD:
        raise HTTPException(status_code=500, detail="未配置 CPE_PASSWORD")
    
    client = CPEClient(CPE_HOST)
    success, msg = client.login(CPE_USERNAME, CPE_PASSWORD)
    
    if not success:
        raise HTTPException(status_code=401, detail=f"登录失败: {msg}")
    
    try:
        sms_list = client.get_unread_sms()
        
        data = [
            {
                "id": sms.id,
                "phone": sms.phone,
                "content": sms.content,
                "time": sms.time,
                "is_read": sms.is_read,
                "is_sent": sms.is_sent
            }
            for sms in sms_list
        ]
        
        return SMSResponse(success=True, count=len(data), data=data)
    
    finally:
        client.logout()


@app.get("/api/watcher/status", response_model=SMSWatcherStatus)
async def get_watcher_status():
    """获取短信监控状态"""
    global watcher
    
    return SMSWatcherStatus(
        running=watcher is not None and watcher._running,
        host=CPE_HOST,
        check_interval=CHECK_INTERVAL
    )


@app.post("/api/watcher/start")
async def start_watcher(background_tasks: BackgroundTasks):
    """启动短信监控"""
    global watcher
    
    if watcher and watcher._running:
        return {"success": True, "message": "短信监控已在运行"}
    
    # 创建通知器
    notifiers = []
    
    bark_key = os.getenv("BARK_KEY", "")
    if bark_key:
        notifiers.append(BarkNotifier(bark_key, os.getenv("BARK_SERVER", "https://api.day.app")))
    
    feishu_webhook = os.getenv("FEISHU_WEBHOOK", "")
    if feishu_webhook:
        notifiers.append(FeishuWebhookNotifier(feishu_webhook))
    
    feishu_app_id = os.getenv("FEISHU_APP_ID", "")
    feishu_app_secret = os.getenv("FEISHU_APP_SECRET", "")
    feishu_receive_id = os.getenv("FEISHU_RECEIVE_ID", "")
    if feishu_app_id and feishu_app_secret and feishu_receive_id:
        notifiers.append(FeishuNotifier(feishu_app_id, feishu_app_secret, feishu_receive_id))
    
    webhook_url = os.getenv("WEBHOOK_URL", "")
    if webhook_url:
        notifiers.append(WebhookNotifier(webhook_url))
    
    # 创建监控器
    watcher = SMSWatcher(
        host=CPE_HOST,
        username=CPE_USERNAME,
        password=CPE_PASSWORD,
        notifiers=notifiers,
        check_interval=CHECK_INTERVAL
    )
    
    # 启动监控（非阻塞）
    watcher.start(blocking=False)
    
    logger.info(f"短信监控已启动，检查间隔: {CHECK_INTERVAL}秒")
    
    return {"success": True, "message": "短信监控已启动"}


@app.post("/api/watcher/stop")
async def stop_watcher():
    """停止短信监控"""
    global watcher
    
    if not watcher or not watcher._running:
        return {"success": True, "message": "短信监控未运行"}
    
    watcher.stop()
    watcher = None
    
    logger.info("短信监控已停止")
    
    return {"success": True, "message": "短信监控已停止"}


# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup_event():
    """应用启动时自动启动短信监控"""
    auto_start = os.getenv("AUTO_START_WATCHER", "false").lower() == "true"
    
    if auto_start and CPE_PASSWORD:
        logger.info("自动启动短信监控...")
        await start_watcher(None)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时停止短信监控"""
    global watcher
    
    if watcher and watcher._running:
        watcher.stop()
        logger.info("短信监控已停止")


# ==================== 入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
