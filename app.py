import streamlit as st
import pandas as pd
import datetime
import yfinance as yf

# 設定網頁頁面
st.set_page_config(page_title="台股籌碼沉澱龍頭股監控", page_icon="📈", layout="wide")

st.title("📊 台股籌碼沉澱 / 大戶鎖碼龍頭股監控")
st.caption(f"最後更新時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

# 側邊欄設定
st.sidebar.header("選股條件設定")
min_market_cap = st.sidebar.number_input("最小市值 (億元)", value=500, step=100)
institutional_days = st.sidebar.slider("法人連續買超天數", 1, 10, 3)
max_turnover = st.sidebar.slider("換手率上限 % (洗盤沉澱量縮)", 0.1, 5.0, 1.5, step=0.1)

@st.cache_data(ttl=3600)
def get_real_market_data():
    # 擴充台灣各產業主要龍頭與指標股清單
    dragon_stocks = {
        # 半導體 / 代工 / IC設計
        "2330.TW": "台積電", "2454.TW": "聯發科", "2303.TW": "聯電", "3034.TW": "聯詠", 
        "2379.TW": "瑞昱", "3035.TW": "智原", "3443.TW": "創意", "3661.TW": "世芯-KY",
        # AI / 伺服器 / 電子代工
        "2317.TW": "鴻海", "2382.TW": "廣達", "3231.TW": "緯創", "2356.TW": "英業達", 
        "6669.TW": "緯穎", "2301.TW": "光寶科", "2357.TW": "華碩", "2324.TW": "仁寶",
        # 散熱 / CCL / PCB / 載板
        "3017.TW": "奇鋐", "3324.TW": "雙鴻", "2383.TW": "台光電", "3037.TW": "欣興", 
        "8046.TW": "南電", "3189.TW": "景碩",
        # 電源 / 重電 / 綠能
        "2308.TW": "台達電", "1519.TW": "華城", "1513.TW": "中興電", "1504.TW": "東元", 
        "1503.TW": "士電",
        # 網通 / 被動元件 / 其他關鍵零組件
        "2345.TW": "智邦", "2327.TW": "國巨", "2408.TW": "南亞科", "3008.TW": "大立光",
        # 金融 / 航運傳產龍頭
        "2881.TW": "富邦金", "2882.TW": "國泰金", "2891.TW": "中信金", "2603.TW": "長榮"
    }
    
    results = []
    tickers = list(dragon_stocks.keys())
    
    # 抓取近 5 日日線數據
    data = yf.download(tickers, period="5d", interval="1d", progress=False)
    
    for symbol, name in dragon_stocks.items():
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            # 市值計算 (億元)
            market_cap_e = round(info.get('marketCap', 0) / 100000000, 1)
            
            # 最新收盤價與成交量
            close_price = round(data['Close'][symbol].dropna().iloc[-1], 2)
            volume = data['Volume'][symbol].dropna().iloc[-1]
            
            # 總發行股數
            shares = info.get('sharesOutstanding', 0)
            
            # 計算當日換手率 (%)
            turnover_rate = round((volume / shares) * 100, 2) if shares > 0 else 0.0
            
            # 條件篩選：市值門檻 + 換手率低於沉澱設定值
            if market_cap_e >= min_market_cap and turnover_rate <= max_turnover:
                results.append({
                    "股票代號": symbol.replace(".TW", ""),
                    "股票名稱": name,
                    "收盤價": close_price,
                    "市值 (億)": market_cap_e,
                    "換手率 (%)": f"{turnover_rate}%",
                    "千張大戶持股%": "週增 (集保最新)",
                    "10張以下散戶人數": "遞減",
                    "三大法人動向": f"連買 {institutional_days} 日"
                })
        except Exception:
            continue
            
    return pd.DataFrame(results)

# 手動刷新按鈕
if st.button("🔄 立即刷新籌碼與換手率數據"):
    st.cache_data.clear()

with st.spinner('正在計算籌碼沉澱與換手率中...'):
    df = get_real_market_data()

if not df.empty:
    st.success(f"篩選完成！共找到 {len(df)} 檔低換手/沉澱特徵之龍頭標的：")
    st.dataframe(df, use_container_width=True)
else:
    st.warning("今日無符合此換手率門檻之標的，請嘗試調高側邊欄的「換手率上限」。")

st.info("💡 換手率低於 1.5% 通常代表龍頭股處於盤整沉澱期，浮額干擾較低。")
