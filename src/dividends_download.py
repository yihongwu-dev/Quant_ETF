"""从AKShare的新浪累计分红接口逐只下载ETF分红，已有文件一律跳过；限流/错误停止，不循环重试。"""
from pathlib import Path
import time
import akshare as ak
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEST = PROJECT_ROOT / "data" / "raw" / "dividends"
DEST.mkdir(parents=True,exist_ok=True)
SYMBOLS={"510050":"sh510050","510300":"sh510300","510500":"sh510500",
         "512100":"sh512100","159915":"sz159915","588000":"sh588000"}
for code,symbol in SYMBOLS.items():
    path=DEST/f"{code}_dividend.csv"
    if path.exists():
        print("跳过已有文件:",path.name)
        continue
    try:
        df=ak.fund_etf_dividend_sina(symbol=symbol)
        if df.empty:
            print(f"{code}: 接口返回空，请检查是否确无分红或者接口失败；不写空文件")
            continue
        if not {"日期","累计分红"}.issubset(df.columns):
            raise ValueError(f"列名异常: {df.columns.tolist()}")
        df["日期"]=pd.to_datetime(df["日期"],errors="raise")
        df=df.sort_values("日期")
        if df["日期"].duplicated().any():raise ValueError("同一除息日重复")
        df.to_csv(path,index=False,encoding="utf-8-sig",date_format="%Y-%m-%d")
        print(f"已存: {path}, 共{len(df)}次事件, 最近{df['日期'].max().date()}")
    except Exception as e:
        print("下载失败，停止（不自动重试）:",code,repr(e))
        break
    time.sleep(5)
