from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from bs4 import BeautifulSoup
import asyncio
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiohttp

@register("web_data_scraper", "Your Name", "抓取网页数据的插件", "1.0.0")
class WebDataScraperPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.group_id = "626778303"  # 改为实际群号
        self.scheduler = AsyncIOScheduler()
    
    async def on_enable(self):
        """插件启用时启动调度器"""
        self._setup_scheduler()
        self.scheduler.start()

    def _setup_scheduler(self):
        """配置定时任务调度器"""
        # 每天8点触发（cron表达式：0 8 * * *）
        self.scheduler.add_job(
            self.send_to_group,
            'cron',
            hour=16,
            minute=40
        )

    async def fetch_failed_users(self):
        """抓取失败用户数据"""
        url = "http://sign.domye.top/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text(encoding='utf-8')
                soup = BeautifulSoup(html, 'html.parser')
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
                return failed_users

    async def send_to_group(self):
        """向指定群组发送数据"""
        try:
            failed_users = await self.fetch_failed_users()
            if failed_users:
                result = "⚠️今日签到失败用户：\n"
                for user in failed_users:
                    result += (
                        f"\n用户名：{user['username']}\n"
                        f"耗时：{user['duration']}\n"
                        f"错误信息：\n{user['message']}\n"
                    )
                await self.context.send_message(
                    unified_msg_origin=f"group_{self.group_id}",
                    chain=[{"type": "plain", "text": result}]
                )
            else:
                await self.context.send_message(
                    unified_msg_origin=f"group_{self.group_id}",
                    chain=[{"type": "plain", "text": "🎉今日没有签到失败用户"}]
                )
        except Exception as e:
            error_msg = f"定时任务异常：{str(e)}"
            print(error_msg)
            await self.context.send_message(
                unified_msg_origin=f"group_{self.group_id}",
                chain=[{"type": "plain", "text": error_msg}]
            )

    @filter.command("ahut_sign")
    async def ahut_sign(self, event: AstrMessageEvent):
        """手动触发时只返回失败用户"""
        try:
            failed_users = await self.fetch_failed_users()
            result = "⚠️失败用户列表：\n" if failed_users else "🎉今日没有签到失败用户"
            for user in failed_users:
                result += (
                    f"\n用户名：{user['username']}\n"
                    f"耗时：{user['duration']}\n"
                    f"错误信息：\n{user['message']}\n"
                )
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"处理异常：{str(e)}")

    async def terminate(self):
        """插件卸载时关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)