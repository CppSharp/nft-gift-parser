# database.py
import aiomysql
import os
from dotenv import load_dotenv
from typing import Any, List

load_dotenv()

db_config = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "db": os.getenv("DB_NAME", "nfts"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "charset": "utf8mb4",
    "autocommit": False,
}

required_keys = ["user", "password"]
for key in required_keys:
    if not db_config.get(key):
        raise ValueError(f"Missing DB config: {key}")

async def create_pool() -> aiomysql.Pool:
    pool = await aiomysql.create_pool(**db_config)
    return pool

async def list_tables(pool: aiomysql.Pool) -> List[str]:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SHOW TABLES")
            rows = await cur.fetchall()
    return [row[0] for row in rows]

async def create_table(pool: aiomysql.Pool, table_name: str):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{table_name}` (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    name TEXT NOT NULL,
                    number INTEGER NOT NULL,
                    m TEXT NOT NULL,
                    bd TEXT NOT NULL,
                    s TEXT NOT NULL,
                    mchance INTEGER NOT NULL,
                    bdchance INTEGER NOT NULL,
                    schance INTEGER NOT NULL,
                    hex1 CHAR(7),
                    hex2 CHAR(7),
                    s_in_dir CHAR(6)
                )
                """
            )
            await conn.commit()

async def insert_nft_batch(pool: aiomysql.Pool, data_list: list, table_name: str):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            query = f"""
                INSERT INTO `{table_name}` (
                    name, number, m, bd, s,
                    mchance, bdchance, schance,
                    hex1, hex2, s_in_dir
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
            """
            await cur.executemany(
                query,
                [(
                    data["name"], data["number"], data["m"], data["bd"], data["s"],
                    data["mchance"], data["bdchance"], data["schance"],
                    data["hex1"], data["hex2"], data["s_in_dir"]
                ) for data in data_list]
            )
            await conn.commit()

async def update(pool: aiomysql.Pool, table_name: str, id: int, column: str, value: Any) -> None:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            query = f"UPDATE `{table_name}` SET `{column}` = %s WHERE id = %s"
            await cur.execute(query, (value, id))
            await conn.commit()
