import requests
from bs4 import BeautifulSoup
from rlottie_python import LottieAnimation
from PIL import Image
import io
import gzip
import aiohttp
from lxml.html import fromstring
import asyncio

def get_first_frame_from_tgs_page(page_url: str, scale: float = 1.0) -> Image.Image:
    resp = requests.get(page_url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    tag = soup.find("source", {"type": "application/x-tgsticker"})
    if not tag or not tag.has_attr("srcset"):
        raise RuntimeError
    tgs_url = tag["srcset"]
    tgs_data = requests.get(tgs_url, timeout=10).content
    anim = LottieAnimation.from_tgs(io.BytesIO(tgs_data))
    w, h = anim.lottie_animation_get_size()
    buf = anim.lottie_animation_render(frame_num=0)
    return Image.frombuffer("RGBA", (int(w * scale), int(h * scale)), buf, "raw", "BGRA")

def download_tgs_file(page_url: str, save_path: str) -> None:
    resp = requests.get(page_url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    tag = soup.find("source", {"type": "application/x-tgsticker"})
    if not tag or not tag.has_attr("srcset"):
        raise RuntimeError
    tgs_url = tag["srcset"]
    tgs_data = requests.get(tgs_url, timeout=10).content
    with open(save_path, "wb") as f:
        f.write(tgs_data)
        
def download_and_save_tgs_as_json(page_url: str, json_filename: str) -> None:
    resp = requests.get(page_url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    tag = soup.find("source", {"type": "application/x-tgsticker"})
    if not tag or not tag.has_attr("srcset"):
        raise RuntimeError
    tgs_url = tag["srcset"]
    tgs_data = requests.get(tgs_url, timeout=10).content
    with gzip.GzipFile(fileobj=io.BytesIO(tgs_data)) as gz:
        json_bytes = gz.read()
    with open(json_filename, "wb") as f:
        f.write(json_bytes)

def download_transparent_png_from_svg(page_url: str, save_path: str) -> None:
    resp = requests.get(page_url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    tag = soup.find("image", {"id": "giftPattern"})
    if not tag or not tag.has_attr("xlink:href"):
        return
    png_url = tag["xlink:href"]
    png_data = requests.get(png_url, timeout=10).content
    with open(save_path, "wb") as f:
        f.write(png_data)

async def get_current_quantity(session):
    async with throttler, session.get(BASE_URL + "1") as resp:
        resp.raise_for_status()
        text = await resp.text()
    tree = html.fromstring(text)
    qty = tree.xpath(
        '//table[contains(@class,"tgme_gift_table")]'
        '//tr[th[contains(translate(., "Q","q"), "quantity")]]/td/text()'
    )
    if not qty:
        logger.error("Quantity field not found")
        raise RuntimeError("Quantity field not found")
    return int(qty[0].split('/')[0].replace('\u00A0', '').replace(',', ''))
