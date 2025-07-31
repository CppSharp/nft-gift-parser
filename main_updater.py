import asyncio
import logging
import os
import aiohttp

from database import create_pool, list_tables, insert_nft_batch
from main import get_current_quantity, parse_page, HEADERS, BATCH_SIZE

UPDATE_INTERVAL = 1

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def update_table(pool, table_name: str):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(f"SELECT COALESCE(MAX(number), 0) FROM `{table_name}`")
            (max_db,) = await cur.fetchone()
    logger.info(f"[{table_name}] Last number in DB: {max_db}")

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        total_site = await get_current_quantity(session)
    logger.info(f"[{table_name}] Current quantity on the website: {total_site}")

    # Если есть новые записи
    if total_site > max_db:
        missing = list(range(max_db + 1, total_site + 1))
        logger.info(f"[{table_name}] New numbers: {missing[0]}–{missing[-1]}")

        for i in range(0, len(missing), BATCH_SIZE):
            batch_nums = missing[i : i + BATCH_SIZE]
            logger.info(f"[{table_name}] Batch processing: {batch_nums[0]}–{batch_nums[-1]}")

            async with aiohttp.ClientSession(headers=HEADERS) as session:
                tasks = [parse_page(session, num) for num in batch_nums]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            valid = [res[1] for res in results if not isinstance(res, Exception) and res[1] is not None]
            if valid:
                await insert_nft_batch(pool, valid, table_name)
                logger.info(f"[{table_name}] Entries inserted: {len(valid)}")
                for record in valid:
                    link = f"t.me/nft/{table_name}-{record['number']}"
                    logger.info(f"[{table_name}] Link: {link}")
    else:
        logger.info(f"[{table_name}] The database is already up to date.")

async def main():
    pool = await create_pool()
    try:
        while True:
            # Получаем все таблицы в базе
            tables = await list_tables(pool)
            logger.info(f"Tables for updating: {tables}")

            # Обновляем каждую таблицу
            for tbl in tables:
                try:
                    await update_table(pool, tbl)
                except Exception as e:
                    logger.error(f"Table update error {tbl}: {e}")

            logger.info(f"All tables have been processed. Next through {UPDATE_INTERVAL} seconds.")
            await asyncio.sleep(UPDATE_INTERVAL)
    finally:
        pool.close()
        await pool.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())
