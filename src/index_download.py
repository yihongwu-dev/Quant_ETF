from pathlib import Path
from time import sleep
from unittest.mock import patch

import akshare as ak
import pandas as pd
from akshare.utils.tqdm import get_tqdm

OUTPUT_DIR = Path(r"D:\Project\Quant-ETF\data\raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 指数名称、六位代码、腾讯接口使用的代码
indices = [
    ("沪深300","000300","sh000300"),
    ("上证50",   "000016", "sh000016"),
    ("中证500",  "000905", "sh000905"),
    ("中证1000", "000852", "sh000852"),
    ("创业板指", "399006", "sz399006"),
    ("科创50",   "000688", "sh000688"),
]

failed = []

# 临时关闭 AKShare 在该模块中使用的图形进度条。
with patch(
    "akshare.index.index_stock_zh.get_tqdm",
    return_value=get_tqdm(enable=False),
):
    for position, (name, code, symbol) in enumerate(indices):
        output_path = OUTPUT_DIR / f"{code}_index.csv"

        if output_path.exists():
            print(f"跳过：{name}，文件已存在：{output_path}")
            continue

        print(f"\n正在下载：{name}（{symbol}）")

        try:
            df_index = ak.index_zh_daily_tx(
                symbol=symbol)

            # 第一列加入指数代码，并统一日期格式。
            df_index.insert(0, "index_code", code)
            df_index.insert(0,"index_name",name)
            df_index["date"] = pd.to_datetime(df_index["date"])
            df_index = (
                df_index.sort_values("date")
                .reset_index(drop=True)
            )
            df_index["date"] = (
                df_index["date"].dt.strftime("%Y-%m-%d")
            )

            # 创建新文件；不覆盖已有文件。
            df_index.to_csv(
                output_path,
                index=False,
                encoding="utf-8-sig",
                mode="x",
            )

            print(f"已保存：{output_path}")
            print(f"行数：{len(df_index)}")

        except Exception as exc:
            failed.append((name, symbol))
            print(f"下载或保存失败：{type(exc).__name__}: {exc}")

        finally:
            if position < len(indices) - 1:
                sleep(2)

print("\n失败列表：", failed)