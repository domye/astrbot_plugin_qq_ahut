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
        """每天定时发送"""
        while True:
            now = datetime.now().time()
            if time(20, 22) <= now < time(20, 23):  # 调整为早上8点触发
                await self.send_to_group()
            await asyncio.sleep(60)

    def parse_web_data(self):
        """解析网页数据结构"""
        url = "http://sign.domye.top/"
        response = requests.get(url)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        # 解析汇总数据
        summary_div = soup.find('div', class_='summary')
        report_time = summary_div.find_all('p')[-1].text.split(": ")[1].strip()
        total_users = int(summary_div.find('p', string=lambda t: "👥 总人数" in t).text.split(": ")[1])
        success_count = int(summary_div.find('p', string=lambda t: "✅ 成功" in t).text.split(": ")[1])
        failure_count = int(summary_div.find('p', string=lambda t: "❌ 失败" in t).text.split(": ")[1])

        # 解析用户数据
        user_cards = soup.find_all('div', class_='user-card')
        results = []
        for card in user_cards:
            is_success = 'success' in card['class']
            username = card.find('h3').text.split(" ")[0]
            duration = card.find('p').text.split(": ")[1]
            message = card.find('pre').text.strip()
            
            results.append({
                "username": username,
                "success": is_success,
                "duration": duration,
                "message": message
            })

        return {
            "report_time": report_time,
            "total_users": total_users,
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results
        }

    def format_message(self, data):
        """格式化输出消息"""
        # 构建汇总信息
        summary = (
            "▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            "📝 宿舍签到汇总报告\n"
            f"👥 总人数: {data['total_users']}\n"
            f"✅ 成功: {data['success_count']}\n"
            f"❌ 失败: {data['failure_count']}\n"
            f"📅 报告时间: {data['report_time']}\n"
            "▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
        )

        # 构建详细信息
        details = []
        for user in data['results']:
            status_icon = "✅" if user['success'] else "❌"
            detail = (
                f"\n┌ {'▬'*20}\n"
                f"▫️ 用户: {user['username']} {status_icon}\n"
                f"⏱ 耗时: {user['duration']}\n"
                f"📝 {'详情' if user['success'] else '错误'}:\n"
                f"{user['message']}\n"
                f"└ {'▬'*20}"
            )
            details.append(detail)

        return summary + "\n" + "\n".join(details) if data['failure_count'] > 0 else summary + "\n🎉 全员签到成功！"

    async def send_to_group(self):
        """发送定时报告"""
        try:
            data = self.parse_web_data()
            formatted_msg = self.format_message(data)
            await self.context.send_message(
                unified_msg_origin=f"group_{self.group_id}",
                chain=[{"type": "plain", "text": formatted_msg}]
            )
        except Exception as e:
            print(f"定时任务异常: {str(e)}")

    @filter.command("ahut_sign")
    async def ahut_sign(self, event: AstrMessageEvent):
        """手动查询签到状态"""
        try:
            data = self.parse_web_data()
            brief_report = (
                "🔍 实时签到状态\n"
                f"✅ 成功: {data['success_count']}\n"
                f"❌ 失败: {data['failure_count']}\n"
                f"⏲ 最新报告时间: {data['report_time']}"
            )
            yield event.plain_result(brief_report)
        except Exception as e:
            yield event.plain_result(f"⚠️ 查询失败: {str(e)}")

    async def terminate(self):
        self.task.cancel()