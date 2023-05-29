import urllib.request
from xml.etree import ElementTree as etree
from typing import List
from pacroller.config import DEF_HTTP_HDRS

def get_news(old_news: str) -> List[str]:
    ARCH_RSS_URL = 'https://archlinux.org/feeds/news/'
    req = urllib.request.Request(ARCH_RSS_URL, data=None, headers=DEF_HTTP_HDRS)
    rss_text = urllib.request.urlopen(req).read().decode('utf-8')

    xml_root = etree.fromstring(rss_text)
    elements: List[etree.Element] = xml_root.findall('channel/item')

    news: List[str] = list()
    for elem in elements:
        title = elem.findtext('title') or 'No title'
        link = elem.findtext('link') or ''
        date = elem.findtext('pubDate') or 'No date'
        news.append(f"{date} | {title} ({link})".rstrip())
    return news[:news.index(old_news)] if old_news in news else news

if __name__ == '__main__':
    from pathlib import Path
    f = Path('/tmp/pacroller-news.db')
    if f.exists():
        old_news = f.read_text()
    else:
        old_news = None
    news = get_news(old_news)
    if news:
        f.write_text(news[0])
        for i in news:
            print(i)
    else:
        print(f'nothing new, {old_news=}')
