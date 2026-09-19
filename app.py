import streamlit as st
import pandas as pd
import datetime

# 設定網頁標題與圖示
st.set_page_config(page_title="台股籌碼沉澱龍頭股監控", page_icon="📈", layout="wide")

st.title("📊 台股籌碼沉澱 / 大戶鎖碼龍頭股監控")
st.caption(f"最後更新時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

# 側邊欄：設定條件參數
st.sidebar.header("選股條件設定")
min_market_cap = st.sidebar.number_input("最小市值 (億元)", value=500, step=100)
institutional_days = st.sidebar.slider("法人連續買超天數", 1, 10, 3)

# 核心選股 logic
@st.cache_data(ttl=3600) # 快取 1 小時，避免頻繁抓取
def fetch_and_filter_stocks():
    # 這裡放前面的籌碼篩選邏輯，回傳測試用的範例 DataFrame
    data = [
        {"股票代號": "2330", "股票名稱": "台積電", "收盤價": 980.0, "千張大戶持股%": "87.5%", "10張以下散戶人數": "遞減", "法人動向": "連買 3 日"},
        {"股票代號": "2317", "股票名稱": "鴻海", "收盤價": 180.5, "千張大戶持股%": "65.2%", "10張以下散戶人數": "遞減", "法人動向": "連買 5 日"},
        {"股票代號": "2345", "股票名稱": "智邦", "收盤價": 550.0, "千張大戶持股%": "72.1%", "10張以下散戶人數": "持續減少", "法人動向": "連買 4 日"}
    ]
    return pd.DataFrame(data)

# 按鈕：手動刷新
if st.button("🔄 立即執行籌碼篩選"):
    st.cache_data.clear()

with st.spinner('正在分析盤後籌碼與集保數據中...'):
    df = fetch_and_filter_stocks()

# 在網頁呈現數據表格
if not df.empty:
    st.success(f"篩選完成！共找到 {len(df)} 檔符合籌碼沉澱條件之標的：")
    st.dataframe(df, use_container_width=True)
else:
    st.warning("今日無符合籌碼完全沉澱之標的。")

st.info("💡 說明：千張大戶與散戶人數每週五盤後更新；三大法人買賣超與價格每日盤後更新。")
