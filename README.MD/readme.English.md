# NFT Parser

## 💖 Support Me

If you find this parser helpful and want to support me (and Komugi 🐈‍⬛),  
please consider making a donation:

[Donate to Komugi](https://cppsharp.github.io/#donate)  

<img src="files/komugi_and_komaru.png" alt="Komugi and Komaru" width="150" style="margin-top:10px;"/>

Any support is greatly appreciated! Thank you! 🙏



## 📋 Table of Contents

1. [Brief Description](#brief-description)
2. [Key Features](#key-features)
3. [Installation & Launch](#installation--launch)
4. [Configuration](#configuration)
5. [Download Steps & Functions](#download-steps--functions)
6. [Parallel Runs](#parallel-runs)
7. [Directory Structure](#directory-structure)
8. [Troubleshooting](#troubleshooting)

---

## 🧾 Brief Description

NFT Gifts Parser is an asynchronous NFT data parser (via t.me/{slug}). The code automatically collects information about models, backgrounds, symbols, and their drop chances, saves results to a database, and downloads both visual and animation files into divinely structured folders.

---

## 📦 Key Features

* Asynchronous high-performance page loading with respect for rate limits
* Parsing NFT attributes: model, background, symbol, and drop chance
* Storing data in MySQL (via aiomysql)
* Automatic downloading of previews (PNG), animations (TGS), and JSON-based animations
* Symbol reference updates (`symbols.json`) and downloading missing PNGs
* Convenient and divinely structured organization of directories for models and patterns

---

## 🚀 Installation & Launch

### Prerequisites

* Python **3.8+**
* Git
* `venv` virtual environment for dependency isolation
* `.env` config file ([see Configuration](#configuration))

### Installation Steps

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/nft-parser.git
   cd nft-parser
   ```

2. **Create and activate a virtual environment**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   ```

3. **Install dependencies**

   ```bash
   py -m pip install --upgrade pip
   py -m pip install -r requirements.txt
   ```

4. **Create directory structure**

   ```bash
   py setup_dirs.py
   ```

### Running the Parser

* **Basic launch**:

  ```bash
  py main.py
  ```

---

## ⚙️ Configuration

All settings are stored in the `.env` file in the project root. Example:

```dotenv
DB_HOST=
DB_USER=
DB_PASSWORD=
DB_NAME=
DB_PORT=

NFT_NAME=
STORAGE_ROOT=./storage
BASE_URL=https://t.me/nft/{NFT_NAME_LOWER}-
TABLE_NAME={NFT_NAME_LOWER}

HEADERS=User-Agent: Mozilla/5.0
RATE_LIMIT=70
PERIOD=1
BATCH_SIZE=70
```

---

## 📥 Download Steps & Functions

1. **Determine total number of NFTs**

   * `get_current_quantity(session)`
2. **Parse data for each NFT**

   * `parse_page(session, idx)`
3. **Store data**

   * `insert_nft_batch(pool, data_list, table_name)`
   * `asyncio` + `aiofiles`
4. **Download visual resources**

   * `download_model(name, idx, session)`

     * `get_first_frame_from_tgs_page`
     * `download_and_save_tgs_as_json`
     * `download_tgs_file`
5. **Process symbols and download missing patterns**

   * `process_symbols(pool)` → `download_transparent_png_from_svg_async`

---

## 🏎️ Parallel Runs

Example: bandwidth — **600 MB** for uploads/downloads.

**Hardware configuration**: AMD Ryzen 7 5700X 8-Core, SSDPR-PX500-256-80-G2

Up to **10** instances running \~500 requests per second each.
10 million NFT gifts parsed in \~7 hours.

> **Tip**: Start with NFTs that have the highest supply to ensure complete collection before potential changes.

---
## 🗄️Data
## 📊 Database table structure

The table stores NFT data with detailed attributes.

| Field       | Type     | Description                                             |
|-------------|----------|---------------------------------------------------------|
| `id`        | INTEGER  | Unique identifier (PRIMARY KEY, AUTO_INCREMENT)         |
| `name`      | TEXT     | NFT name                                                |
| `number`    | INTEGER  | NFT number or index                                     |
| `m`         | TEXT     | Model                                                   |
| `bd`        | TEXT     | Background                                              |
| `s`         | TEXT     | Symbol                                                  |
| `mchance`   | INTEGER  | Model drop chance (%)                                   |
| `bdchance`  | INTEGER  | Background drop chance (%)                              |
| `schance`   | INTEGER  | Symbol drop chance (%)                                  |
| `hex1`      | CHAR(7)  | Color in HEX format (e.g., `#FFFFFF`)                   |
| `hex2`      | CHAR(7)  | Second color in HEX                                     |
| `s_in_dir`  | CHAR(6)  | Symbol code in directory                                |

## 📂 Directory Structure

```text
nft-parser/
├── main.py
├── database.py
├── nft_utils.py
├── setup_dirs.py
├── requirements.txt
├── .env
└── storage/
    ├── models/
    │   └── <NFT_NAME>/
    │       ├── img/
    │       ├── anim/
    │       └── tgs/
    └── patterns/
        ├── 00/
        ├── 01/
        └── ...
        └── ff/
```

---

## 🚧 Troubleshooting

Common issues:

- **429 Too Many Requests**  
  Increase `PERIOD` or decrease `RATE_LIMIT` in `.env`.

- **Insufficient write permissions**  
  Run the script with administrator rights.

- **Invalid parser response format**  
  Check if the website structure has changed.

- **Missing images or animations**  
  Check the connection and save paths.
