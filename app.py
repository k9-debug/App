import streamlit as st
import pandas as pd
import datetime
import requests
import yfinance as yf

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
            
            # 市值 (億元)
            market_cap_e = round(info.get('marketCap', 0) / 100000000, 1)
            
            # 收盤價與歷史區間
            close_series = data['Close'][symbol].dropna()
            close_price = round(close_series.iloc[-1], 2)
            
            # 停損價與目標價
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
            
            # 易經卦象計算
            hexagram_str = get_hexagram(turnover_rate, actual_buy_days, rr_ratio)
            
            # Yahoo 股市 K 線圖網址
            tech_chart_url = f"https://tw.stock.yahoo.com/quote/{stock_id}.TW/technical-analysis"
            
            if (market_cap_e >= min_cap and 
                turnover_rate <= max_turnover_rate and 
                actual_buy_days >= req_inst_days and
                div_yield >= req_min_yield and
                rr_ratio >= req_min_rr):
                
                results.append({
                    "股票代號": stock_id,
                    "股票名稱": name,
                    "連結": tech_chart_url,
                    "當前價": close_price,
                    "易經卦象": hexagram_str,
                    "預估盈虧比": f"{rr_ratio} : 1",
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

if st.button("🔄 立即刷新籌碼、風控與卦象"):
    st.cache_data.clear()

with st.spinner('正在計算籌碼、盈虧比與易經卦象中...'):
    df = get_real_market_data(min_market_cap, institutional_days, max_turnover, min_yield, min_rr_ratio)

if not df.empty:
    st.success(f"篩選完成！共找到 {len(df)} 檔標的：")
    
    # 使用 LinkColumn 將股票名稱欄位顯示為中文，並綁定連結欄位
    st.dataframe(
        df,
        column_config={
            "連結": None,  # 隱藏純網址欄位
            "股票名稱": st.column_config.LinkColumn(
                "股票名稱",
                help="點擊股票名稱開啟 Yahoo 股市 K 線圖",
                validate=r"^https://",
                display_text=r"https://tw\.stock\.yahoo\.com/quote/.*"
            )
        },
        use_container_width=True
    )
else:
    st.warning("目前無符合篩選條件之標的。")

st.info("💡 提示：點擊表格中的『股票名稱』即可直接開啟該個股的 Yahoo 股市技術分析與 K 線圖。")
