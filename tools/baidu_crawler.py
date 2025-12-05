import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import random
from bs4.element import Tag

def crawl_baidu_news(keyword, max_count=20, max_pages=5):
    """
    爬取百度资讯搜索结果 (Generator Version)
    :param keyword: 搜索关键字
    :param max_count: 期望获取的最大数据量，默认为20
    :param max_pages: 最大爬取页数，默认为5
    :yield: 字典形式的新闻数据
    """
    base_url = "https://www.baidu.com/s"
    
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Cookie": "BAIDUID=CFAA73C2203E2E4943756281B8073CBE:FG=1; BDUSS=g3UmQyWXN0TFduQ2VuVHVZMWZJQ1o0SkNCcHBpOUVIMVFaYzVEWjVJbkQxVXRwSVFBQUFBJCQAAAAAAQAAAAEAAAAM8kWZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMNIJGnDSCRpLU; BDUSS_BFESS=g3UmQyWXN0TFduQ2VuVHVZMWZJQ1o0SkNCcHBpOUVIMVFaYzVEWjVJbkQxVXRwSVFBQUFBJCQAAAAAAQAAAAEAAAAM8kWZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMNIJGnDSCRpLU; BIDUPSID=CFAA73C2203E2E4943756281B8073CBE; PSTM=1764750643; BD_UPN=12314753; H_PS_PSSID=63148_65315_66100_66208_66231_66274_66262_66393_66469_66516_66529_66555_66586_66592_66604_66613_66652_66663_66677_66670_66687_66709_66741_66617_66785_66793_66803_66799_66599; BAIDUID_BFESS=CFAA73C2203E2E4943756281B8073CBE:FG=1; H_WISE_SIDS=63148_65315_66100_66208_66231_66274_66262_66393_66469_66516_66529_66555_66586_66592_66604_66613_66652_66663_66677_66670_66687_66709_66741_66617_66785_66793_66803_66799_66599; BDRCVFR[4Sa5I932hZT]=-_EV5wtlMr0mh-8uz4WUvY; BA_HECTOR=2l840h80a025alagal8ka58g0g042g1kj1k5c25; ZFY=Chp:B1KHMY1XLnKJaFUxm6MA0xWoH7ZOyjyYv2v0VaDQ:C; BD_CK_SAM=1; PSINO=1; delPer=0; BDORZ=FFFB88E999055A3F8A630C64834BD6D0; channel=bing; SMARTINPUT=%5Bobject%20Object%5D; H_PS_645EC=9f926h4Zh8DH%2F0N3a0bcv89RyiL1pLTc8RDBY4tgAadvVUeMCWEJj%2Fb5w3WR3IVaNOxhoQ; baikeVisitId=fabc5841-e9ae-409b-96b9-8fc844714301",
        "Host": "www.baidu.com",
        "Referer": "https://cn.bing.com/",
        "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Microsoft Edge";v="122"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
    }

    count = 0
    seen_urls = set()
    seen_titles = set() # 增加标题去重
    page = 0
    max_pages = 5 # 防止无限循环，最多爬取5页
    
    while count < max_count and page < max_pages:
        pn = page * 10
        print(f"正在爬取第 {page + 1} 页 (pn={pn})...")
        
        params = {
            "rtt": "1",
            "bsst": "1",
            "cl": "2",
            "tn": "news",
            "rsv_dl": "ns_pc",
            "word": keyword,
            "pn": str(pn)
        }

        try:
            response = requests.get(base_url, params=params, headers=headers)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                print(f"Request failed with status code: {response.status_code}")
                break

            # 保存HTML文件以便调试
            with open(f'debug_baidu_page_{page}.html', 'w', encoding='utf-8') as f:
                f.write(response.text)

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找所有的新闻结果容器
            # 尝试不同的选择器以适应百度可能的页面结构变化
            news_items = soup.select('.result-op.c-container')
            
            if not news_items:
                print("No news items found with primary selector. Trying fallback...")
                news_items = soup.select('.result')
            
            if not news_items:
                print(f"第 {page + 1} 页未找到任何数据，停止爬取。")
                break

            for item in news_items:
                try:
                    # 标题
                    title_elem = item.select_one('h3 a')
                    title = title_elem.get_text(strip=True) if title_elem else "无标题"
                    original_url = title_elem['href'] if title_elem else ""
                    
                    # 去重
                    if original_url in seen_urls:
                        continue
                    
                    # 标题去重，避免因为百度链接不同但内容相同导致重复
                    if title in seen_titles:
                        continue
                        
                    seen_urls.add(original_url)
                    seen_titles.add(title)

                    def _pick_src(e):
                        for k in ['src','data-src','data-ori','data-original','data-thumb','data-lazyload']:
                            v = e.get(k)
                            if v and v.strip():
                                return v.strip()
                        return ''
                    def _cover_from_item(it):
                        candidates = [
                            it.select_one('.c-img'),
                            it.select_one('.img_1gB26'),
                            it.select_one('img.c-img'),
                            it.select_one('img')
                        ]
                        for e in candidates:
                            if e:
                                s = _pick_src(e)
                                if s:
                                    return s
                        return ''
                    cover_url = _cover_from_item(item)
                    # Skip deep cover extraction for speed in streaming mode
                    # if not cover_url and original_url:
                    #     # Deep cover extraction logic removed to improve response speed
                    #     pass
                    
                    # 来源
                    source_elem = item.select_one('.c-color-gray')
                    if not source_elem:
                        source_elem = item.select_one('.c-color-gray2') # 备选来源选择器
                    if not source_elem:
                        source_elem = item.select_one('.source_1Vdff') # 百度资讯新版结构
                    source = source_elem.get_text(strip=True) if source_elem else "未知来源"
                    
                    news_data = {
                        "title": title,
                        "cover": cover_url,
                        "url": original_url,
                        "source": source
                    }
                    yield news_data
                    count += 1
                    
                    if count >= max_count:
                        break
                    
                except Exception as e:
                    print(f"Error parsing item: {e}")
                    continue
            
            if count >= max_count:
                break

            page += 1
            # 随机延时，避免被封
            time.sleep(random.uniform(1, 2))
            
        except Exception as e:
            print(f"Crawler error on page {page}: {e}")
            break

import json
from lxml import etree

def collect_content_by_rule(url, title_xpath, content_xpath, headers_str, timeout=15):
    """
    使用指定的规则爬取详细内容
    :param url: 目标URL
    :param title_xpath: 标题XPath
    :param content_xpath: 内容XPath
    :param headers_str: JSON字符串形式的headers
    :return: (title, content) 如果失败则返回None
    """
    try:
        headers = {}
        if headers_str:
            try:
                headers = json.loads(headers_str)
            except:
                pass
        
        if not headers:
             headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
            
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        
        if resp.status_code != 200:
            return None
            
        html = etree.HTML(resp.text)
        if html is None:
            return None
            
        title = ""
        content = ""
        
        if title_xpath:
            t_nodes = html.xpath(title_xpath)
            if t_nodes:
                # lxml returns list of elements or strings
                if isinstance(t_nodes[0], str):
                    title = t_nodes[0].strip()
                elif hasattr(t_nodes[0], 'text'):
                    title = "".join([n.xpath('string(.)') for n in t_nodes]).strip()
                else:
                    title = str(t_nodes[0]).strip()

        if content_xpath:
            c_nodes = html.xpath(content_xpath)
            if c_nodes:
                # Aggregate content from all matched nodes
                parts = []
                for node in c_nodes:
                    if isinstance(node, str):
                        parts.append(node.strip())
                    elif hasattr(node, 'xpath'):
                        # Use string(.) to get all text within the node
                        parts.append(node.xpath('string(.)').strip())
                    else:
                        parts.append(str(node).strip())
                content = "\n".join([p for p in parts if p])
                
        return title, content
    except Exception as e:
        print(f"Rule crawl error: {e}")
        return None

import re

def deep_collect_content(url, timeout=10):
    """
    深度采集指定URL的内容 (Optimized Version)
    :param url: 目标URL
    :return: 清洗后的正文内容
    """
    try:
        data = generic_extract(url, timeout=timeout)
        return data.get('content', '')
    except Exception:
        return ""

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

def generic_extract(url, timeout=10):
    """
    通用提取器：提取标题、正文、封面、来源
    :return: dict
    """
    try:
        headers = {
             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
             "Referer": "https://www.baidu.com/",
             "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
             "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
             "Cookie": "BAIDUID=CFAA73C2203E2E4943756281B8073CBE:FG=1;"
        }
        
        host = urllib.parse.urlparse(url).netloc
        
        # Special handling for baijiahao using curl_cffi if available
        if 'baijiahao.baidu.com' in host and HAS_CURL_CFFI:
             try:
                 print(f"DEBUG: Using curl_cffi for {url}")
                 resp = curl_requests.get(
                     url, 
                     impersonate="chrome124",
                     headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                     },
                     timeout=timeout
                 )
             except Exception as e:
                 print(f"curl_cffi failed, falling back to requests: {e}")
                 resp = requests.get(url, timeout=timeout, headers=headers)
        else:
             resp = requests.get(url, timeout=timeout, headers=headers)
        
        # Encoding detection improvement
        if hasattr(resp, 'apparent_encoding'):
            encoding = resp.apparent_encoding
            if 'charset=gb2312' in resp.text.lower() or 'charset=gbk' in resp.text.lower():
                 encoding = 'gb18030'
            resp.encoding = encoding or 'utf-8'
        elif hasattr(resp, 'encoding') and hasattr(resp, 'charset'):
             # For curl_cffi, it might not have apparent_encoding but has charset
             if 'charset=gb2312' in resp.text.lower() or 'charset=gbk' in resp.text.lower():
                 resp.encoding = 'gb18030'
        
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 1. Clean up: remove script, style, etc.
        # But be careful, some sites (like baijiahao) might have content in scripts (e.g. JSON) if dynamic
        # For now, we keep script removal but maybe parse JSON if needed.
        for tag in soup(['script', 'style', 'iframe', 'noscript', 'header', 'footer', 'nav', 'meta', 'link']):
            tag.decompose()
            
        # 2. Extract Title
        title = ""
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
        if not title:
            title = soup.title.get_text(strip=True) if soup.title else ""
            
        # 3. Extract Content (Density based + Selectors)
        content = ""
        
        # Specific domain logic (simplified)
        host = urllib.parse.urlparse(url).netloc
        candidates = []
        if 'baijiahao.baidu.com' in host:
            # Baijiahao often has content in specific classes
            candidates = [
                '.index-module_articleWrap_2Zphx', # New class often seen
                '.article-content', 
                '.content', 
                '#article', 
                'article',
                'div[class*="article-content"]',
                'div[class*="index-module_article"]'
            ]
        elif 'mp.weixin.qq.com' in host:
             candidates = ['#js_content', '.rich_media_content']
        else:
            candidates = ['article', '#content', '.content', '.article', '.post', '.entry-content', '.news-content', '.main-content', '.detail-content']
            
        for sel in candidates:
            elem = soup.select_one(sel)
            if elem:
                content = elem.get_text("\n", strip=True)
                if len(content) > 100:
                    break
        
        # Fallback: Density Analysis
        if not content or len(content) < 50:
            # Find the block element with the most text
            max_len = 0
            best_elem = None
            for tag in soup.find_all(['div', 'section', 'td', 'li']):
                # Simple heuristic: text length minus tag overhead
                txt = tag.get_text(strip=True)
                if len(txt) > max_len:
                    # Check link density
                    links = tag.find_all('a')
                    link_text_len = sum([len(a.get_text(strip=True)) for a in links])
                    if len(txt) > 0 and (link_text_len / len(txt)) < 0.5: # Less than 50% link text
                        max_len = len(txt)
                        best_elem = tag
            
            if best_elem:
                content = best_elem.get_text("\n", strip=True)

        # 4. Clean content
        # Remove common noise
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        content = "\n".join(lines)
        
        # Invalid content keywords filter
        invalid_keywords = [
            "403 Forbidden", "404 Not Found", "访问受限", "验证码", 
            "JavaScript is required", "Please turn on JavaScript",
            "Browser not supported", "浏览器版本过低"
        ]
        if any(kw in content[:200] for kw in invalid_keywords):
            content = ""

        return {
            "title": title,
            "content": content[:5000], # Limit length
            "url": url
        }
    except Exception as e:
        print(f"Generic extract error: {e}")
        return {}


def crawl_xinhua_sc_news(max_count=20):
    """
    爬取新华网四川新闻页，返回与百度新闻一致的数据结构 (Generator Version)
    数据源: http://sc.news.cn/scyw.htm
    yield: Dict，每项包含 title, cover, url, source
    """
    base_url = "http://sc.news.cn/scyw.htm"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    count = 0
    seen = set()
    try:
        r = requests.get(base_url, headers=headers, timeout=10)
        r.encoding = r.apparent_encoding or 'utf-8'
        if r.status_code != 200:
            return
        soup = BeautifulSoup(r.text, 'html.parser')

        def pick_src(e):
            for k in ['src','data-src','data-ori','data-original','data-thumb','data-lazyload']:
                v = e.get(k)
                if v and v.strip():
                    return v.strip()
            return ''

        def extract_cover_from_page(url):
            try:
                rr = requests.get(url, headers=headers, timeout=8)
                rr.encoding = rr.apparent_encoding or 'utf-8'
                if rr.status_code != 200:
                    return ''
                sp = BeautifulSoup(rr.text, 'html.parser')
                metas = [
                    sp.find('meta', attrs={'property':'og:image'}),
                    sp.find('meta', attrs={'name':'og:image'}),
                    sp.find('meta', attrs={'property':'twitter:image'}),
                    sp.find('meta', attrs={'name':'twitter:image'})
                ]
                for m in metas:
                    if m:
                        c = (m.get('content') or '').strip()
                        if c:
                            return urllib.parse.urljoin(url, c)
                l = sp.find('link', rel='image_src')
                if l:
                    h = (l.get('href') or '').strip()
                    if h:
                        return urllib.parse.urljoin(url, h)
                # 尝试从可能的样式背景图中提取
                bg_candidates = sp.select('.pic, .image, .cover, .thumb, .poster')
                for bg in bg_candidates:
                    style = (bg.get('style') or '')
                    if 'background-image' in style:
                        import re
                        m = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
                        if m and m.group(1):
                            return urllib.parse.urljoin(url, m.group(1))
                # 兜底：扫描脚本中的图片链接
                import re
                for sc in sp.find_all('script'):
                    txt = sc.string or sc.text or ''
                    if not txt:
                        continue
                    m = re.search(r"https?://[^\s'\"]+\.(?:jpg|jpeg|png|gif|webp)", txt, re.IGNORECASE)
                    if m:
                        return urllib.parse.urljoin(url, m.group(0))
                ig = sp.select_one('article img') or sp.select_one('.article img') or sp.select_one('.content img') or sp.select_one('.news-content img') or sp.find('img')
                if ig:
                    s = pick_src(ig)
                    if s:
                        return urllib.parse.urljoin(url, s)
                return ''
            except Exception:
                return ''

        # 主要与备用选择器，尽量适配常见新华列表结构
        item_selectors = [
            'div.dataList li',
            '#dataList li',
            'div.news_list li',
            '#news_list li',
            'ul.list li',
            '.content_list li',
            '.newsList li',
            '.newslist li'
        ]
        items = []
        for sel in item_selectors:
            items = soup.select(sel)
            if items:
                break
        if not items:
            # 兜底：寻找包含链接的块级元素
            items = soup.select('a')

        for it in items:
            # 提取链接与标题
            a = it if it.name == 'a' else it.select_one('a')
            if not a:
                continue
            title = a.get_text(strip=True) or (a.get('title') or '').strip()
            href = (a.get('href') or '').strip()
            if not href or not title:
                continue
            url = urllib.parse.urljoin(base_url, href)
            if url in seen:
                continue
            seen.add(url)

            # 提取封面
            cover = ''
            img = it.select_one('img') if it and it != a else None
            if img:
                s = pick_src(img)
                if s:
                    cover = urllib.parse.urljoin(base_url, s)
            if not cover:
                cover = extract_cover_from_page(url)
            # 针对部分新华子域名提供兜底封面
            if not cover:
                host = urllib.parse.urlparse(url).netloc
                if 'app.xinhuanet.com' in host or 'xinhuaxmt.com' in host:
                    cover = 'https://lib.news.cn/common/sharelogo.jpg'

            # 来源固定标注为新华网（四川）或页面来源文本
            source = '新华网'
            src_el = it.select_one('.source') or it.select_one('.news_source')
            if src_el:
                st = src_el.get_text(strip=True)
                if st:
                    source = st

            yield {
                'title': title,
                'cover': cover,
                'url': url,
                'source': source
            }
            count += 1
            if count >= max_count:
                break

    except Exception:
        pass

if __name__ == "__main__":
    keyword = "西昌"
    print(f"开始爬取关键字: {keyword}")
    data_gen = crawl_baidu_news(keyword)
    
    results = []
    for i, item in enumerate(data_gen, 1):
        print(f"\n[{i}]")
        print(f"标题: {item['title']}")
        print(f"封面: {item['cover']}")
        print(f"原始URL: {item['url']}")
        print(f"来源: {item['source']}")
        results.append(item)

    if results:
        print(f"共抓取到 {len(results)} 条数据")
    else:
        print("未抓取到任何数据。")
