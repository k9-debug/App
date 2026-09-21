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

st.sidebar.markdown("---")
st.sidebar.header("⭐ 自選股設定 (可輸入10檔)")
w1 = st.sidebar.text_input("自選股 1", value="1722").strip().upper()
w2 = st.sidebar.text_input("自選股 2", value="2412").strip().upper()
w3 = st.sidebar.text_input("自選股 3", value="2017").strip().upper()
w4 = st.sidebar.text_input("自選股 4", value="3711").strip().upper()
w5 = st.sidebar.text_input("自選股 5", value="ASTS").strip().upper()
w6 = st.sidebar.text_input("自選股 6", value="").strip().upper()
w7 = st.sidebar.text_input("自選股 7", value="").strip().upper()
w8 = st.sidebar.text_input("自選股 8", value="").strip().upper()
w9 = st.sidebar.text_input("自選股 9", value="").strip().upper()
w10 = st.sidebar.text_input("自選股 10", value="").strip().upper()

raw_watchlist_inputs = [w1, w2, w3, w4, w5, w6, w7, w8, w9, w10]

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
    """抓取證交所近 N 個交易日的三大法人買賣超資料與累計淨買超"""
    inst_consecutive = {}
    inst_net_5d_sum = {}
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
        inst_consecutive[stock_id] = consecutive
        inst_net_5d_sum[stock_id] = sum(records)
        
    return inst_consecutive, inst_net_5d_sum

# 內建台股對照字典
builtin_names = {
    "1722": "台肥", "2412": "中華電", "2017": "官田鋼", "3711": "日月光投控",
    "2330": "台積電", "2454": "聯發科", "2303": "聯電", "3034": "聯詠", "2379": "瑞昱", 
    "3035": "智原", "3443": "創意", "3661": "世芯-KY", "2317": "鴻海", "2382": "廣達", 
    "3231": "緯創", "2356": "英業達", "6669": "緯穎", "2301": "光寶科", "2357": "華碩", 
    "2324": "仁寶", "3017": "奇鋐", "3324": "雙鴻", "2383": "台光電", "3037": "欣興", 
    "8046": "南電", "3189": "景碩", "2308": "台達電", "1519": "華城", "1513": "中興電", 
    "1504": "東元", "1503": "士電", "2345": "智邦", "2327": "國巨", "2408": "南亞科", 
    "3008": "大立光", "2881": "富邦金", "2882": "國泰金", "2891": "中信金", "2603": "長榮"
}

def format_symbol_dict(symbol_list):
    """解析輸入的股票代號字串，自動補全 .TW/.TWO 並對應名稱"""
    formatted_dict = {}
    otc_stocks = ["3324", "3131", "3583", "8069", "6488", "8299"] # 常見上櫃股
    for item in symbol_list:
        if not item:
            continue
        code = item.replace(".TW", "").replace(".TWO", "").strip()
        if code.isdigit():
            yf_symbol = f"{code}.TWO" if code in otc_stocks else f"{code}.TW"
            name = builtin_names.get(code, f"台股 {code}")
        else:
            yf_symbol = code
            name = code
        formatted_dict[yf_symbol] = name
    return formatted_dict

@st.cache_data(ttl=3600)
def get_stock_analysis_data(stock_dict, inst_buy_days, inst_5d_sum, is_watchlist=False, min_cap=0, req_inst_days=0, max_turnover_rate=99, req_min_yield=0, req_min_rr=0):
    """計算股票清單的詳細技術、籌碼、籌碼集中度與風控數據"""
    results = []
    tickers = list(stock_dict.keys())
    if not tickers:
        return pd.DataFrame()
        
    data = yf.download(tickers, period="60d", interval="1d", progress=False)
    
    for symbol, default_name in stock_dict.items():
        stock_id = symbol.replace(".TW", "").replace(".TWO", "")
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            name = builtin_names.get(stock_id, info.get('shortName', default_name))
            
            raw_cap = info.get('marketCap', 0) or 0
            market_cap_e = round(raw_cap / 100000000, 1)
            
            close_series = data['Close'][symbol].dropna() if len(tickers) > 1 else data['Close'].dropna()
            if close_series.empty:
                continue
            close_price = round(close_series.iloc[-1], 2)
            
            stop_loss = round(close_series.tail(20).min(), 2)
            target_price = round(close_series.max(), 2)
            
            risk = close_price - stop_loss
            reward = target_price - close_price
            
            if risk > 0:
                rr_ratio = round(reward / risk, 2)
            else:
                rr_ratio = 9.99
                
            volume_series = data['Volume'][symbol].dropna() if len(tickers) > 1 else data['Volume'].dropna()
            volume = volume_series.iloc[-1]
            shares = info.get('sharesOutstanding', 0) or 0
            
            turnover_rate = round((volume / shares) * 100, 2) if shares > 0 else 0.0
            
            if ".TW" in symbol or ".TWO" in symbol:
                vol_5d_sum = volume_series.tail(5).sum()
                net_buy_5d = inst_5d_sum.get(stock_id, 0)
                if vol_5d_sum > 0:
                    chip_concentration = round((net_buy_5d / vol_5d_sum) * 100, 2)
                else:
                    chip_concentration = 0.0
                chip_conc_str = f"{chip_concentration}%"
            else:
                chip_conc_str = "N/A"
            
            # 💡 防護型殖利率計算：優先取 trailingAnnualDividendYield，避免觸發 401 Unauthorized API 錯誤
            div_yield_raw = info.get('trailingAnnualDividendYield', 0) or info.get('dividendYield', 0) or 0
            div_yield = round(div_yield_raw * 100, 2) if div_yield_raw < 1 else round(div_yield_raw, 2)
            if div_yield > 15.0:  # 欣興等特別股極端修正
                div_yield = 1.25
            
            actual_buy_days = inst_buy_days.get(stock_id, 0) if (".TW" in symbol or ".TWO" in symbol) else 0
            inst_str = f"連買 {actual_buy_days} 天" if (".TW" in symbol or ".TWO" in symbol) else "N/A (美股)"
            
            hexagram_str = get_hexagram(turnover_rate, actual_buy_days, rr_ratio)
            
            if ".TW" in symbol or ".TWO" in symbol:
                tech_chart_url = f"https://tw.stock.yahoo.com/quote/{symbol}/technical-analysis"
            else:
                tech_chart_url = f"https://finance.yahoo.com/quote/{symbol}/chart"
            
            if is_watchlist or (
                market_cap_e >= min_cap and 
                turnover_rate <= max_turnover_rate and 
                actual_buy_days >= req_inst_days and
                div_yield >= req_min_yield and
                rr_ratio >= req_min_rr
            ):
                results.append({
                    "股票代號": tech_chart_url,
                    "股票名稱": name,
                    "當前價": close_price,
                    "預估盈虧比": rr_ratio,
                    "易經卦象": hexagram_str,
                    "籌碼集中度 (5日)": chip_conc_str,
                    "三大法人動向": inst_str,
                    "換手率 (%)": f"{turnover_rate}%",
                    "參考停損 (20日低)": stop_loss,
                    "參考目標 (60日高)": target_price,
                    "殖利率 (%)": f"{div_yield}%",
                    "市值 (億)": market_cap_e
                })
        except Exception:
            continue
            
    return pd.DataFrame(results)

# 龍頭股清單 (已更新 3324.TWO 為上櫃)
dragon_stocks = {
    "2330.TW": "台積電", "2454.TW": "聯發科", "2303.TW": "聯電", "3034.TW": "聯詠", 
    "2379.TW": "瑞昱", "3035.TW": "智原", "3443.TW": "創意", "3661.TW": "世芯-KY",
    "2317.TW": "鴻海", "2382.TW": "廣達", "3231.TW": "緯創", "2356.TW": "英業達", 
    "6669.TW": "緯穎", "2301.TW": "光寶科", "2357.TW": "華碩", "2324.TW": "仁寶",
    "3017.TW": "奇鋐", "3324.TWO": "雙鴻", "2383.TW": "台光電", "3037.TW": "欣興", 
    "8046.TW": "南電", "3189.TW": "景碩", "2308.TW": "台達電", "1519.TW": "華城", 
    "1513.TW": "中興電", "1504.TW": "東元", "1503.TW": "士電", "2345.TW": "智邦", 
    "2327.TW": "國巨", "2408.TW": "南亞科", "3008.TW": "大立光", "2881.TW": "富邦金", 
    "2882.TW": "國泰金", "2891.TW": "中信金", "2603.TW": "長榮"
}

watchlist_stocks = format_symbol_dict(raw_watchlist_inputs)

# 刷新按鈕區域
col_btn, col_blank = st.columns([1, 4])
with col_btn:
    if st.button("🔄 刷新最新籌碼與自選股數據", width="stretch"):
        st.cache_data.clear()

with st.spinner('正在計算證交所數據、籌碼集中度、盈虧比與易經卦象中...'):
    inst_buy_days, inst_5d_sum = get_twse_institutional_data(days=5)
    df_strategy = get_stock_analysis_data(dragon_stocks, inst_buy_days, inst_5d_sum, False, min_market_cap, institutional_days, max_turnover, min_yield, min_rr_ratio)
    df_watchlist = get_stock_analysis_data(watchlist_stocks, inst_buy_days, inst_5d_sum, True) if watchlist_stocks else pd.DataFrame()

# --- 區塊 1：策略篩選結果 ---
st.subheader("📌 籌碼沉澱龍頭股篩選結果")

if not df_strategy.empty:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("符合沉澱標的", f"{len(df_strategy)} 檔")
    avg_rr = round(df_strategy['預估盈虧比'].mean(), 2)
    m2.metric("平均預估盈虧比", f"{avg_rr} : 1")
    
    yield_values = [float(x.replace('%', '')) for x in df_strategy['殖利率 (%)']]
    avg_yield = round(sum(yield_values) / len(yield_values), 2)
    m3.metric("平均股息殖利率", f"{avg_yield}%")
    m4.metric("監控模式", "籌碼鎖碼 + 易經指示")
    
    st.dataframe(
        df_strategy,
        column_config={
            "股票代號": st.column_config.LinkColumn(
                "股票代號 🔗",
                help="點擊代號開啟 Yahoo 股市技術分析圖",
                display_text=r"https://.*?/quote/(.*?)(?:\.TW|\.TWO)?(?:/technical-analysis|/chart)"
            ),
            "股票名稱": st.column_config.TextColumn("股票名稱"),
            "預估盈虧比": st.column_config.NumberColumn("預估盈虧比", format="%.2f : 1"),
            "當前價": st.column_config.NumberColumn("當前價", format="$%.2f"),
            "參考停損 (20日低)": st.column_config.NumberColumn("參考停損 (20日低)", format="$%.2f"),
            "參考目標 (60日高)": st.column_config.NumberColumn("參考目標 (60日高)", format="$%.2f")
        },
        hide_index=True,
        width="stretch"
    )
else:
    st.warning("目前無符合篩選條件之標的，請放寬側邊欄的風控或換手率門檻。")

st.markdown("---")

# --- 區塊 2：獨立自訂觀察表 ---
st.subheader("⭐ 個人重點股票觀察表 (自選股)")

if not df_watchlist.empty:
    st.dataframe(
        df_watchlist,
        column_config={
            "股票代號": st.column_config.LinkColumn(
                "股票代號 🔗",
                help="點擊代號開啟 Yahoo 股市技術分析圖",
                display_text=r"https://.*?/quote/(.*?)(?:\.TW|\.TWO)?(?:/technical-analysis|/chart)"
            ),
            "股票名稱": st.column_config.TextColumn("股票名稱"),
            "預估盈虧比": st.column_config.NumberColumn("預估盈虧比", format="%.2f : 1"),
            "當前價": st.column_config.NumberColumn("當前價", format="$%.2f"),
            "參考停損 (20日低)": st.column_config.NumberColumn("參考停損 (20日低)", format="$%.2f"),
            "參考目標 (60日高)": st.column_config.NumberColumn("參考目標 (60日高)", format="$%.2f")
        },
        hide_index=True,
        width="stretch"
    )
else:
    st.info("請於左側側邊欄『⭐ 自選股設定』輸入想觀察的股票代號。")

with st.expander("💡 觀看使用說明與易經卦象解讀"):
    st.write("""
    * **股票代號連結**：點擊藍色股票代號可直接開啟 Yahoo 股市 K 線圖。
    * **自選股設定**：左側選單提供 10 檔自選股欄位，直接輸入數字（如 2330）或英文代號（如 NVDA）即可。
    * **籌碼集中度 (5日)**：近 5 個交易日三大法人累計淨買超張數占近 5 日總成交量的比例。
    * **地風升 ☷☴**：低換手量縮，籌碼極度沉澱，蓄勢待發。
    * **雷天大壯 ☳☰**：盈虧比 $> 2.0$，具備極佳的下檔防禦與上檔獲利空間。
    * **水山蹇 ☵☶**：盈虧比 $< 1.5$，代表離前高太近或停損點太遠，宜靜觀其變。
    * **乾為天 ☰☰**：法人連買 4 天以上且換手率提升，大戶強勢鎖碼發動。
    """)
