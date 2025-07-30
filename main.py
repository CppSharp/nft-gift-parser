import asyncio
import aiohttp
import aiomysql
import aiofiles
import json
import random
import string
import time
import logging
import ssl
import certifi
import csv
from pathlib import Path
from bs4 import BeautifulSoup
from lxml import html
from asyncio_throttle import Throttler
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from nft_utils import (
    get_first_frame_from_tgs_page,
    download_and_save_tgs_as_json,
    download_transparent_png_from_svg,
    download_tgs_file,
    get_quantity
)
from database import create_pool, create_table, insert_nft_batch, update
from dotenv import load_dotenv
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

NFT_NAME = os.getenv("NFT_NAME")
BASE_URL = os.getenv("BASE_URL").format(NFT_NAME_LOWER=NFT_NAME.lower())
TABLE_NAME = os.getenv("TABLE_NAME").format(NFT_NAME_LOWER=NFT_NAME.lower())
STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT"))
MODELS_ROOT = STORAGE_ROOT / "models" / NFT_NAME
IMG_DIR = MODELS_ROOT / "img"
ANIM_DIR = MODELS_ROOT / "anim"
TGS_DIR = MODELS_ROOT / "tgs"
SYMBOLS_PATH = STORAGE_ROOT / "patterns" / "symbols.json"
PATTERNS_DIR = STORAGE_ROOT / "patterns"
CSV_PATH = STORAGE_ROOT / f"{TABLE_NAME}_data.csv"
HEADERS = {"User-Agent": os.getenv("HEADERS").split(": ")[1]}
throttler = Throttler(rate_limit=int(os.getenv("RATE_LIMIT")), period=int(os.getenv("PERIOD")))
BATCH_SIZE = int(os.getenv("BATCH_SIZE"))

def prepare_dirs_and_index():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    ANIM_DIR.mkdir(parents=True, exist_ok=True)
    TGS_DIR.mkdir(parents=True, exist_ok=True)
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)

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

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, ConnectionResetError))
)
async def parse_page(session, idx):
    url = BASE_URL + str(idx)
    try:
        async with throttler, session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning(f"[{idx}] Status {resp.status} for {url}")
                return idx, None
            text = await resp.text()
    except Exception as e:
        logger.error(f"[{idx}] Request error for {url}: {e}")
        raise
    tree = html.fromstring(text)
    d = {
        "name": NFT_NAME.lower(),
        "number": idx,
        "m": "Unknown",
        "bd": "Unknown",
        "s": "Unknown",
        "mchance": 0,
        "bdchance": 0,
        "schance": 0,
        "hex1": "None",
        "hex2": "None",
        "s_in_dir": None
    }

    for key, db_key in [("model", "m"), ("backdrop", "bd"), ("symbol", "s")]:
        tr = tree.xpath(
            f'//table[contains(@class,"tgme_gift_table")]'
            f'//tr[th[contains(translate(., "{key.upper()}","{key.lower()}"), "{key}")]]'
        )
        if tr:
            td = tr[0].find("td")
            mark = td.find("mark")
            chance = mark.text_content().replace("%", "").strip() if mark is not None else "0"
            full = td.text_content().strip()
            name = full.replace(mark.text_content(), "").strip() if mark is not None else full
            try:
                chance_value = float(chance) * 100 if chance else 0
                d[db_key], d[f"{db_key}chance"] = name, int(chance_value)
            except ValueError:
                logger.warning(f"[{idx}] Invalid chance format for {key}: {chance}")
                d[db_key], d[f"{db_key}chance"] = name, 0
        else:
            d[db_key], d[f"{db_key}chance"] = "Unknown", 0

    stops = tree.xpath('//radialgradient[@id="giftGradient"]//stop/@stop-color')
    d["hex1"], d["hex2"] = (stops + ["None", "None"])[:2]

    logger.info(f"Parsed NFT ID: {idx}, Model: {d['m']} ({d['mchance']/100:.1f}%), Backdrop: {d['bd']} ({d['bdchance']/100:.1f}%), Symbol: {d['s']} ({d['schance']/100:.1f}%), Gradient: {d['hex1']}, {d['hex2']}")

    return idx, d

async def save_all_to_db(pool):
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        total = await get_current_quantity(session)
        logger.info(f"Total models: {total}. Saving to `{TABLE_NAME}` and `{CSV_PATH}`")

        fieldnames = ['name', 'number', 'm', 'bd', 's', 'mchance', 'bdchance', 'schance', 'hex1', 'hex2', 's_in_dir']
        try:
            async with aiofiles.open(CSV_PATH, mode='w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                await writer.writeheader()
        except Exception as e:
            logger.error(f"CSV creation error `{CSV_PATH}`: {e}")
            raise

        for start in range(1, total + 1, BATCH_SIZE):
            end = min(start + BATCH_SIZE, total + 1)
            logger.info(f"Processing batch {start}–{end - 1}")
            batch_start_time = time.time()

            tasks = [parse_page(session, idx) for idx in range(start, end)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            valid = [r[1] for r in results if not isinstance(r, Exception) and r[1] is not None]
            if valid:
                try:
                    await insert_nft_batch(pool, valid, TABLE_NAME)
                except Exception as e:
                    logger.error(f"Batch {start}–{end - 1} DB write error: {e}")

                try:
                    async with aiofiles.open(CSV_PATH, mode='a', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        await writer.writerows(valid)
                except Exception as e:
                    logger.error(f"Batch {start}–{end - 1} CSV write error: {e}")

            batch_time = time.time() - batch_start_time
            logger.info(f"Batch {start}–{end - 1} done in {batch_time:.2f}s")
            await asyncio.sleep(0.1)

        logger.info(f"Data saved to `{TABLE_NAME}` and `{CSV_PATH}`")

async def read_unique_models(pool):
    unique = {}
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    f"SELECT number, m FROM `{TABLE_NAME}` WHERE name = %s",
                    (NFT_NAME.lower(),)
                )
                rows = await cur.fetchall()
                for number, model_name in rows:
                    if model_name not in unique:
                        unique[model_name] = number
            except Exception as e:
                logger.error(f"Error reading models from `{TABLE_NAME}`: {e}")
                raise
    return unique

async def download_model(name, idx, session):
    url = BASE_URL + str(idx)
    try:
        img = await asyncio.to_thread(get_first_frame_from_tgs_page, url)
        img.save(IMG_DIR / f"{name}.png")
        logger.info(f"Model {name}.png saved")
    except Exception as e:
        logger.error(f"Model preview error for {name}: {e}")

    try:
        await asyncio.to_thread(download_and_save_tgs_as_json, url, ANIM_DIR / f"{name}.json")
        logger.info(f"Model {name}.json saved")
    except Exception as e:
        logger.error(f"Model JSON animation error for {name}: {e}")

    try:
        await asyncio.to_thread(download_tgs_file, url, TGS_DIR / f"{name}.tgs")
        logger.info(f"Model {name}.tgs saved")
    except Exception as e:
        logger.error(f"Model TGS error for {name}: {e}")

async def download_models(pool):
    unique = await read_unique_models(pool)
    logger.info(f"Downloading {len(unique)} models")
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [download_model(name, idx, session) for name, idx in unique.items()]
        await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Models downloaded")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, ConnectionResetError))
)
async def download_transparent_png_from_svg_async(session, page_url: str, save_path: Path) -> None:
    try:
        async with session.get(page_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            text = await resp.text()
        soup = BeautifulSoup(text, "html.parser")
        tag = soup.find("image", {"id": "giftPattern"})
        if not tag or not tag.has_attr("xlink:href"):
            logger.warning(f"No <image id='giftPattern'> on {page_url}")
            return
        png_url = tag["xlink:href"]
        async with session.get(png_url, timeout=aiohttp.ClientTimeout(total=30)) as png_resp:
            png_data = await png_resp.read()
        async with aiofiles.open(save_path, "wb") as f:
            await f.write(png_data)
        logger.info(f"PNG saved: {save_path}")
    except aiohttp.ClientError as e:
        logger.error(f"Network error downloading {page_url}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error downloading PNG from {page_url}: {e}")
        raise

async def process_symbols(pool):
    try:
        with open(SYMBOLS_PATH, "r", encoding="utf-8") as f:
            symbols_data = json.load(f)
    except FileNotFoundError:
        logger.warning(f"{SYMBOLS_PATH} not found. Creating empty.")
        symbols_data = {}
    symbol_keys = list(symbols_data.keys())
    logger.info(f"Read {len(symbol_keys)} keys from symbols.json")

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    f"SELECT id, number, s FROM `{TABLE_NAME}` WHERE name = %s",
                    (NFT_NAME.lower(),)
                )
                records = await cur.fetchall()
            except Exception as e:
                logger.error(f"Error reading records from `{TABLE_NAME}`: {e}")
                return

    processed_records = [{"id": r[0], "number": r[1], "s": r[2]} for r in records]
    missing_s_in_dir = []

    for record in processed_records:
        symbol = record["s"]
        if symbol in symbol_keys:
            filename = Path(symbols_data[symbol]).name[:-4]
            record["s_in_dir"] = filename
        else:
            missing_s_in_dir.append((record["id"], record["number"], symbol))

    logger.info(f"Processed {len(processed_records)} records, missing s_in_dir: {len(missing_s_in_dir)}")

    unique_symbols = {}
    for id_, number, symbol in missing_s_in_dir:
        if symbol not in unique_symbols:
            unique_symbols[symbol] = (id_, number)

    pattern_dirs = [d for d in PATTERNS_DIR.iterdir() if d.is_dir() and len(d.name) == 2]
    if not pattern_dirs:
        logger.warning(f"No dirs in {PATTERNS_DIR}. Creating 'ab'.")
        (PATTERNS_DIR / "ab").mkdir(exist_ok=True)
        pattern_dirs = [PATTERNS_DIR / "ab"]
    file_counts = {d: len(list(d.iterdir())) for d in pattern_dirs}

    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(headers=HEADERS, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        for symbol, (id_, number) in unique_symbols.items():
            url = BASE_URL + str(number)
            min_dir = min(file_counts, key=file_counts.get)
            xx = min_dir.name[:2]
            yyyy = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
            filename = f"{xx}{yyyy}.png"
            save_path = min_dir / filename
            try:
                await download_transparent_png_from_svg_async(session, url, save_path)
                symbols_data[symbol] = str(save_path)
                file_counts[min_dir] += 1
                async with pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        try:
                            await cur.execute(
                                f"UPDATE `{TABLE_NAME}` SET s_in_dir = %s WHERE s = %s AND name = %s",
                                (filename[:-4], symbol, NFT_NAME.lower())
                            )
                            await conn.commit()
                            logger.info(f"Updated s_in_dir for symbol '{symbol}' in all matching records")
                        except Exception as e:
                            logger.error(f"Error updating s_in_dir for symbol '{symbol}': {e}")
            except Exception as e:
                logger.error(f"Error processing symbol '{symbol}' (ID: {id_}, number: {number}): {e}")
                continue

    with open(SYMBOLS_PATH, "w", encoding="utf-8") as f:
        json.dump(symbols_data, f, ensure_ascii=False, indent=4)
    logger.info("Updated symbols.json saved")

async def main():
    start = time.time()
    prepare_dirs_and_index()
    pool = await create_pool()
    try:
        await create_table(pool, TABLE_NAME)
        await save_all_to_db(pool)
        await download_models(pool)
        await process_symbols(pool)
    finally:
        pool.close()
        await pool.wait_closed()
    logger.info(f"Execution completed in {time.time() - start:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())