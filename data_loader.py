# data_loader.py
import pandas as pd
import re
import streamlit as st


@st.cache_data(show_spinner="正在載入賽馬資料...")
def load_data(filepath: str = "hkjc_results_25_26.xlsx") -> pd.DataFrame:
    """載入並清洗香港賽馬結果資料"""
    df = pd.read_excel(filepath, sheet_name="賽果")

    # 1. 拆分馬名與品牌編號
    extracted = df["馬名"].astype(str).str.extract(r"(.+?)\s*\((\w+)\)")
    df["馬名"] = extracted[0].str.strip()
    df["品牌編號"] = extracted[1].str.strip().str.upper()

    # 2. 標準化路程
    df["路程"] = df["路程"].astype(str).str.replace("米", "", regex=False)
    df["路程"] = pd.to_numeric(df["路程"], errors="coerce")

    # 3. 標準化場地
    df["場地"] = df["場地"].map({"ST": "沙田", "HV": "跑馬地"}).fillna(df["場地"])

    # 4. 數值欄位轉換
    df["名次"] = pd.to_numeric(df["名次"], errors="coerce")
    df["獨贏賠率"] = pd.to_numeric(df["獨贏賠率"], errors="coerce")
    df["檔位"] = pd.to_numeric(df["檔位"], errors="coerce")

    # 5. 日期轉 datetime
    df["比賽日期"] = pd.to_datetime(df["比賽日期"], dayfirst=True, errors="coerce")

    # 6. 只保留完成賽事的記錄
    df = df.dropna(subset=["名次", "品牌編號"]).copy()

    # 7. 拆解沿途走位
    df["走位列表"] = df["沿途走位"].astype(str).str.strip().str.split()
    df["走位列表"] = df["走位列表"].apply(
        lambda x: [int(i) for i in x if str(i).isdigit()] if isinstance(x, list) else []
    )

    return df


def get_horse_list(df: pd.DataFrame) -> pd.DataFrame:
    """取得所有馬匹清單（品牌編號 + 馬名）"""
    horses = df[["品牌編號", "馬名"]].drop_duplicates().sort_values("品牌編號")
    return horses.reset_index(drop=True)
