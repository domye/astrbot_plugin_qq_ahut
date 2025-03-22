from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import requests
from bs4 import BeautifulSoup

@register("web_data_scraper", "Your Name", "抓取网页数据的插件", "1.0.0")
class WebDataScraperPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("scrape_web_data")
    async def scrape_web_data(self, event: AstrMessageEvent):
        url = "http://your_webpage_url"  # 请将这里替换为实际的网页地址
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        summary = soup.find('div', class_='summary')
        total_users = summary.find('p').text.split(': ')[1]
        success_count = summary.find_all('p')[1].text.split(': ')[1]
        failure_count = summary.find_all('p')[2].text.split(': ')[1]

        user_cards = soup.find_all('div', class_='user-card')
        user_data = []
        for card in user_cards:
            username = card.find('h3').text.split(' ')[0]
            success_status = card.find('h3').text.split(' ')[1] == "✅"
            duration = card.find('p').text.split(': ')[1]
            message = card.find('details').find('pre').text.replace("<br>", "\n")
            user_data.append({
                "username": username,
                "success": success_status,
                "duration": duration,
                "message": message
            })

        result = f"总人数: {total_users}\n成功人数: {success_count}\n失败人数: {failure_count}\n"
        for user in user_data:
            result += f"\n用户名: {user['username']}\n成功状态: {user['success']}\n耗时: {user['duration']}\n消息: {user['message']}\n"

        yield event.plain_result(result)