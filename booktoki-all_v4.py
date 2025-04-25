# coding: utf8
# title: Booktoki-All V4
# author: github.com/hyriph/hdl-stubs
# comment: Updated at 2025/04/25

from utils import (
    Soup,
    LazyUrl,
    Downloader,
    clean_title,
    Session,
    limits,
    check_alive,
    get_print,
)
from translator import tr_
import clf2
import ree as re
import page_selector
import utils

from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, parse_qs
from typing import TypedDict, Optional, Dict, List, Union
from io import BytesIO
from bs4 import Tag


class Image(object):
    def __init__(self, src, name):
        ext = ".{}".format(src.split(".")[-1])
        if ext.lower()[1:] not in ["jpg", "jpeg", "bmp", "png", "gif", "webm", "webp"]:
            ext = ".jpg"
        self.filename = f"{name}{ext}"
        self.url = LazyUrl(src, lambda _: src, self)


class Info(TypedDict):
    title: str
    platform: str
    tags: str
    artist: str
    summary: str


class Page:
    title: str
    url: str
    idx: int
    id: int

    def __init__(self, title: str, url: str, idx: int):
        self.title = clean_title(title)
        self.url = url
        self.idx = idx
        self.id = int(re.find(r"/novel/([0-9]+)", url, err="no id")[1])


#
# ---------------------- [ HELPER FUNCTION ] ----------------------
#


def compact_ranges(nums: List[int]) -> List[Union[int, List[int]]]:
    """
    주어진 정수 리스트에서 연속 구간을 압축해 돌려줍니다.

    예:
        >>> compact_ranges([1, 2, 3, 7, 9, 10, 11, 20])
        [[1, 3], 7, [9, 11], 20]
    """
    nums.sort()
    result: List[Union[int, List[int]]] = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:  # 같은 구간 안
            prev = n
            continue
        # 구간 종료 처리
        if start == prev:  # 구간 길이 1
            result.append(start)
        else:  # 구간 길이 ≥ 2
            result.append([start, prev])
        # 새 구간 시작
        start = prev = n
    # 마지막 구간 처리
    if start == prev:
        result.append(start)
    else:
        result.append([start, prev])
    return result


def humanize_compact_ranges(
    nums: List[int],
    *,
    suffix: str = "화",
    range_sep: str = "-",
    limit: Optional[int] = 10,
) -> str:
    """
    `compact_ranges()` 결과를 사람이 읽기 좋은 문자열로 변환합니다.

    Parameters
    ----------
    nums : list[int]
        원본 정수 리스트
    suffix : str, default ""
        각 숫자 뒤에 붙일 접미사(예: "화", "회" 등)
    range_sep : str, default "-"
        [start, end] 구간에서 start·end 사이에 들어갈 문자열
    limit : int | None, default None
        표시할 항목(구간‧단일 숫자) 최대 개수.
        초과 시 '…+n' 형식으로 남은 개수를 알려줍니다.

    Returns
    -------
    str
        예: `"1화-3화, 7화, 9화-11화, 20화"`
    """
    compacted = compact_ranges(nums)
    pieces: List[str] = []

    for item in compacted:
        if isinstance(item, list):  # [start, end]
            start, end = item
            piece = f"{start}{suffix}{range_sep}{end}{suffix}"
        else:  # 단일 숫자
            piece = f"{item}{suffix}"
        pieces.append(piece)

    if limit is not None and len(pieces) > limit:
        hidden = len(pieces) - limit
        pieces = pieces[:limit] + [f"…+{hidden}"]

    return ", ".join(pieces)


#
# ---------------------- [ DOWNLOADER ] ----------------------
#


@Downloader.register
class Downloader_Booktoki(Downloader):
    type = "booktoki"
    URLS = [r"regex:booktoki[0-9]*\.com"]
    MAX_CORE = 4
    # icon = ""
    ACCEPT_COOKIES = [r"(.*\.)?(mana|new)toki[0-9]*\.(com|net)"]
    ACCEPT_COOKIES = [r"(.*\.)?(mana|new)toki[0-9]*\.(com|net)"]

    session: Session
    soup: Soup

    @try_n(2)
    def init(self):
        self.session, self.soup = get_soup(self.url, cw=self.cw)
        self.url, query_dict = anal_url(self.url)

        # handle range_p from url input
        # parsed_query = parse_query_dict(query_dict)
        # if len(parsed_query) != 0:
        #     self.cw.range_p = parsed_query

    @try_n(4)
    def read_novel_page(self, page: Page):
        session, soup = get_soup(page.url, session=self.session, cw=self.cw)

        novel_title = get_novel_title(soup)
        novel_content = get_novel_content(soup)

        title = f"{page.idx}화 | {novel_title}"
        content = title + "\n\n" + novel_content + "\n\n\n"

        return content

    def read(self):
        self.title = tr_("읽는 중...")

        info = get_info(self.soup)
        self.artist = get_artist(info)
        title = get_title(info)

        # cover image is optional
        img_candidate: Tag | None = self.soup.find("div", class_="view-img").find("img")
        if img_candidate:
            src: str = img_candidate["src"]
            img = Image(src, "cover")
            self.urls.append(img.url)

        pages_ = get_pages(self.url, self.soup)
        # we can trust this because modification occurs in init
        filtered_pages: List[Page] = page_selector.filter(pages_, self.cw)

        # generate suffix based on range_p
        page_idx = [page.idx for page in filtered_pages]
        if len(pages_) == len(filtered_pages):
            suffix = "全"
        else:
            suffix = humanize_compact_ranges(page_idx, suffix="화", limit=10)
        full_title = f"[{self.artist}] {title} ({suffix})"

        full_content = ""

        for n, page in enumerate(filtered_pages):
            check_alive(self.cw)
            progress = f"{n + 1} / {len(filtered_pages)}"
            self.title = f"{full_title} ({progress})"
            self.print_(f"Reading: {progress}")
            page_content = self.read_novel_page(page)
            full_content += page_content

        f = BytesIO()
        f.write(full_content.encode("UTF-8"))
        f.seek(0)

        self.filenames[f] = full_title + ".txt"
        self.urls.append(f)

        self.title = full_title


@limits(10)
def get_soup(url, session: Optional[Session] = None, cw=None, win=None):
    if session is None:
        session = Session()
    virgin = True

    def f(html, browser=None):
        nonlocal virgin
        soup = Soup(html)
        if soup.find("form", {"name": "fcaptcha"}):  # 4660
            browser.show()
            if virgin:
                virgin = False
                browser.runJavaScript(
                    'window.scrollTo({top: document.getElementsByClassName("form-box")[0].getBoundingClientRect().top-150})'
                )  # 5504
            return False
        if not virgin:  # 7158
            browser.hide()
        return True

    res = clf2.solve(url, session=session, f=f, cw=cw, win=win)
    soup = Soup(res["html"], apply_css=True)

    return session, soup


#
# ---------------------- [ URL PARSING ] ----------------------
#


def anal_url(url: str):
    parsed = urlparse(url)
    query_dict = get_unique_query_params(url)
    url_without_query = parsed._replace(query="")
    return urlunparse(url_without_query), query_dict


def get_unique_query_params(url: str) -> Dict[str, str]:
    # original query to dict endures unnecessary dups
    query_list = parse_qsl(urlparse(url).query)
    result: Dict[str, str] = {}

    for key, value in query_list:
        if key not in result:
            # store only first value
            result[key] = value

    return result


def parse_query_dict(query_dict: Dict[str, str]):
    parsed = {}
    # list overrides everyting
    if "list" in query_dict:
        return [int(x) for x in query_dict["list"].split(",")]

    # min and max should be paired
    # considering about open interval
    match_pair = 0
    if "min" in query_dict:
        parsed["min"] = int(query_dict["min"])
        match_pair += 1
    if "max" in query_dict:
        parsed["max"] = int(query_dict["max"])
        match_pair += 1

    list_: List[int] = []
    if match_pair == 2:
        list_ = list(range(parsed["min"], parsed["max"] + 1))

    if "add" in query_dict:
        list_ += [int(x) for x in query_dict["add"].split(",")]

    return sorted(list_)


def add_spage_param(url: str, spage: int) -> str:
    """
    주어진 URL에 page 파라미터를 추가하거나 업데이트한 새 URL을 반환합니다.
    """
    parsed = urlparse(url)
    params: dict[str, str] = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params["spage"] = str(spage)

    new_query = urlencode(params)
    # _replace로 query만 교체한 새로운 ParseResult 생성
    rebuilt = parsed._replace(query=new_query)
    return urlunparse(rebuilt)


#
# ---------------------- [ PAGE READER ] ----------------------
#


def get_pagination(soup: Soup):
    """
    페이지네이션의 마지막 숫자를 가져옵니다.
    """
    pagination_box: Tag = soup.find("ul", class_="pagination")
    page_numbers: List[int] = [
        int(item.get_text(strip=True))
        for item in pagination_box.find_all("li")
        if item.get_text(strip=True).isdigit()
    ]
    return max(page_numbers, default=1)


def get_pages(base_url: str, base_soup: Soup, sub=False, cw=None, win=None):
    # 모든 페이지를 고려
    max_page = get_pagination(base_soup)
    spage = 1
    pages: List[tuple[str, str]] = []

    while spage <= max_page:
        url = add_spage_param(base_url, spage)
        session, soup = get_soup(url, cw=cw, win=win)
        list_body: Tag = soup.find("ul", class_="list-body")

        items: List[Tag] = list_body.find_all("li", class_="list-item")
        for item in items:
            for span in item.a.findAll("span"):
                span.decompose()
            anchor: Tag = item.find("a")
            title = anchor.get_text(strip=True)
            href: str = anchor["href"]
            pages.append((title, href))

        spage += 1

    titles = {}
    pages_: List[Page] = []
    for idx, (title, href) in enumerate(pages[::-1], start=1):
        title = utils.fix_dup(title, titles)  # 4161
        spage = Page(title, href, idx)
        pages_.append(spage)

    return pages_


#
# ---------------------- [ SELECT CHAPTER ] ----------------------
#


@page_selector.register("booktoki")
def f(url: str, win):
    session, soup = get_soup(url, win=win)
    list: Tag | None = soup.find("ul", class_="list-body")
    if list is None:
        raise Exception(tr_("목록 주소를 입력해주세요"))
    pages = get_pages(url, soup)
    return pages


#
# ---------------------- [ INFO GETTER ] ----------------------
#


def get_info(soup: Soup) -> Info:
    infobox: Tag = soup.find("div", class_="col-sm-8")
    contents: List[Tag] = infobox.find_all("div", class_="view-content")

    # (platform, tags, artist)
    details: List[str] = contents[1].get_text().split("\xa0")
    for n, detail in enumerate(details):
        details[n] = detail.strip()

    title = contents[0].get_text(strip=True)
    summary = contents[2].get_text(strip=True)

    return {
        "title": title,
        "platform": details[0],
        "tags": details[1],
        "artist": details[2],
        "summary": summary,
    }


def get_title(info: Info) -> str:
    return clean_title(info["title"])


def get_artist(info: Info) -> str:
    return clean_title(info["artist"])


def get_novel_content(soup: Soup) -> str:
    novel: Tag = soup.find("div", {"id": "novel_content"})
    ps: List[Tag] = novel.find_all("p")
    if len(ps) != 0:
        text = ""
        for p in ps:
            if p.get_text() != "":
                text += p.get_text()
            else:
                text += "\n"
            text += "\n"
    else:
        text = novel.get_text()
    return text


def get_novel_title(soup: Soup) -> str:
    full: Tag = soup.find("div", class_="toon-title")
    span = full.find("span")
    span.decompose()
    title = full.get_text(strip=True)
    return clean_title(title)


log(f"Site Added: Booktoki-All V4")
