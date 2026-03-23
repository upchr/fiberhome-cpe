#!/usr/bin/env python3
"""
短信转发服务

持续监听 CPE 短信并转发到飞书等通知渠道
"""

import sys
import os
import logging
import argparse
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from cpe_api import SMSWatcher, BarkNotifier, WebhookNotifier, FeishuNotifier, FeishuWebhookNotifier

# 尝试加载 dotenv
try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)


def load_env_config():
    """从 .env 文件加载配置"""
    # 查找 .env 文件
    env_paths = [
        Path(__file__).parent / ".env",  # cpe_api/.env
        Path(__file__).parent.parent / ".env",  # code/.env
        Path.cwd() / ".env",  # 当前目录
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            if HAS_DOTENV:
                load_dotenv(env_path)
                logger.info(f"已加载配置文件: {env_path}")
            else:
                logger.warning(f"找到 .env 文件但未安装 python-dotenv，请运行: pip install python-dotenv")
            break
    
    return {
        # CPE 配置
        "host": os.getenv("CPE_HOST", "http://192.168.1.1"),
        "username": os.getenv("CPE_USERNAME", "admin"),
        "password": os.getenv("CPE_PASSWORD", ""),
        "check_interval": float(os.getenv("CHECK_INTERVAL", "3.0")),
        "wait_after_logout": float(os.getenv("WAIT_AFTER_LOGOUT", "600.0")),
        
        # 通知器配置
        "bark_key": os.getenv("BARK_KEY", ""),
        "bark_server": os.getenv("BARK_SERVER", "https://api.day.app"),
        "feishu_webhook": os.getenv("FEISHU_WEBHOOK", ""),
        "feishu_app_id": os.getenv("FEISHU_APP_ID", ""),
        "feishu_app_secret": os.getenv("FEISHU_APP_SECRET", ""),
        "feishu_receive_id": os.getenv("FEISHU_RECEIVE_ID", ""),
        "webhook_url": os.getenv("WEBHOOK_URL", ""),
    }


def main():
    parser = argparse.ArgumentParser(description="烽火 CPE 短信转发服务")
    
    # CPE 配置（命令行参数可覆盖 .env）
    parser.add_argument("--host", help="CPE 地址")
    parser.add_argument("-u", "--username", help="CPE 用户名")
    parser.add_argument("-p", "--password", help="CPE 密码")
    parser.add_argument("-i", "--interval", type=float, help="检查间隔（秒）")
    parser.add_argument("-w", "--wait", type=float, help="被登出后等待时间（秒）")
    
    # 通知器配置（命令行参数可覆盖 .env）
    parser.add_argument("-b", "--bark-key", help="Bark 推送 Key")
    parser.add_argument("--feishu-webhook", help="飞书 Webhook URL")
    parser.add_argument("--feishu-app-id", help="飞书应用 ID")
    parser.add_argument("--feishu-app-secret", help="飞书应用密钥")
    parser.add_argument("--feishu-receive-id", help="飞书接收者 ID")
    parser.add_argument("--webhook", help="自定义 Webhook URL")
    
    # 其他选项
    parser.add_argument("--debug", action="store_true", help="开启调试日志")
    parser.add_argument("--dry-run", action="store_true", help="测试模式（不实际监听）")
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 加载配置
    config = load_env_config()
    
    # 命令行参数覆盖 .env 配置
    host = args.host or config["host"]
    username = args.username or config["username"]
    password = args.password or config["password"]
    check_interval = args.interval or config["check_interval"]
    wait_after_logout = args.wait or config["wait_after_logout"]
    
    # 检查必需配置
    if not password:
        logger.error("未配置 CPE 密码，请设置环境变量 CPE_PASSWORD 或使用 -p 参数")
        sys.exit(1)
    
    # 创建通知器
    notifiers = []
    
    # Bark
    bark_key = args.bark_key or config["bark_key"]
    if bark_key:
        bark_server = config["bark_server"]
        notifiers.append(BarkNotifier(bark_key, bark_server))
        logger.info("已添加 Bark 通知器")
    
    # 飞书 Webhook（推荐）
    feishu_webhook = args.feishu_webhook or config["feishu_webhook"]
    if feishu_webhook:
        notifiers.append(FeishuWebhookNotifier(feishu_webhook))
        logger.info("已添加飞书 Webhook 通知器")
    
    # 飞书应用机器人
    feishu_app_id = args.feishu_app_id or config["feishu_app_id"]
    feishu_app_secret = args.feishu_app_secret or config["feishu_app_secret"]
    feishu_receive_id = args.feishu_receive_id or config["feishu_receive_id"]
    if feishu_app_id and feishu_app_secret and feishu_receive_id:
        notifiers.append(FeishuNotifier(feishu_app_id, feishu_app_secret, feishu_receive_id))
        logger.info("已添加飞书应用机器人通知器")
    
    # 自定义 Webhook
    webhook_url = args.webhook or config["webhook_url"]
    if webhook_url:
        notifiers.append(WebhookNotifier(webhook_url))
        logger.info("已添加 Webhook 通知器")
    
    if not notifiers:
        logger.warning("未配置任何通知器，短信将仅打印到日志")
    
    # 回调函数
    def on_sms(sms):
        logger.info(f"📩 新短信: [{sms.time}] {sms.phone}")
        logger.debug(f"内容: {sms.content}")
    
    def on_logout():
        logger.warning("⚠️ 被其他用户登出")
    
    # 创建监听器
    watcher = SMSWatcher(
        host=host,
        username=username,
        password=password,
        notifiers=notifiers,
        check_interval=check_interval,
        on_sms=on_sms,
        on_logout=on_logout,
        wait_after_logout=wait_after_logout
    )
    
    # 启动信息
    logger.info("=" * 50)
    logger.info("烽火 CPE 短信转发服务")
    logger.info("=" * 50)
    logger.info(f"CPE 地址: {host}")
    logger.info(f"用户名: {username}")
    logger.info(f"检查间隔: {check_interval}秒")
    logger.info(f"通知器数量: {len(notifiers)}")
    logger.info("=" * 50)
    
    if args.dry_run:
        logger.info("测试模式，不实际监听")
        return
    
    logger.info("启动监听，按 Ctrl+C 停止")
    
    try:
        watcher.start(blocking=True)
    except KeyboardInterrupt:
        logger.info("收到停止信号")
        watcher.stop()
        logger.info("已退出")


if __name__ == "__main__":
    main()
