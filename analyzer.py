# analyzer.py
import pandas as pd
import numpy as np
from scipy.stats import spearmanr


# ============ 基礎分析 ============

def 整體概況(df, 品牌編號):
    d = df[df["品牌編號"] == 品牌編號]
    出賽 = len(d)
    if 出賽 == 0:
        return {}
    冠 = int((d["名次"] == 1).sum())
    亞 = int((d["名次"] == 2).sum())
    季 = int((d["名次"] == 3).sum())
    return {
        "出賽次數": 出賽, "冠": 冠, "亞": 亞, "季": 季,
        "勝率": round(冠 / 出賽, 3),
        "入位率": round((冠 + 亞 + 季) / 出賽, 3),
        "平均名次": round(d["名次"].mean(), 2),
        "最佳名次": int(d["名次"].min()),
    }


def 路程分析(df, 品牌編號):
    d = df[df["品牌編號"] == 品牌編號]
    if d.empty:
        return pd.DataFrame()
    result = d.groupby("路程")["名次"].agg(
        出賽="count",
        冠=lambda x: (x == 1).sum(),
        亞=lambda x: (x == 2).sum(),
        季=lambda x: (x == 3).sum(),
        平均名次="mean",
        最佳名次="min",
    ).round(2)
    result["入位率"] = ((result["冠"] + result["亞"] + result["季"]) / result["出賽"]).round(3)
    return result.sort_values("出賽", ascending=False)


def 場地分析(df, 品牌編號):
    d = df[df["品牌編號"] == 品牌編號].copy()
    if d.empty:
        return pd.DataFrame()
    d["場地賽道"] = d["場地"] + " " + d["賽道"].astype(str)
    result = d.groupby("場地賽道")["名次"].agg(
        出賽="count",
        冠=lambda x: (x == 1).sum(),
        亞=lambda x: (x == 2).sum(),
        季=lambda x: (x == 3).sum(),
        平均名次="mean",
        最佳名次="min",
    ).round(2)
    result["入位率"] = ((result["冠"] + result["亞"] + result["季"]) / result["出賽"]).round(3)
    return result.sort_values("出賽", ascending=False)


def 騎師分析(df, 品牌編號):
    d = df[df["品牌編號"] == 品牌編號]
    if d.empty:
        return pd.DataFrame()
    result = d.groupby("騎師")["名次"].agg(
        合作次數="count",
        冠=lambda x: (x == 1).sum(),
        亞=lambda x: (x == 2).sum(),
        季=lambda x: (x == 3).sum(),
        平均名次="mean",
        最佳名次="min",
    ).round(2)
    result["入位率"] = ((result["冠"] + result["亞"] + result["季"]) / result["合作次數"]).round(3)
    return result.sort_values("合作次數", ascending=False)


def 騎師路程分析(df, 品牌編號):
    d = df[df["品牌編號"] == 品牌編號]
    if d.empty:
        return pd.DataFrame()
    result = d.groupby(["騎師", "路程"])["名次"].agg(
        出賽="count",
        冠=lambda x: (x == 1).sum(),
        平均名次="mean",
    ).round(2)
    return result.sort_values(["騎師", "出賽"], ascending=[True, False])


# ============ 檔位分析 ============

def 檔位分析(df, 品牌編號=None):
    d = df.copy()
    if 品牌編號:
        d = d[d["品牌編號"] == 品牌編號]
    if d.empty:
        return pd.DataFrame()
    d["檔位區間"] = pd.cut(
        d["檔位"],
        bins=[0, 4, 8, 12, 14],
        labels=["內檔(1-4)", "中內(5-8)", "中外(9-12)", "外檔(13-14)"],
    )
    result = d.groupby("檔位區間", observed=True)["名次"].agg(
        出賽="count",
        冠=lambda x: (x == 1).sum(),
        亞=lambda x: (x == 2).sum(),
        季=lambda x: (x == 3).sum(),
        平均名次="mean",
        最佳名次="min",
    ).round(2)
    result["入位率"] = ((result["冠"] + result["亞"] + result["季"]) / result["出賽"]).round(3)
    return result


def 檔位優勢指數(df, 場地, 路程):
    d = df[(df["場地"] == 場地) & (df["路程"] == 路程)].copy()
    if d.empty:
        return pd.DataFrame()
    場次規模 = d.groupby("場次編號")["馬號"].transform("count")
    d["相對名次"] = d["名次"] / 場次規模
    result = d.groupby("檔位")["相對名次"].agg(
        出賽="count",
        平均相對名次="mean",
    ).round(3)
    result["檔位優勢指數"] = (1 - result["平均相對名次"]).round(3)
    return result.sort_values("檔位優勢指數", ascending=False)


# ============ 賠率分析 ============

def 賠率分析(df, 品牌編號=None):
    d = df.copy()
    if 品牌編號:
        d = d[d["品牌編號"] == 品牌編號]
    d = d.dropna(subset=["獨贏賠率"])
    if d.empty:
        return pd.DataFrame()
    d["賠率區間"] = pd.cut(
        d["獨贏賠率"],
        bins=[0, 3, 6, 10, 20, 50, 9999],
        labels=["大熱(≤3)", "熱門(3-6)", "中價(6-10)", "冷門(10-20)", "大冷(20-50)", "巨冷(>50)"],
    )
    result = d.groupby("賠率區間", observed=True)["名次"].agg(
        出賽="count",
        冠=lambda x: (x == 1).sum(),
        入位=lambda x: (x <= 3).sum(),
        平均名次="mean",
    ).round(2)
    result["勝率"] = (result["冠"] / result["出賽"]).round(3)
    result["入位率"] = (result["入位"] / result["出賽"]).round(3)
    return result


def 賠率相關性(df):
    d = df.dropna(subset=["獨贏賠率", "名次"])
    if len(d) < 10:
        return {}
    corr, p = spearmanr(d["獨贏賠率"], d["名次"])
    return {"Spearman相關係數": round(corr, 3), "p值": round(p, 4), "樣本數": len(d)}


def 個別馬匹賠率表現(df, 品牌編號):
    d = df[df["品牌編號"] == 品牌編號].copy()
    cols = ["比賽日期", "場地", "路程", "名次", "獨贏賠率", "騎師"]
    cols = [c for c in cols if c in d.columns]
    return d[cols].sort_values("比賽日期")


# ============ 走位分析 ============

def 拆解走位(df):
    d = df.copy()
    d = d[d["走位列表"].apply(lambda x: isinstance(x, list) and len(x) >= 2)].copy()
    if d.empty:
        return d
    d["起步位"] = d["走位列表"].apply(lambda x: x[0])
    d["最終走位"] = d["走位列表"].apply(lambda x: x[-1])
    d["衝刺前位"] = d["走位列表"].apply(lambda x: x[-2] if len(x) >= 2 else np.nan)
    d["走位變化"] = d["最終走位"] - d["衝刺前位"]
    d["衝刺提升"] = d["衝刺前位"] - d["最終走位"]
    return d


def 走位模式分析(df, 品牌編號=None):
    d = 拆解走位(df)
    if 品牌編號:
        d = d[d["品牌編號"] == 品牌編號]
    if d.empty:
        return pd.DataFrame()

    def 分類(row):
        起步 = row["起步位"]
        最終 = row["最終走位"]
        if 起步 <= 4 and 最終 <= 4:
            return "前領型"
        elif 起步 >= 10 and 最終 <= 4:
            return "後上型"
        elif 起步 <= 6 and 最終 >= 10:
            return "前段搶放後勁不繼"
        elif 起步 >= 8 and 最終 >= 8:
            return "全程後列"
        else:
            return "中段型"

    d["走位模式"] = d.apply(分類, axis=1)
    result = d.groupby("走位模式")["名次"].agg(
        出賽="count",
        冠=lambda x: (x == 1).sum(),
        入位=lambda x: (x <= 3).sum(),
        平均名次="mean",
    ).round(2)
    result["入位率"] = (result["入位"] / result["出賽"]).round(3)
    return result.sort_values("入位率", ascending=False)


def 走位提升分析(df, 品牌編號=None):
    d = 拆解走位(df)
    if 品牌編號:
        d = d[d["品牌編號"] == 品牌編號]
    if d.empty:
        return pd.DataFrame()
    d["提升區間"] = pd.cut(
        d["衝刺提升"],
        bins=[-15, -3, 0, 3, 6, 15],
        labels=["大幅後退(≤-4)", "輕微後退(-3~0)", "輕微前進(1~3)", "明顯前進(4~6)", "大幅前進(≥7)"],
    )
    result = d.groupby("提升區間", observed=True)["名次"].agg(
        出賽="count",
        冠=lambda x: (x == 1).sum(),
        入位=lambda x: (x <= 3).sum(),
        平均名次="mean",
    ).round(2)
    result["入位率"] = (result["入位"] / result["出賽"]).round(3)
    return result


def 走位明細(df, 品牌編號):
    d = 拆解走位(df)
    d = d[d["品牌編號"] == 品牌編號].copy()
    cols = ["比賽日期", "場地", "路程", "名次", "沿途走位",
            "起步位", "衝刺前位", "最終走位", "衝刺提升", "騎師"]
    cols = [c for c in cols if c in d.columns]
    return d[cols].sort_values("比賽日期")
