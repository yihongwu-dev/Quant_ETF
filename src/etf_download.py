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
    ("华泰柏瑞沪深300ETF",   "510300", "sh510300"),
    ("华夏上证50ETF",   "510050", "sh510050"),
    ("南方中证500ETF",  "510500", "sh510500"),
    ("南方中证1000ETF", "512100", "sh512100"),
    ("易方达创业板ETF", "159915", "sz159915"),
    ("华夏科创50ETF",   "588000", "sh588000"),
]
failed = []

# 临时关闭 AKShare 在该模块中使用的图形进度条。
with patch(
    "akshare.index.index_stock_zh.get_tqdm",
    return_value=get_tqdm(enable=False),
):
    for position, (name, code, symbol) in enumerate(indices):
        output_path = OUTPUT_DIR / f"{code}_etf.csv"

        if output_path.exists():
            print(f"跳过：{name}，文件已存在：{output_path}")
            continue

        print(f"\n正在下载：{name}（{symbol}）")

        try:
            df = ak.fund_etf_hist_sina(
                symbol=symbol)

            # 第一列加入指数代码，并统一日期格式。
            df.insert(0, "etf_name", name)
            df.insert(0, "etf_code", code)
            df["date"] = pd.to_datetime(df["date"])
            df = (
                df.sort_values("date")
                .reset_index(drop=True)
            )
            df["date"] = (
                df["date"].dt.strftime("%Y-%m-%d")
            )

            # 创建新文件；不覆盖已有文件。
            df.to_csv(
                output_path,
                index=False,
                encoding="utf-8-sig",
                mode="x",
            )

            print(f"已保存：{output_path}")
            print(f"行数：{len(df)}")

        except Exception as exc:
            failed.append((name, symbol))
            print(f"下载或保存失败：{type(exc).__name__}: {exc}")

        finally:
            if position < len(indices) - 1:
                sleep(2)

print("\n失败列表：", failed)