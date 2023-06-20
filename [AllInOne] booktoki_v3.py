# coding: utf8
# title: Add Booktoki.com
# author: github.com/STR-HK/hdl-stubs
# comment: Created at 12022/12/10

from io import BytesIO
from utils import Soup, LazyUrl, Downloader, clean_title
import clf2


class Image(object):
    def __init__(self, src, name):
        ext = ".{}".format(src.split(".")[-1])
        if ext.lower()[1:] not in ["jpg", "jpeg", "bmp", "png", "gif", "webm", "webp"]:
            ext = ".jpg"
        self.filename = f"{name}{ext}"
        self.url = LazyUrl(src, lambda _: src, self)


@Downloader.register
class Downloader_Booktoki(Downloader):
    type = "booktoki"
    URLS = [r"regex:booktoki[0-9]*\.com"]
    MAX_CORE = 4
    icon = "https://booktoki153.com/img/book/favicon-32x32.png"

    def read(self):
        soup = get_soup(self.url)
        artist = self.get_artist(soup)
        title = f"[{artist}] {self.get_title(soup)} 全"
        self.artist = artist

        img_candidate = soup.find("div", class_="view-img").find("img")
        if img_candidate:
            src = img_candidate["src"]
            img = Image(src, "cover")
            self.urls.append(img.url)

        content_titles = []
        contents = []

        pages = get_pages_list(soup)
        self.print_(pages)
        for n, page in enumerate(pages):
            self.title = f"{title} ({n+1}/{len(pages)})"
            self.print_(f"Reading: {n+1}/{len(pages)}")
            pagesoup = get_soup(page)

            @try_n(4)
            def content_getter():
                try:
                    return get_content(pagesoup)
                except:
                    return get_content(get_soup(page))

            contents.append(content_getter().replace("&nbsp;", "\n"))

            @try_n(4)
            def title_getter():
                try:
                    return f"{n+1}화 | {get_page_title(pagesoup)}"
                except:
                    return f"{n+1}화 | {get_page_title(get_soup(page))}"

            content_titles.append(title_getter())

        full_content = ""
        for n in range(len(content_titles)):
            full_content += content_titles[n]
            full_content += "\n\n"
            full_content += contents[n]
            full_content += "\n\n\n"
        full_content += "終"

        f = BytesIO()
        f.write(full_content.encode("UTF-8"))
        f.seek(0)

        self.filenames[f] = title + ".txt"
        self.urls.append(f)

        self.title = title

    def get_info_list(self, soup: Soup) -> list:
        """-> [title, [platform, tags, artist], summary]"""
        infobox = soup.find("div", class_="col-sm-8")
        contents = infobox.find_all("div", class_="view-content")
        details = contents[1].get_text().split("\xa0")
        for n, detail in enumerate(details):
            details[n] = detail.strip()
        return [
            contents[0].get_text().strip(),
            details,
            contents[2].get_text().strip(),
        ]

    def get_title(self, soup: Soup):
        return self.get_info_list(soup)[0]

    def get_artist(self, soup: Soup):
        return self.get_info_list(soup)[1][2]


def get_soup(url: str):
    return Soup(clf2.solve(url)["html"])


def get_pages_list(soup: Soup):
    pages_list = []
    list_body = soup.find("ul", class_="list-body")
    list_items = list_body.find_all("li", class_="list-item")
    for list_item in list_items:
        page = list_item.find("a")["href"]
        pages_list.append(page)
    pages_list.reverse()
    return pages_list


def get_content(soup: Soup):
    novel = soup.find("div", {"id": "novel_content"})
    ps = novel.find_all("p")
    if len(novel.find_all("p")) != 0:
        text = ""
        for n, p in enumerate(ps):
            if p.get_text() != "":
                text += p.get_text()
            else:
                text += "\n"
            text += "\n"
    else:
        text = novel.get_text()
    return text


def get_page_title(soup: Soup):
    full = soup.find("div", class_="toon-title")
    span = full.find("span").get_text()
    title = full.get_text().replace(span, "").strip()
    return clean_title(title)


log(f"Site Added: Booktoki")
