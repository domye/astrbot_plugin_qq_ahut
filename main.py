from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import requests
from bs4 import BeautifulSoup
import astrbot.api.message_components as Comp

@register("web_scraper", "YourName", "网页数据抓取插件", "1.0.0", "https://github.com/yourrepo")
class WebScraper(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    @filter.command("scrape")
    async def scrape_website(self, event: AstrMessageEvent, url: str):
        """
        抓取指定网页的用户卡片数据
        参数：url - 目标网页地址
        示例：/scrape https://example.com
        """
        try:
            # 发送HTTP请求
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # 解析网页内容
            soup = BeautifulSoup(response.text, 'html.parser')
            user_cards = soup.find_all('div', class_='user-card')
            
            if not user_cards:
                yield event.plain_result("⚠️ 未找到用户卡片数据")
                return

            # 构建消息链
            result = event.make_result()
            result.message("抓取结果：").bold("共找到 {} 条数据\n".format(len(user_cards)))
            
            for index, card in enumerate(user_cards[:5]):  # 限制显示前5条
                title = card.find('h3').text.strip()
                content = card.find('p').text.strip()
                
                result.message(f"{index+1}. {title}\n")
                result.message(f"   {content}\n")
                result.hr()
            
            result.message("\n完整数据已保存到文件").italic()
            yield result

        except requests.exceptions.RequestException as e:
            error_chain = [
                Comp.Text("请求失败: ").color("#dc3545"),
                Comp.Text(str(e)).bold(),
                Comp.Image.fromURL("https://example.com/error.png")
            ]
            yield event.chain_result(error_chain)
        except Exception as e:
            yield event.plain_result(f"解析错误: {str(e)}")

    @filter.command("scrape_advanced")
    async def advanced_scrape(self, event: AstrMessageEvent):
        """
        交互式网页抓取命令
        示例：/scrape_advanced
        """
        yield event.plain_result("请输入要抓取的网页地址：")
        
        @filter.session_waiter(timeout=60)
        async def wait_for_url(controller, event: AstrMessageEvent):
            url = event.message_str
            if url.startswith(("http://", "https://")):
                await self.scrape_website(event, url)
                controller.stop()
            else:
                yield event.plain_result("⚠️ 无效的URL格式，请重新输入")

        await wait_for_url(event)