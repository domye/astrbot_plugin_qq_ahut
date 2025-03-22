from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import requests
from bs4 import BeautifulSoup
import astrbot.api.message_components as Comp
import asyncio

@register("checkin_monitor", "EDU_TEAM", "宿舍签到监控系统", "1.0.0")
class CheckinMonitor(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.failed_students = []
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cache-Control": "no-cache"
        }
        asyncio.create_task(self.schedule_check())  # 初始化定时任务

    async def schedule_check(self):
        """定时监控任务"""
        while True:
            await asyncio.sleep(3600)  # 每小时执行一次
            if self.failed_students:
                await self.send_failure_report()

    async def fetch_checkin_data(self, url: str):
        """获取签到数据"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            self.logger.error(f"数据获取失败: {str(e)}")
            return None

    def parse_failures(self, soup):
        """解析失败数据"""
        failures = []
        for card in soup.find_all('div', class_='user-card error'):
            student_id = card.get('data-id')  # 假设学号存储在data-id属性
            username = card.find('h3').text.split()[0]
            duration = card.find('p', string=lambda t: "耗时" in t).text
            failures.append({
                "id": student_id,
                "name": username,
                "duration": duration
            })
        return failures

    async def send_failure_report(self):
        """发送失败报告"""
        report = ["❌ 签到失败名单"]
        for idx, student in enumerate(self.failed_students, 1):
            report.append(
                f"{idx}. {student['id']} {student['name']}"
                f"\n⏱ 耗时: {student['duration']}"
            )
        
        await self.context.send_message(
            target="ADMIN_CHANNEL",  # 预设管理频道
            message=Comp.Text("\n\n".join(report)).card_style("#ffe6e6")
        )

    @filter.command("check_failures")
    async def check_failures(self, event: AstrMessageEvent, url: str):
        """即时检查失败名单
        示例：/check_failures https://example.com/checkin
        """
        soup = await self.fetch_checkin_data(url)
        if not soup:
            yield event.plain_result("数据获取失败，请检查URL")
            return

        self.failed_students = self.parse_failures(soup)
        if not self.failed_students:
            yield event.plain_result("🎉 当前无签到失败记录")
            return

        # 构建富文本消息
        result = event.make_result()
        result.message("📋 最新失败名单").bold().divider()
        
        for student in self.failed_students:
            result.message(
                f"学号: {student['id']}\n"
                f"姓名: {student['name']}\n"
                f"耗时: {student['duration']}"
            ).divider()
        
        yield result

    @filter.command("set_schedule")
    async def set_schedule(self, event: AstrMessageEvent, interval: int):
        """设置定时监控间隔（小时）
        示例：/set_schedule 2
        """
        global CHECK_INTERVAL
        CHECK_INTERVAL = interval * 3600
        yield event.plain_result(f"✅ 监控间隔已设置为每{interval}小时")