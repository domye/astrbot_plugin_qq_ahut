from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import requests
from bs4 import BeautifulSoup
import asyncio
import json
import os
from datetime import datetime, time, timedelta
import heapq

class GroupConfigManager:
    def __init__(self, config_path="ahut_config.json"):
        self.config_path = config_path
        self.group_settings = {}
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.group_settings = json.load(f)

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.group_settings, f, ensure_ascii=False, indent=2)

    def get_group_config(self, group_id):
        return self.group_settings.get(group_id, {
            'enabled': False,
            'schedule_time': '08:00',
            'last_sent': None
        })

    def update_group_config(self, group_id, **kwargs):
        config = self.get_group_config(group_id)
        config.update(kwargs)
        self.group_settings[group_id] = config
        self.save_config()

@register("ahut_notifier", "Your Name", "安徽工业大学签到状态监控", "1.1.0")
class AhutNotifierPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config_manager = GroupConfigManager()
        self.scheduler = None
        self.task = asyncio.create_task(self.init_scheduler())

    async def init_scheduler(self):
        """初始化定时任务调度器"""
        self.scheduler = asyncio.create_task(self.schedule_loop())
    
    async def fetch_failed_users(self):
        """获取签到失败用户数据"""
        try:
            url = "http://sign.domye.top/"
            response = requests.get(url, timeout=10)
            response.encoding = 'utf-8'
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            users = []
            
            for card in soup.find_all('div', class_='user-card'):
                title = card.find('h3').text
                if '❌' in title:
                    username = title.split(' ')[0]
                    duration = card.find('p').text.split(': ')[1]
                    error = card.find('pre').text.strip()
                    users.append(f"· {username} | 耗时：{duration}\n   错误：{error}")
            
            return users
        except Exception as e:
            logger.error(f"数据获取失败: {str(e)}")
            return None

    async def send_group_message(self, group_id, message):
        """发送消息到指定群组"""
        await self.context.send_message(
            unified_msg_origin=f"group_{group_id}",
            chain=[{"type": "plain", "text": message}]
        )

    async def schedule_loop(self):
        """定时任务主循环"""
        while True:
            now = datetime.now()
            for group_id in list(self.config_manager.group_settings.keys()):
                config = self.config_manager.get_group_config(group_id)
                
                if not config['enabled']:
                    continue
                
                # 解析预定时间
                try:
                    schedule_time = datetime.strptime(config['schedule_time'], "%H:%M").time()
                except ValueError:
                    continue
                
                # 计算下一次触发时间
                target_time = datetime.combine(now.date(), schedule_time)
                if target_time <= now:
                    target_time += timedelta(days=1)
                
                # 到达预定时间时执行
                if now >= target_time - timedelta(seconds=60) and now <= target_time:
                    users = await self.fetch_failed_users()
                    if users:
                        msg = "⚠️今日签到失败用户：\n" + "\n".join(users)
                        await self.send_group_message(group_id, msg)
                        self.config_manager.update_group_config(
                            group_id, last_sent=now.isoformat()
                        )

            await asyncio.sleep(30)  # 每30秒检查一次

    @filter.command("set_ahut_time")
    async def set_schedule_time(self, event: AstrMessageEvent, time_str: str):
        """设置每日通知时间（群管理员）"""
        group_id = event.get_group_id()
        
        try:
            # 验证时间格式
            datetime.strptime(time_str, "%H:%M")
            self.config_manager.update_group_config(
                group_id, 
                schedule_time=time_str,
                enabled=True
            )
            yield event.plain_result(f"✅ 已设置每日通知时间为 {time_str}")
        except ValueError:
            yield event.plain_result("❌ 时间格式错误，请使用 HH:MM 格式")

    @filter.command("enable_ahut")
    async def enable_notifications(self, event: AstrMessageEvent):
        """启用每日通知（群管理员）"""
        group_id = event.get_group_id()
        self.config_manager.update_group_config(group_id, enabled=True)
        yield event.plain_result("✅ 已启用每日签到状态通知")

    @filter.command("disable_ahut")
    async def disable_notifications(self, event: AstrMessageEvent):
        """禁用每日通知（群管理员）"""
        group_id = event.get_group_id()
        self.config_manager.update_group_config(group_id, enabled=False)
        yield event.plain_result("✅ 已禁用每日签到状态通知")

    @filter.command("ahut_status")
    async def check_status(self, event: AstrMessageEvent):
        """查看当前配置"""
        group_id = event.get_group_id()
        config = self.config_manager.get_group_config(group_id)
        status = "已启用" if config['enabled'] else "已禁用"
        msg = (
            f"当前状态：{status}\n"
            f"每日通知时间：{config['schedule_time']}\n"
            f"最后发送时间：{config['last_sent'] or '从未发送'}"
        )
        yield event.plain_result(msg)

    async def terminate(self):
        """插件卸载时清理任务"""
        if self.scheduler:
            self.scheduler.cancel()
        logger.info("安徽工大签到插件已卸载")