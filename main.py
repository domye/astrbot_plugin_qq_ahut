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
        self.group_id = "626778303"  # 改为实际群号
        self.task = asyncio.create_task(self.scheduled_task())

    async def scheduled_task(self):
        """每天8点定时发送"""
        while True:
            now = datetime.now().time()
            if time(8, 0) <= now < time(8, 1):
                await self.send_to_group()
            await asyncio.sleep(60)

    async def parse_web_data(self):
        """解析网页数据并返回结构化信息"""
        url = "http://sign.domye.top/"
        response = requests.get(url)
        response.encoding = 'utf-8'
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 解析报告时间（根据实际网页结构调整选择器）
        time_element = soup.find('div', class_='summary').find_all('p')[-1]
        report_time = time_element.text.split(': ')[1].strip()
        
        # 解析用户数据
        user_cards = soup.find_all('div', class_='user-card')
        total = len(user_cards)
        success = 0
        failed_users = []
        
        for card in user_cards:
            username = card.find('h3').text.split(' ')[0]
            is_success = "✅" in card.find('h3').text
            
            if is_success:
                success += 1
            else:
                duration = card.find('p').text.split(': ')[1]
                message = card.find('details').find('pre').get_text('\n').strip()
                failed_users.append({
                    "username": username,
                    "duration": duration,
                    "message": message
                })
        
        return {
            "report_time": report_time,
            "total": total,
            "success": success,
            "failed_users": failed_users
        }

    async def send_to_group(self):
        """向指定群组发送完整报告"""
        try:
            data = await self.parse_web_data()
            
            summary = (
                "📝 宿舍签到汇总报告\n"
                f"👥 总人数: {data['total']}\n"
                f"✅ 成功: {data['success']}\n"
                f"❌ 失败: {data['total'] - data['success']}\n"
                f"📅 报告生成时间: {data['report_time']}\n"
            )
            
            if data['failed_users']:
                details = "\n⚠️ 失败详情：\n"
                for user in data['failed_users']:
                    details += (
                        f"\n▫️ 用户：{user['username']}\n"
                        f"⏱ 耗时：{user['duration']}\n"
                        f"📝 错误：\n{user['message']}\n"
                    )
                full_msg = summary + details
            else:
                full_msg = summary + "\n🎉 全员签到成功！"

            await self.context.send_message(
                unified_msg_origin=f"group_{self.group_id}",
                chain=[{"type": "plain", "text": full_msg}]
            )
            
        except Exception as e:
            print(f"定时任务异常：{str(e)}")

    @filter.command("ahut_sign")
    async def ahut_sign(self, event: AstrMessageEvent):
        """手动查询签到情况"""
        try:
            data = await self.parse_web_data()
            
            report = (
                "📋 最新签到统计\n"
                f"👥 总人数: {data['total']}\n"
                f"✅ 成功: {data['success']}\n"
                f"❌ 失败: {data['total'] - data['success']}\n"
                f"📅 报告时间: {data['report_time']}"
            )
            
            yield event.plain_result(report)
            
        except Exception as e:
            yield event.plain_result(f"❌ 查询失败：{str(e)}")

    async def terminate(self):
        self.task.cancel()