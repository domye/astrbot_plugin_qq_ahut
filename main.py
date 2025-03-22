from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import requests
from bs4 import BeautifulSoup
import asyncio
import json
import os
from datetime import datetime, time, timedelta
import heapq

@register("web_data_scraper", "Your Name", "抓取网页数据的插件", "1.0.0")
class WebDataScraperPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config_file = "data/config/web_scraper_config.json"
        self.schedule_queue = []
        self.load_config()
        self.task = asyncio.create_task(self.schedule_loop())
        
    def load_config(self):
        """加载定时配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.schedule_queue = [
                        (datetime.strptime(t, "%H:%M").time(), group_id)
                        for t, group_id in data
                    ]
                    heapq.heapify(self.schedule_queue)
        except Exception as e:
            print(f"配置加载失败: {str(e)}")

    def save_config(self):
        """保存定时配置"""
        try:
            data = [
                (t.strftime("%H:%M"), group_id)
                for t, group_id in self.schedule_queue
            ]
            with open(self.config_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"配置保存失败: {str(e)}")

    async def schedule_loop(self):
        """定时任务主循环"""
        while True:
            now = datetime.now()
            if self.schedule_queue:
                next_time, group_id = self.schedule_queue[0]
                target = datetime.combine(now.date(), next_time)
                if target < now:
                    target += timedelta(days=1)
                
                wait_seconds = (target - now).total_seconds()
                try:
                    await asyncio.sleep(wait_seconds)
                    await self.send_to_group(group_id)
                    # 更新下次执行时间
                    new_time = (target + timedelta(days=1)).time()
                    heapq.heappush(self.schedule_queue, (new_time, group_id))
                    self.save_config()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"定时任务异常: {str(e)}")
                finally:
                    heapq.heappop(self.schedule_queue)
            else:
                await asyncio.sleep(60)

    async def send_to_group(self, group_id: str):
        """向指定群组发送数据"""
        try:
            url = "http://sign.domye.top/"
            response = requests.get(url, timeout=10)
            response.encoding = 'utf-8'
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            user_cards = soup.find_all('div', class_='user-card')
            
            failed_users = []
            for card in user_cards:
                username_element = card.find('h3')
                if not username_element:
                    continue
                    
                username = username_element.text.split(' ')[0]
                success_status = "✅" in username_element.text
                if not success_status:
                    duration = card.find('p').text.split(': ')[1] if card.find('p') else "N/A"
                    message = card.find('details').find('pre').get_text('\n').strip() if card.find('details') else "无错误信息"
                    failed_users.append({
                        "username": username,
                        "duration": duration,
                        "message": message
                    })

            if failed_users:
                result = "⚠️今日签到失败用户：\n"
                for user in failed_users:
                    result += (
                        f"\n用户名：{user['username']}\n"
                        f"耗时：{user['duration']}\n"
                        f"错误信息：\n{user['message']}\n{'='*20}"
                    )
                await self.context.send_message(
                    unified_msg_origin=f"group_{group_id}",
                    chain=[{
                        "type": "text",
                        "data": {"text": result}
                    }]
                )
                
        except Exception as e:
            print(f"发送群消息失败: {str(e)}")

    @filter.command("add_schedule")
    async def add_schedule(self, event: AstrMessageEvent, time_str: str, group_id: str):
        """添加定时任务 格式: /add_schedule 08:00 123456"""
        try:
            scheduled_time = datetime.strptime(time_str, "%H:%M").time()
            heapq.heappush(self.schedule_queue, (scheduled_time, group_id))
            self.save_config()
            yield event.plain_result(f"✅ 已添加定时任务\n时间: {time_str}\n群组: {group_id}")
        except ValueError:
            yield event.plain_result("❌ 时间格式错误，请使用 HH:MM 格式")

    @filter.command("list_schedules")
    async def list_schedules(self, event: AstrMessageEvent):
        """列出所有定时任务"""
        if not self.schedule_queue:
            yield event.plain_result("当前没有定时任务")
            return
        
        result = "📅 当前定时任务:\n"
        for idx, (t, gid) in enumerate(sorted(self.schedule_queue), 1):
            result += f"{idx}. 时间: {t.strftime('%H:%M')} | 群组: {gid}\n"
        yield event.plain_result(result)

    @filter.command("ahut_sign")
    async def ahut_sign(self, event: AstrMessageEvent):
        """立即获取签到状态"""
        try:
            url = "http://sign.domye.top/"
            response = requests.get(url)
            response.encoding = 'utf-8'
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            user_cards = soup.find_all('div', class_='user-card')
            
            failed_users = []
            for card in user_cards:
                username = card.find('h3').text.split(' ')[0]
                success_status = "✅" in card.find('h3').text
                if not success_status:
                    duration = card.find('p').text.split(': ')[1]
                    message = card.find('details').find('pre').get_text('\n').strip()
                    failed_users.append({
                        "username": username,
                        "duration": duration,
                        "message": message
                    })

            if failed_users:
                result = "⚠️失败用户列表：\n"
                for user in failed_users:
                    result += (
                        f"\n用户名：{user['username']}\n"
                        f"耗时：{user['duration']}\n"
                        f"错误信息：\n{user['message']}\n"
                    )
            else:
                result = "🎉今日没有签到失败用户"
                
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"请求失败: {str(e)}")

    async def terminate(self):
        """插件卸载时清理任务"""
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        self.save_config()