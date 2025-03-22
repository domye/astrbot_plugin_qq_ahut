from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import requests
from bs4 import BeautifulSoup
import asyncio
from datetime import datetime, time

@register("web_data_scraper", "Your Name", "抓取网页数据的插件", "1.0.0")
class WebDataScraperPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 添加群号配置（需在管理面板配置）
        self.group_id = "你的群号"  # 改为实际群号
        # 启动定时任务
        self.task = asyncio.create_task(self.scheduled_task())

    async def scheduled_task(self):
        """每天8点定时发送"""
        while True:
            now = datetime.now().time()
            if time(8, 0) <= now < time(8, 1):  # 每天8点触发
                await self.send_to_group()
            await asyncio.sleep(60)  # 每分钟检查一次

    async def send_to_group(self):
        """向指定群组发送数据"""
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
                if not success_status:  # 仅处理失败用户
                    duration = card.find('p').text.split(': ')[1]
                    message = card.find('details').find('pre').get_text('\n').strip()
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
                        f"错误信息：\n{user['message']}\n"
                    )
                # 发送到指定群组
                await self.context.send_message(
                    unified_msg_origin=f"group_{self.group_id}",
                    chain=[{"type": "plain", "text": result}]
                )
                
        except Exception as e:
            print(f"定时任务异常：{str(e)}")

    @filter.command("scrape_web_data")
    async def scrape_web_data(self, event: AstrMessageEvent):
        """手动触发时只返回失败用户"""
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
            
        except requests.RequestException as e:
            yield event.plain_result(f"请求失败：{str(e)}")
        except Exception as e:
            yield event.plain_result(f"处理异常：{str(e)}")

    async def terminate(self):
        """插件卸载时取消定时任务"""
        self.task.cancel()