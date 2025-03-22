from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, AtAll
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime, time, timedelta
import logging

logger = logging.getLogger(__name__)

@register("dorm_checkin", "宿舍签到监控", "自动抓取宿舍签到状态并推送群消息", "1.1.0")
class DormCheckinPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = self.context.get_config().get("dorm_checkin", {})
        self.session = aiohttp.ClientSession()
        asyncio.create_task(self.scheduler())

    async def scheduler(self):
        """精准定时任务调度"""
        while True:
            now = datetime.now()
            target_time = datetime.combine(now.date(), time(9, 30))
            if now >= target_time:
                target_time += timedelta(days=1)
            
            delay = (target_time - now).total_seconds()
            await asyncio.sleep(delay)
            
            try:
                data = await self.fetch_data()
                await self.send_report(data)
            except Exception as e:
                logger.error(f"定时任务执行失败: {str(e)}")
            await asyncio.sleep(60)  # 防止重复执行

    async def fetch_data(self):
        """增强型网页抓取"""
        try:
            async with self.session.get(
                self.config.get("web_url", ""),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return self.parse_html(await response.text())
                return None
        except Exception as e:
            logger.error(f"网络请求异常: {str(e)}")
            return None

    def parse_html(self, html):
        """稳健的HTML解析"""
        soup = BeautifulSoup(html, "lxml")
        
        # 解析汇总数据
        summary = soup.find("div", class_="summary")
        total = int(summary.find("p", string=lambda t: "总人数" in t).text.split(":")[1].strip())
        success = int(summary.find("p", style="color: #28a745;").text.split(":")[1].strip())
        
        # 解析失败学号
        failures = []
        for card in soup.find_all("div", class_="user-card"):
            if "error" in card["class"]:
                username = card.find("h3").text.split()[0].strip()
                failures.append(username)
        
        return {
            "total": total,
            "success": success,
            "failures": failures,
            "failure_count": len(failures)
        }

    async def send_report(self, data):
        """增强消息链构建"""
        if not data or not self.config.get("qq_group"):
            return
        
        chain = [Plain("📢 宿舍签到报告\n")]
        
        if data["failure_count"] == 0:
            chain.append(Plain(f"✅ 全员签到成功！总人数：{data['total']}"))
        else:
            chain.extend([
                AtAll(),
                Plain(f"❌ 签到失败！失败人数：{data['failure_count']}\n"),
                Plain("失败学号列表：\n" + "\n".join(data["failures"]))
            ])
        
        await self.context.send_message(
            unified_msg_origin=f"group::{self.config['qq_group']}",
            message_chain=chain
        )

    @filter.command("set_group")
    async def set_group(self, event: AstrMessageEvent, group_id: str):
        """设置监控群号"""
        if not group_id.isdigit():
            yield event.plain_result("❌ 群号必须为纯数字")
            return
        
        self.config["qq_group"] = group_id
        self.context.get_config()["dorm_checkin"] = self.config
        self.context.get_config().save_config()
        yield event.plain_result(f"✅ 监控群号已设置为：{group_id}")

    @filter.command("set_url")
    async def set_url(self, event: AstrMessageEvent, url: str):
        """设置监控地址"""
        if not url.startswith(("http://", "https://")):
            yield event.plain_result("❌ URL必须以http://或https://开头")
            return
        
        self.config["web_url"] = url
        self.context.get_config()["dorm_checkin"] = self.config
        self.context.get_config().save_config()
        yield event.plain_result(f"✅ 监控地址已设置为：{url}")

    async def terminate(self):
        """清理资源"""
        await self.session.close()