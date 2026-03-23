"""
CPE API 客户端 - 浏览器后端

通过浏览器自动化调用 CPE API
"""

import subprocess
import json
import time
import logging
from typing import Optional, Dict, Any, List, Tuple

from models import DeviceInfo, SMSMessage, WiFiInfo, ConnectedDevice

logger = logging.getLogger(__name__)


class CPEClientBrowser:
    """
    CPE API 客户端（浏览器后端）
    
    由于路由器 API 有保护机制，需要通过浏览器自动化调用
    """
    
    def __init__(self, base_url: str = "http://192.168.1.1"):
        self.base_url = base_url.rstrip("/")
        self._logged_in = False
    
    def _run_browser(self, *args: str, timeout: int = 30) -> str:
        """运行浏览器命令"""
        cmd = ["agent-browser"] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    
    def _eval_js(self, js_code: str, timeout: int = 30) -> str:
        """在浏览器中执行 JavaScript"""
        return self._run_browser("eval", js_code, timeout=timeout)
    
    def login(self, username: str, password: str) -> Tuple[bool, str]:
        """登录路由器"""
        try:
            # 打开登录页面
            self._run_browser("open", f"{self.base_url}/login.html", "--timeout", "30000")
            time.sleep(2)
            
            # 填写表单
            self._run_browser("fill", "@e2", username)
            self._run_browser("fill", "@e3", password)
            self._run_browser("click", "@e1")
            time.sleep(3)
            
            # 检查登录状态
            result = self._eval_js(
                "new Promise((resolve) => { "
                "$post('get_device_info', null, 'nocheck').then(data => resolve('success')); "
                "});"
            )
            
            if "success" in result:
                self._logged_in = True
                return True, "登录成功"
            else:
                return False, "登录失败"
                
        except Exception as e:
            return False, str(e)
    
    def logout(self) -> bool:
        """登出"""
        try:
            self._run_browser("close")
            self._logged_in = False
            return True
        except:
            return False
    
    def _call_api(self, method: str, data: Any = None, api_type: str = "nocheck") -> Any:
        """调用 API"""
        if not self._logged_in:
            raise Exception("未登录")
        
        data_str = "null" if data is None else json.dumps(data)
        js_code = f'''
        new Promise((resolve) => {{
            $post('{method}', {data_str}, '{api_type}').then(data => resolve(JSON.stringify(data)));
        }});
        '''
        
        result = self._eval_js(js_code)
        
        if result:
            try:
                # 去掉外层引号
                if result.startswith('"') and result.endswith('"'):
                    result = result[1:-1].replace('\\"', '"')
                return json.loads(result)
            except:
                return None
        return None
    
    def get_device_info(self) -> DeviceInfo:
        """获取设备信息"""
        try:
            data = self._call_api("get_device_info")
            if data:
                return DeviceInfo.from_dict(data)
        except Exception as e:
            logger.error(f"获取设备信息失败: {e}")
        return DeviceInfo()
    
    def get_new_sms_flag(self) -> bool:
        """检查是否有新短信"""
        try:
            data = self._call_api("get_new_sms")
            return data.get("new_sms_flag", "false") == "true"
        except:
            return False
    
    def get_sms_list(self) -> List[SMSMessage]:
        """获取短信列表"""
        try:
            data = self._call_api("get_sms_data")
            
            messages = []
            if isinstance(data, dict):
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
    
    def close(self):
        """关闭浏览器"""
        try:
            self._run_browser("close")
        except:
            pass
