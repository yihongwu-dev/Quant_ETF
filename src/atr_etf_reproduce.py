"""广发金工 ATR ETF 网格演讲稿的可审计、简化复现（不联网）。

步骤：
    python atr_etf_reproduce.py check
    python atr_etf_reproduce.py indicators --n 20 --n1 20
    python atr_etf_reproduce.py index --n 20 --n1 20
    python atr_etf_reproduce.py portfolio --n 20 --n1 20

注意：N=20/N1=20是演示假设，非研报确认的参数。
由于行情CSV并非完整复权序列，ETF总收益依赖 data/raw/dividends/*.csv 和份额折算信息。
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INDEX_TO_ETF = {
    "000016": "510050",
    "000300": "510300",
    "000905": "510500",
    "000852": "512100",
    "399006": "159915",
    "000688": "588000",
}
INDEX_NAMES = {"000016":"上证50", "000300":"沪深300", "000905":"中证500",
               "000852":"中证1000", "399006":"创业板指", "000688":"科创50"}
BASE = Path(__file__).resolve().parent
INDEX_DIR = BASE / "data/raw/index"
ETF_DIR = BASE / "data/raw/etf"
DIV_DIR = BASE / "data/raw/dividends"
OUT = BASE / "outputs"
END = pd.Timestamp("2025-09-30")
START_2019 = pd.Timestamp("2019-01-02")  # 2018-12-31为休市日，2019-01-02首交易日
START_2022 = pd.Timestamp("2022-01-04")


def normalize_csv(path: Path, with_code: bool=False) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"index_code":str,"etf_code":str})
    df = df.rename(columns={"日期":"date", "开盘":"open", "最高":"high", "最低":"low",
                            "收盘":"close", "成交量":"volume", "成交额":"amount"})
    expected = {"date","open","high","low","close"}
    if missing := sorted(expected - set(df.columns)):
        raise ValueError(f"{path.name} 缺少字段 {missing}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ["open","high","low","close","volume","amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df["date"].notna() & df["date"].le(END)].copy().sort_values("date")
    if df.empty: raise ValueError(f"{path.name} 无截至{END.date()}可用数据")
    if df["date"].duplicated().any(): raise ValueError(f"{path.name} 日期重复，先检查原始文件")
    if df[["open","high","low","close"]].isna().any().any():
        raise ValueError(f"{path.name} 存在缺失OHLC")
    p = df[["open","high","low","close"]]
    invalid = (p.le(0).any(axis=1) | df["high"].lt(p[["open","low","close"]].max(axis=1))
               | df["low"].gt(p[["open","high","close"]].min(axis=1)))
    if invalid.any(): raise ValueError(f"{path.name} OHLC有{invalid.sum()}行不合理")
    return df.set_index("date").sort_index()


def discover(directory: Path, expected: set[str]) -> dict[str, Path]:
    found = {}
    for f in sorted(directory.glob("*.csv")):
        match = re.search(r"(?<!\d)(\d{6})(?!\d)",f.stem)
        if not match or match.group(1) not in expected: continue
        code = match.group(1)
        if code in found: raise ValueError(f"重复证券文件：{code} -> {found[code]} 与 {f}")
        found[code] = f
    return found


def load_index() -> dict[str,pd.DataFrame]:
    files = discover(INDEX_DIR,set(INDEX_TO_ETF))
    return {code: normalize_csv(path) for code,path in files.items()}


def load_etfs() -> dict[str,pd.DataFrame]:
    files = discover(ETF_DIR,set(INDEX_TO_ETF.values()))
    return {code: normalize_csv(path) for code,path in files.items()}


def make_indicators(df:pd.DataFrame, n:int, n1:int)->pd.DataFrame:
    df = df.copy()
    prev = df["close"].shift(1)
    true_range = pd.concat([(df["high"]-df["low"]),
                            (df["high"]-prev).abs(),
                            (df["low"]-prev).abs()],axis=1).max(axis=1)
    # 第一日无昨收，TR退化为最高-最低；ATR使用N个完整TR观察值
    df["tr"] = true_range
    df["atr"] = true_range.rolling(n,min_periods=n).mean()
    df["ma_n"] = df["close"].rolling(n,min_periods=n).mean()
    df["natr"] = (df["close"]-df["ma_n"])/df["atr"].replace(0,np.nan)
    df["matr"] = df["atr"].rolling(n1,min_periods=n1).mean()
    df["ma_n1"] = df["close"].rolling(n1,min_periods=n1).mean()
    df["timing"] = np.select([
        df["matr"].lt(df["matr"].shift(1)) & df["ma_n1"].gt(df["ma_n1"].shift(1)),
        df["matr"].lt(df["matr"].shift(1)) & df["ma_n1"].lt(df["ma_n1"].shift(1))],
        [1,-1],default=0).astype(int)
    valid = df["natr"].notna()
    x = df["natr"].to_numpy(dtype=float)
    regime = df["timing"].to_numpy()

    def weight_at(distance_up, distance_down, center):
        # 研报表1：(-1,1)中枢；每跨越1个NATR阈值仓位变化10%，上下限截断
        px = np.clip(np.floor(np.maximum(x,0)/distance_up),0,5)
        nx = np.clip(np.floor(np.maximum(-x,0)/distance_down),0,5)
        return np.clip(center - 0.1*px + 0.1*nx,0,1)

    base = weight_at(1,1,0.5)
    df["w_base"] = base
    # 研报表2策略1：看多时上方间距2倍、下方0.5倍；看空反之。
    up = np.where(regime==1,2.0,np.where(regime==-1,0.5,1.0))
    down = np.where(regime==1,0.5,np.where(regime==-1,2.0,1.0))
    df["w_t1"] = weight_at(up,down,0.5)
    # 策略2：看多中枢60%，看空中枢40%；其他时刻中枢50%。
    center = np.where(regime==1,0.6,np.where(regime==-1,0.4,0.5))
    df["w_t2"] = weight_at(1,1,center)
    # 策略3：看多时最低仓位50%；看空时最高仓位50%。
    df["w_t3"] = np.where(regime==1,np.maximum(base,0.5),
                         np.where(regime==-1,np.minimum(base,0.5),base))
    # 策略4：看多时仓位不低于上期，看空时仓位不高于上期（路径依赖）。
    t4 = np.full(len(df),np.nan)
    prev_weight = None
    for i,(wt,s) in enumerate(zip(base,regime)):
        if not np.isfinite(wt): continue
        if prev_weight is None: result = wt
        elif s==1: result = max(wt,prev_weight)
        elif s==-1: result = min(wt,prev_weight)
        else: result = wt
        t4[i] = result
        prev_weight = result
    df["w_t4"] = t4
    for col in ["w_base","w_t1","w_t2","w_t3"]:
        df.loc[~valid,col] = np.nan
    return df


def metrics(daily_ret:pd.Series)->dict:
    rr = daily_ret.dropna().astype(float)
    if len(rr)<2: return {"n_days":len(rr),"annual_return":np.nan,"max_drawdown":np.nan,"annual_vol":np.nan,"sharpe_rf0":np.nan}
    nav = (1+rr).cumprod()
    vol=rr.std(ddof=1)*np.sqrt(252)
    return {"n_days":len(rr),"annual_return":float(nav.iloc[-1]**(252/len(rr))-1),
            "max_drawdown":float((nav/nav.cummax()-1).min()),
            "annual_vol":float(vol), "sharpe_rf0":float(rr.mean()*252/vol) if vol>0 else np.nan}


def plot_series(x:pd.Index, cols:dict[str,pd.Series],filename:Path,title:str):
    filename.parent.mkdir(parents=True,exist_ok=True)
    plt.figure(figsize=(11,4.5))
    for label,values in cols.items(): plt.plot(x, values, label=label)
    plt.title(title);plt.legend();plt.grid(alpha=0.25);plt.tight_layout()
    plt.savefig(filename,dpi=140);plt.close()


def batch_indicators(n,n1,save=True):
    if n<2 or n1<2: raise ValueError("N和N1至少为2")
    ind=load_index()
    if not ind: raise FileNotFoundError(f"没有指数文件，请放入 {INDEX_DIR}")
    result={c:make_indicators(df,n,n1) for c,df in ind.items()}
    if save:
        (OUT/"features").mkdir(parents=True,exist_ok=True)
        for code,d in result.items():
            d.to_csv(OUT/"features"/f"{code}_n{n}_n1{n1}.csv",encoding="utf-8-sig",date_format="%Y-%m-%d")
            plot_series(d.index,{"ATR":d.atr},OUT/"figures"/f"{code}_atr.png",f"{code} ATR (N={n})")
            plot_series(d.index,{"NATR":d.natr},OUT/"figures"/f"{code}_natr.png",f"{code} NATR (N={n})")
            plot_series(d.index,{"base grid":d.w_base},OUT/"figures"/f"{code}_weight.png",f"{code} target weight")
            print(f"[指标] {code} {INDEX_NAMES[code]}: {len(d)}日, 首个NATR={d.natr.first_valid_index()}")
    return result


def index_test(n,n1,fee_bps):
    indicators=batch_indicators(n,n1,save=True)
    strat_cols=["w_base","w_t1","w_t2","w_t3","w_t4"]
    summary=[]
    for code,d in indicators.items():
        r=d.close.pct_change()
        for start in [START_2019,START_2022]:
            if d.index.max()<start: continue
            results={}
            for s in strat_cols:
                # t收盘生成信号，t+1收盘完成调仓，t+2才获得仓位对应的日收益
                pos=d[s].shift(2)
                gross=pos*r
                # 每次日频换仓，按每次交易权重的绝对变动计费用
                fee=pos.diff().abs().fillna(pos.abs())*fee_bps/10000.0
                ret=(gross-fee).loc[lambda x:x.index>=start].dropna()
                if len(ret)<2:continue
                results[s]=ret
                summary.append({"index":code,"requested_start":str(start.date()),
                                "actual_start":str(ret.index.min().date()),"strategy":s,
                                "n":n,"n1":n1,"fee_bps":fee_bps,**metrics(ret)})
            if results:
                earliest=max(series.index.min() for series in results.values())
                x=d.loc[earliest:].index
                navs={name:(1+ret.reindex(x).fillna(0)).cumprod() for name,ret in results.items()}
                navs["buy_hold_index"]=(1+r.reindex(x).fillna(0)).cumprod()
                plot_series(x,navs,OUT/"figures"/f"{code}_index_{start.year}.png",
                            f"{code} index backtest effective {earliest.date()} / weights lagged 2 days")
                for name,ret in results.items():
                    plot_series(ret.index,{"position":d[name].shift(2).reindex(ret.index)},
                                OUT/"figures"/f"{code}_{name}_{start.year}_pos.png",f"{code} {name} position")
    OUT.mkdir(exist_ok=True)
    if summary:
        pd.DataFrame(summary).to_csv(OUT/"index_metrics.csv",index=False,encoding="utf-8-sig")
        print("[完成] 指数回测指标:", OUT/"index_metrics.csv")
    else: print("[提醒] 暂无满足日期与预热要求的指数回测")


def read_dividend(code:str)->pd.Series:
    path=DIV_DIR/f"{code}_dividend.csv"
    if not path.exists():
        print(f"[警告] 没有 {path.name}；暂时不计该ETF现金分红，不能解释为真实总收益")
        return pd.Series(dtype=float)
    d=pd.read_csv(path,encoding="utf-8-sig")
    d=d.rename(columns={"日期":"date","累计分红":"cum_dividend"})
    if not {"date","cum_dividend"}.issubset(d.columns):
        raise ValueError(f"{path.name}: 必须包含 '日期','累计分红' 或 date,cum_dividend")
    d["date"]=pd.to_datetime(d["date"],errors="raise")
    d["cum_dividend"]=pd.to_numeric(d["cum_dividend"],errors="raise")
    d=d.sort_values("date")
    if d.date.duplicated().any():raise ValueError(f"{path.name} 存在重复除息日")
    event=d["cum_dividend"].diff().fillna(d["cum_dividend"])
    if event.lt(-1e-8).any():
        raise ValueError(f"{path.name} 累计分红出现负增量，可能有份额折算/口径变化，请核对公告")
    return pd.Series(event.values,index=d.date,name="dividend_per_share")


def etf_returns(etfs:dict[str,pd.DataFrame])->pd.DataFrame:
    # 仅当获得足额的分红和折算信息，才可以把下面输出视为总收益。
    output=[]
    for code,df in etfs.items():
        raw=df.close.astype(float)
        events=read_dividend(code)
        # 若缺失事件明细，认为0仅用于“价格收益/不完整总收益”的近似回测。
        div=events.reindex(raw.index,fill_value=0.0).astype(float)
        missed=events.index.difference(raw.index)
        if len(missed)>0:
            # 上市前少量分红日期可能与行情起点不一致；回测期内的不匹配必须人工排查
            bad=missed[missed>=pd.Timestamp("2018-12-31")]
            if len(bad):raise ValueError(f"{code} 有分红除息日不在价格交易日中: {bad.tolist()}")
        share_ratio=pd.Series(1.0,index=raw.index)
        if code=="512100":
            # 2022-09-02停牌合并，2022-09-05恢复交易（每1旧份额转成0.36555新份额）。
            date=pd.Timestamp("2022-09-05")
            if date in share_ratio.index: share_ratio.at[date]=0.36555
            else:raise ValueError("512100应包含2022-09-05行情，才能正确处理份额合并")
        # 折算当日新份额数/旧份额数；在恢复交易日将其作用到新份额价格。
        adjusted=(raw+div)*share_ratio/raw.shift(1)-1
        suspicious=adjusted[(adjusted.index>=START_2019)&(adjusted.abs()>0.4)]
        if len(suspicious):raise ValueError(f"{code} 存在单日大于40%的异常收益，检查分红、折算: {suspicious.to_dict()}")
        output.append(adjusted.rename(code))
    return pd.concat(output,axis=1).sort_index()


def portfolio_test(n,n1,fee_bps):
    indicators=batch_indicators(n,n1,save=False)
    etfs=load_etfs()
    missing_index=sorted(set(INDEX_TO_ETF)-set(indicators))
    missing_etf=sorted(set(INDEX_TO_ETF.values())-set(etfs))
    if missing_index or missing_etf:
        raise FileNotFoundError(f"缺少指数CSV: {missing_index}；缺少ETF CSV: {missing_etf}；当前仅支持6对完整文件组合")
    returns=etf_returns(etfs)
    dates=sorted(set().union(*(d.index for d in indicators.values()), returns.index))
    dates=pd.DatetimeIndex([v for v in dates if v<=END])
    # 实际交易日以ETF行情的联合日期为准；同日并非可交易则只能持有不新增交易。
    sample=pd.DataFrame(index=dates)
    for code,etf_code in INDEX_TO_ETF.items():
        sample[etf_code]=indicators[code]["w_t2"].reindex(dates)
    # 固定6只ETF的实验：仅当信号和ETF有行情（上市）才计入样本；不做20亿元规模筛选。
    available=pd.DataFrame(index=dates)
    for etf_code,df in etfs.items(): available[etf_code]=dates.isin(df.index)
    eligible=available & sample.notna()
    active=eligible.sum(axis=1)
    # 每只ETF的配置上限为1/N，其中N为当天能交易且有信号的固定样本个数；仅是演示。
    targets=sample.where(eligible,0).div(active.replace(0,np.nan),axis=0).fillna(0)
    if targets.sum(axis=1).gt(1+1e-9).any():raise AssertionError("ETF总权重超过100%")
    # 信号在t日收盘形成，t+1收盘执行，t+2对下一日日收益生效。
    held=targets.shift(2).fillna(0)
    r=returns.reindex(dates).reindex(columns=list(INDEX_TO_ETF.values()))
    invalid=(held.gt(0)&r.isna()).loc[lambda x:x.index>=START_2019]
    if invalid.any().any():
        print("[警告] 存在持仓ETF当日无行情，暂按停牌当日收益0%，需审查可交易性")
    r=r.fillna(0)
    gross=(held*r).sum(axis=1)
    turnover=held.diff().abs().sum(axis=1) # 仅权益交易额；不含现金
    daily=(gross - turnover*fee_bps/10000).loc[lambda x:x.index>=START_2019]
    nav=(1+daily).cumprod()
    OUT.mkdir(exist_ok=True)
    table=pd.DataFrame({"portfolio_return":daily,"nav":nav,
                        "equity_weight":held.sum(axis=1).reindex(daily.index),
                        "cash_weight":1-held.sum(axis=1).reindex(daily.index),
                        "turnover":turnover.reindex(daily.index)})
    table.to_csv(OUT/"portfolio_daily.csv",encoding="utf-8-sig",date_format="%Y-%m-%d")
    held.loc[daily.index].to_csv(OUT/"portfolio_etf_weights.csv",encoding="utf-8-sig",date_format="%Y-%m-%d")
    r.loc[daily.index].to_csv(OUT/"etf_total_returns_provisional.csv",encoding="utf-8-sig",date_format="%Y-%m-%d")
    summary=metrics(daily)
    pd.DataFrame([{**summary,"n":n,"n1":n1,"fee_bps":fee_bps,
                   "method":"固定6ETF / 择时2 / 缺失分红视0 / 现金收益0 / 目标权重滞后2日"}]).to_csv(
        OUT/"portfolio_metrics.csv",index=False,encoding="utf-8-sig")
    yearly=(1+daily).groupby(daily.index.year).prod()-1
    yearly.rename("annual_return").to_csv(OUT/"portfolio_annual_returns.csv",encoding="utf-8-sig")
    plot_series(nav.index,{"portfolio":nav},OUT/"figures"/"portfolio_nav.png","Six fixed ETF approximation")
    plot_series(table.index,{"equity allocation":table.equity_weight},
                OUT/"figures"/"portfolio_weight.png","Six fixed ETF equity weight")
    print("[组合完成，非原研报完整复现]",summary)
    print("结果目录:",OUT)


def check():
    idx=load_index();etfs=load_etfs()
    for label,content,expected in [("INDEX",idx,set(INDEX_TO_ETF)),("ETF",etfs,set(INDEX_TO_ETF.values()))]:
        for code,df in sorted(content.items()):
            print(f"[{label}] {code}, {len(df)}日, {df.index.min().date()} -> {df.index.max().date()}, cols={','.join(df.columns)}")
        for code in sorted(expected-set(content)): print(f"[{label} MISSING] {code}")
    print("\n分红文件:")
    for c in sorted(set(INDEX_TO_ETF.values())):
        p=DIV_DIR/f"{c}_dividend.csv"
        print(c, "已有" if p.exists() else "尚未提供（该ETF回测视为暂未计分红）")


def main():
    ap=argparse.ArgumentParser(description="广发ATR ETF网格策略教学复现；不联网，不自动下载")
    ap.add_argument("step",choices=["check","indicators","index","portfolio"])
    ap.add_argument("--n",type=int,default=20,help="演示ATR回看N，默认20非研报确认")
    ap.add_argument("--n1",type=int,default=20,help="演示择时均线N1，默认20非研报确认")
    ap.add_argument("--fee-bps",type=float,default=0,help="单边交易成本基点，默认0")
    args=ap.parse_args()
    if args.step=="check":check()
    elif args.step=="indicators":batch_indicators(args.n,args.n1)
    elif args.step=="index":index_test(args.n,args.n1,args.fee_bps)
    else:portfolio_test(args.n,args.n1,args.fee_bps)

if __name__=="__main__":main()
