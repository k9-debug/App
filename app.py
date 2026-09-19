import streamlit as st
import pandas as pd
import datetime
import requests
import yfinance as yf

# 頁面配置
st.set_page_config(page_title="台股籌碼沉澱龍頭股監控", page_icon="📈", layout="wide")

st.title("📊 台股籌碼沉澱 / 大戶鎖碼龍頭股監控 ☯️")
st.caption(f"最後更新時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

# 側邊欄設定
st.sidebar.header("選股條件設定")
min_market_cap = st.sidebar.number_input("最小市值 (億元)", value=500, step=100)
institutional_days = st.sidebar.slider("法人連續買超天數 (至少)", 1, 5, 2)
max_turnover = st.sidebar.slider("換手率上限 % (洗盤沉澱量縮)", 0.1, 5.0, 2.0, step=0.1)
min_yield = st.sidebar.slider("最低殖利率 % (股利下檔防禦)", 0.0, 8.0, 0.0, step=0.5)
min_rr_ratio = st.sidebar.slider("最低預估盈虧比 (風控過濾)", 1.0, 5.0, 1.0, step=0.5)

def get_hexagram(turnover_rate, actual_buy_days, rr_ratio):
    """根據籌碼與風控指標自動對應易經卦象"""
    if actual_buy_days >= 4 and turnover_rate >= 1.0:
        return "乾為天 ☰☰ (大戶強攻)"
    elif turnover_rate < 0.8 and actual_buy_days >= 2:
        return "地風升 ☷☴ (沉澱蓄勢)"
    elif rr_ratio >= 2.0 and actual_buy_days >= 2:
        return "雷天大壯 ☳☰ (風控極佳)"
    elif rr_ratio < 1.5:
        return "水山蹇 ☵☶ (空間受限)"
    else:
        return "坤為地 ☷☷ (量縮打底)"

@st.cache_data(ttl=3600)
def get_twse_institutional_data(days=5):
    """抓取證交所近 N 個交易日的三大法人買賣超資料"""
    inst_data = {}
    today = datetime.date.today()
    fetched_days = 0
    check_date = today
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    daily_buy_records = {}

    for _ in range(12):
        if fetched_days >= days:
            break
        if check_date.weekday() >= 5:
            check_date -= datetime.timedelta(days=1)
            continue
            
        date_str = check_date.strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALL"
        
        try:
            res = requests.get(url, headers=headers, timeout=5)
            data = res.json()
            if data.get("stat") == "OK" and "data" in data:
                fetched_days += 1
                for row in data["data"]:
                    stock_id = row[0].strip()
                    try:
                        net_buy = int(row[18].replace(',', ''))
                    except ValueError:
                        net_buy = 0
                    
                    if stock_id not in daily_buy_records:
                        daily_buy_records[stock_id] = []
                    daily_buy_records[stock_id].append(net_buy)
        except Exception:
            pass
            
        check_date -= datetime.timedelta(days=1)
        
    for stock_id, records in daily_buy_records.items():
        consecutive = 0
        for net in records:
            if net > 0:
                consecutive += 1
            else:
                break
        inst_data[stock_id] = consecutive
        
    return inst_data

@st.cache_data(ttl=3600)
def get_real_market_data(min_cap, req_inst_days, max_turnover_rate, req_min_yield, req_min_rr):
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
    
    inst_buy_days = get_twse_institutional_data(days=5)
    
    results = []
    tickers = list(dragon_stocks.keys())
    data = yf.download(tickers, period="60d", interval="1d", progress=False)
    
    for symbol, name in dragon_stocks.items():
        stock_id = symbol.replace(".TW", "")
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            market_cap_e = round(info.get('marketCap', 0) / 100000000, 1)
            
            close_series = data['Close'][symbol].dropna()
            close_price = round(close_series.iloc[-1], 2)
            
            stop_loss = round(close_series.tail(20).min(), 2)
            target_price = round(close_series.max(), 2)
            
            risk = close_price - stop_loss
            reward = target_price - close_price
            
            if risk > 0:
                rr_ratio = round(reward / risk, 2)
            else:
                rr_ratio = 9.99
                
            volume = data['Volume'][symbol].dropna().iloc[-1]
            shares = info.get('sharesOutstanding', 0)
            
            turnover_rate = round((volume / shares) * 100, 2) if shares > 0 else 0.0
            
            div_yield_raw = info.get('dividendYield', 0) or 0
            div_yield = round(div_yield_raw * 100, 2) if div_yield_raw < 1 else round(div_yield_raw, 2)
            
            actual_buy_days = inst_buy_days.get(stock_id, 0)
            hexagram_str = get_hexagram(turnover_rate, actual_buy_days, rr_ratio)
            
            tech_chart_url = f"https://tw.stock.yahoo.com/quote/{stock_id}.TW/technical-analysis"
            
            if (market_cap_e >= min_cap and 
                turnover_rate <= max_turnover_rate and 
                actual_buy_days >= req_inst_days and
                div_yield >= req_min_yield and
                rr_ratio >= req_min_rr):
                
                results.append({
                    "股票代號": tech_chart_url,
                    "股票名稱": name,
                    "當前價": close_price,
                    "預估盈虧比": rr_ratio,
                    "易經卦象": hexagram_str,
                    "換手率 (%)": f"{turnover_rate}%",
                    "三大法人動向": f"連買 {actual_buy_days} 天",
                    "參考停損 (20日低)": stop_loss,
                    "參考目標 (60日高)": target_price,
                    "殖利率 (%)": f"{div_yield}%",
                    "市值 (億)": market_cap_e
                })
        except Exception:
            continue
            
    return pd.DataFrame(results)

# 刷新按鈕區域
col_btn, col_blank = st.columns([1, 4])
with col_btn:
    if st.button("🔄 刷新最新籌碼數據", use_container_width=True):
        st.cache_data.clear()

with st.spinner('正在計算證交所數據、盈虧比與易經卦象中...'):
    df = get_real_market_data(min_market_cap, institutional_days, max_turnover, min_yield, min_rr_ratio)

if not df.empty:
    # 頂部關鍵數據指標卡片
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("符合沉澱標的", f"{len(df)} 檔")
    avg_rr = round(df['預估盈虧比'].mean(), 2)
    m2.metric("平均預估盈虧比", f"{avg_rr} : 1")
    
    # 解析殖利率平均值
    yield_values = [float(x.replace('%', '')) for x in df['殖利率 (%)']]
    avg_yield = round(sum(yield_values) / len(yield_values), 2)
    m3.metric("平均股息殖利率", f"{avg_yield}%")
    m4.metric("監控模式", "籌碼鎖碼 + 易經指示")
    
    st.markdown("---")
    
    # 表格欄位格式化（格式化盈虧比欄位，並隱藏行索引 0,1,2,3）
    st.dataframe(
        df,
        column_config={
            "股票代號": st.column_config.LinkColumn(
                "股票代號 🔗",
                help="點擊代號開啟 Yahoo 股市技術分析圖",
                display_text=r"https://tw\.stock\.yahoo\.com/quote/(.*?)\.TW/technical-analysis"
            ),
            "股票名稱": st.column_config.TextColumn("股票名稱"),
            "預估盈虧比": st.column_config.NumberColumn(
                "預估盈虧比",
                format="%.2f : 1"
            ),
            "當前價": st.column_config.NumberColumn("當前價", format="$%.2f"),
            "參考停損 (20日低)": st.column_config.NumberColumn("參考停損 (20日低)", format="$%.2f"),
            "參考目標 (60日高)": st.column_config.NumberColumn("參考目標 (60日高)", format="$%.2f")
        },
        hide_index=True,
        use_container_width=True
    )
    
    # 說明摺疊區塊（節省空間）
    with st.expander("💡 觀看使用說明與易經卦象解讀"):
        st.write("""
        * **股票代號連結**：點擊藍色股票代號可直接開啟 Yahoo 股市 K 線圖。
        * **地風升 ☷☴**：低換手量縮，籌碼極度沉澱，蓄勢待發。
        * **雷天大壯 ☳☰**：盈虧比 $> 2.0$，具備極佳的下檔防禦與上檔獲利空間。
        * **水山蹇 ☵☶**：盈虧比 $< 1.5$，代表離前高太近或停損點太遠，宜靜觀其變。
        * **乾為天 ☰☰**：法人連買 4 天以上且換手率提升，大戶強勢鎖碼發動。
        """)
else:
    st.warning("目前無符合篩選條件之標的，請放寬側邊欄的風控或換手率門檻。")
