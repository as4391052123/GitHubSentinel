# src/hacker_news_client.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime  # 导入datetime模块用于获取日期和时间
import os  # 导入os模块用于文件和目录操作
from logger import LOG  # 导入日志模块


def _parse_stories(soup):
    # 查找包含新闻的所有 <tr> 标签
    soup_stories = soup.find_all('tr', class_='athing')

    top_stories = []
    for soup_story in soup_stories:
        title_tag = soup_story.find('span', class_='titleline').find('a')
        if title_tag:
            title = title_tag.text
            link = title_tag.get('href', '')  # 防止链接为空
            top_stories.append({'title': title, 'link': link})

    return top_stories


class HackerNewsClient:
    BASE_URL = 'https://news.ycombinator.com/'

    def fetch_hackernews_top_stories(self):
        try:
            response = requests.get(self.BASE_URL)
            response.raise_for_status()  # 检查请求是否成功
            soup = BeautifulSoup(response.text, 'html.parser')
            return _parse_stories(soup)
        except requests.RequestException as e:
            LOG.error(f"获取Hacker News的热门新闻失败：{str(e)}")
            return []

    def export_top_stories(self, date=None, hour=None):
        """
        导出热点新闻到指定目录下的 Markdown 文件。
        :param date: 日期，格式为2024-12-03 默认为None
        :param hour: 时间
        """
        LOG.info("准备导出Hacker News的热门新闻。")
        top_stories = self.fetch_hackernews_top_stories()
        if not top_stories:
            LOG.error("无法获取Hacker News的热门新闻。")
            return None
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        if hour is None:
            hour = datetime.now().strftime('%H')
        # 拼接存储路径
        dir_path = os.path.join("daily_progress", 'hacker_news', date)
        os.makedirs(dir_path, exist_ok=True)  # 确保目录存在
        file_path = os.path.join(dir_path, f'{hour}.md')  # 定义文件路径
        with open(file_path, 'w', encoding='utf-8') as f:
            if top_stories:
                for story_idx, story_content in enumerate(top_stories, start=1):
                    f.write(f"{story_idx}. [{story_content['title']}]({story_content['link']})\n")
            else:
                f.write("No stories found.\n")
        LOG.info(f"Hacker News热门新闻文件生成：{file_path}")
        return file_path

if __name__ == "__main__":
    hacker_news_client = HackerNewsClient()
    hacker_news_client.export_top_stories()  # 默认情况下使用当前日期和时间