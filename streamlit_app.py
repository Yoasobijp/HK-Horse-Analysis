# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

from data_loader import load_data, get_horse_list
from analyzer import (
    整體概況, 路程分析, 場地分析, 騎師分析, 騎師路程分析,
    檔位分析, 檔位優勢指數,
    賠率分析, 賠率相關性, 個別馬匹賠率表現,
    走位模式分析, 走位提升分析, 走位明細,
)

st.set_page_config(
    page_title="香港賽馬馬匹查詢及分析系統",
    page_icon="🐎",
    layout="wide",
)

st.title("🐎 香港賽馬馬匹查詢及分析系統")
st.caption("資料來源：2025/26 賽季香港賽馬結果")

try:
    df = load_data("hkjc_results_25_26.xlsx")
except FileNotFoundError:
    st.error("找不到 hkjc_results_25_26.xlsx，請確認檔案位於同一目錄下。")
    st.stop()

horses = get_horse_list(df)

# ============ 側邊欄 ============
st.sidebar.header("🔍 馬匹查詢")
查詢方式 = st.sidebar.radio("查詢方式", ["輸入品牌編號", "從清單選擇"])

if 查詢方式 == "輸入品牌編號":
    品牌編號 = st.sidebar.text_input("品牌編號（如 J266）", value="").strip().upper()
else:
    選項 = horses.apply(lambda r: f"{r['品牌編號']} - {r['馬名']}", axis=1).tolist()
    選中 = st.sidebar.selectbox("選擇馬匹", options=[""] + 選項)
    品牌編號 = 選中.split(" - ")[0] if 選中 else ""

st.sidebar.markdown("---")
st.sidebar.metric("資料總筆數", f"{len(df):,}")
st.sidebar.metric("馬匹總數", f"{df['品牌編號'].nunique():,}")

# ============ 主畫面 ============
if not 品牌編號:
    st.info("👈 請在左側輸入馬匹品牌編號，或從清單中選擇一匹馬。")
    st.subheader("📋 資料預覽")
    st.dataframe(df.head(20), use_container_width=True)
    st.subheader("🏇 可查詢的馬匹（前 50 匹）")
    st.dataframe(horses.head(50), use_container_width=True)
    st.stop()

if 品牌編號 not in df["品牌編號"].values:
    st.error(f"❌ 找不到品牌編號「{品牌編號}」，請確認輸入是否正確。")
    st.stop()

馬名 = df[df["品牌編號"] == 品牌編號]["馬名"].iloc[0]
st.header(f"🏇 {馬名} （{品牌編號}）")

# ============ 整體概況 ============
概況 = 整體概況(df, 品牌編號)
st.subheader("📊 整體概況")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("出賽次數", 概況["出賽次數"])
col2.metric("冠", 概況["冠"])
col3.metric("亞", 概況["亞"])
col4.metric("季", 概況["季"])
col5.metric("勝率", f"{概況['勝率']:.1%}")
col6.metric("入位率", f"{概況['入位率']:.1%}")

col7, col8 = st.columns(2)
col7.metric("平均名次", 概況["平均名次"])
col8.metric("最佳名次", 概況["最佳名次"])

# ============ 分頁 ============
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["🛤️ 路程/場地", "🧑‍✈️ 騎師", "📍 檔位", "💰 賠率", "🏃 走位", "📋 明細"]
)

with tab1:
    st.subheader("路程表現")
    路 = 路程分析(df, 品牌編號)
    if not 路.empty:
        st.dataframe(路, use_container_width=True)
        fig = px.bar(路.reset_index(), x="路程", y="平均名次",
                     title="各路程平均名次（越低越好）",
                     color="出賽", text="出賽")
        fig.update_layout(yaxis_autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("無路程資料")

    st.subheader("場地表現")
    場 = 場地分析(df, 品牌編號)
    if not 場.empty:
        st.dataframe(場, use_container_width=True)

with tab2:
    st.subheader("騎師合作表現")
    騎 = 騎師分析(df, 品牌編號)
    if not 騎.empty:
        st.dataframe(騎, use_container_width=True)
        fig = px.bar(騎.reset_index(), x="騎師", y="平均名次",
                     color="合作次數", text="合作次數",
                     title="各騎師平均名次（越低越好）")
        fig.update_layout(yaxis_autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("騎師 × 路程 交叉分析")
    騎路 = 騎師路程分析(df, 品牌編號)
    if not 騎路.empty:
        st.dataframe(騎路, use_container_width=True)

with tab3:
    st.subheader("檔位區間表現")
    檔 = 檔位分析(df, 品牌編號)
    if not 檔.empty:
        st.dataframe(檔, use_container_width=True)
    else:
        st.info("無檔位資料")

    st.markdown("---")
    st.subheader("全體檔位優勢分析")
    c1, c2 = st.columns(2)
    with c1:
        場地選 = st.selectbox("場地", sorted(df["場地"].dropna().unique()))
    with c2:
        路程選 = st.selectbox("路程", sorted(df["路程"].dropna().unique().astype(int)))

    檔優 = 檔位優勢指數(df, 場地選, 路程選)
    if not 檔優.empty and len(檔優) > 1:
        st.dataframe(檔優, use_container_width=True)
        fig = px.bar(檔優.reset_index(), x="檔位", y="檔位優勢指數",
                     title=f"{場地選} {路程選}m 各檔位優勢指數（越高越好）",
                     text="出賽")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("此條件下資料不足")

with tab4:
    st.subheader("賠率區間表現")
    賠 = 賠率分析(df, 品牌編號)
    if not 賠.empty:
        st.dataframe(賠, use_container_width=True)

    st.subheader("此駒賠率與名次明細")
    賠明 = 個別馬匹賠率表現(df, 品牌編號)
    if not 賠明.empty:
        st.dataframe(賠明, use_container_width=True)
        fig = px.scatter(賠明, x="獨贏賠率", y="名次",
                         hover_data=["比賽日期", "騎師"],
                         title="賠率 vs 名次（此駒）")
        fig.update_layout(yaxis_autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("全市場賠率效率")
    相關 = 賠率相關性(df)
    if 相關:
        st.json(相關)

with tab5:
    st.subheader("走位模式分析")
    走 = 走位模式分析(df, 品牌編號)
    if not 走.empty:
        st.dataframe(走, use_container_width=True)
        fig = px.bar(走.reset_index(), x="走位模式", y="入位率",
                     title="各走位模式入位率", text="出賽")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("無走位資料")

    st.subheader("衝刺提升分析")
    升 = 走位提升分析(df, 品牌編號)
    if not 升.empty:
        st.dataframe(升, use_container_width=True)

    st.subheader("走位明細")
    明 = 走位明細(df, 品牌編號)
    if not 明.empty:
        st.dataframe(明, use_container_width=True)

with tab6:
    st.subheader("完整往績")
    明細 = df[df["品牌編號"] == 品牌編號].copy()
    cols = ["比賽日期", "場地", "場次", "班別", "路程", "場地狀況",
            "賽道", "名次", "馬號", "騎師", "練馬師", "實際負磅",
            "檔位", "沿途走位", "完成時間", "獨贏賠率"]
    cols = [c for c in cols if c in 明細.columns]
    明細 = 明細[cols].sort_values("比賽日期")
    st.dataframe(明細, use_container_width=True)

    csv = 明細.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 下載 CSV", csv,
                       file_name=f"{品牌編號}_往績.csv",
                       mime="text/csv")
