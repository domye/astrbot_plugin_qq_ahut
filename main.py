from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import requests
from bs4 import BeautifulSoup

@register("sign_monitor", "Your Name", "宿舍签到状态查询插件", "1.1.0")
class SignMonitorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    def _parse_web_data(self):
        """核心数据解析方法"""
        try:
            response = requests.get("http://sign.domye.top/", timeout=10)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')

            # 解析汇总数据
            summary = soup.find('div', class_='summary')
            report_time = summary.find('p', text=lambda t: t and '报告生成时间' in t).text.split(': ')[1]
            total = int(summary.find('p', text=lambda t: t and '👥 总人数' in t).text.split(': ')[1])
            success = int(summary.find('p', text=lambda t: t and '✅ 成功' in t).text.split(': ')[1])

            # 解析详细数据
            failures = []
            for card in soup.find_all('div', class_='user-card'):
                if 'error' in card['class']:
                    username = card.find('h3').text.split(' ')[0]
                    duration = card.find('p').text.split(': ')[1]
                    error_log = card.find('pre').text.strip()
                    failures.append(f"【{username}】\n⏱ {duration}\n📝 {error_log}")

            return {
                "time": report_time,
                "total": total,
                "success": success,
                "failures": failures
            }

        except Exception as e:
            raise RuntimeError(f"数据解析失败: {str(e)}")

    @filter.command("sign")
    async def query_sign_status(self, event: AstrMessageEvent):
        """触发签到状态查询"""
        try:
            data = self._parse_web_data()
            failure_count = data['total'] - data['success']
            
            # 构建消息模板
            report = (
                "🔔 宿舍签到实时监控\n"
                f"🕒 报告时间: {data['time']}\n"
                f"👥 总人数: {data['total']}\n"
                f"✅ 成功: {data['success']}\n"
                f"❌ 失败: {failure_count}"
            )

            # 添加失败详情
            if failure_count > 0:
                report += "\n\n📜 失败清单:\n" + "\n▬▬▬▬▬\n".join(data['failures'])
            
            yield event.plain_result(report)

        except RuntimeError as e:
            yield event.plain_result(f"⚠️ {str(e)}")
        except Exception as e:
            yield event.plain_result(f"❌ 系统异常: {str(e)}")