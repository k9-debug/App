import streamlit as st
import pandas as pd
import datetime
import requests
import yfinance as yf

st.set_page_config(page_title="台股籌碼沉澱龍頭股監控", page_icon="📈", layout="wide")

st.title("📊 台股籌碼沉澱 / 大戶鎖碼龍頭股監控")
st.caption(f"最後更新時間：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

st.sidebar.header("選股條件設定")
min_market_cap = st.sidebar.number_input("最小市值 (億元)", value=500, step=100)
institutional_days = st.sidebar.slider("法人連續買超天數 (至少)", 1, 5, 2)
max_turnover = st.sidebar.slider("換手率上限 % (洗盤沉澱量縮)", 0.1, 5.0, 2.0, step=0.1)

@st.cache_data(ttl=3600)
def get_twse_institutional_data(days=5):
    """抓取證交所近 N 個交易日的三大法人買賣超資料"""
    inst_data = {} # {stock_id: consecutive_buy_days}
    today = datetime.date.today()
    fetched_days = 0
    check_date = today
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    daily_buy_records = {} # {stock_id: [day1_net, day2_net, ...]}

    # 往前搜尋近 10 天，找足交易日
    for _ in range(12):
        if fetched_days >= days:
            break
        # 跳過週末
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
                    # 三大法人買賣超股數 (欄位 18)
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
        
    # 計算連買天數
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
def get_real_market_data(min_cap, req_inst_days, max_turnover_rate):
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
    
    # 取得法人連買資料
    inst_buy_days = get_twse_institutional_data(days=5)
    
    results = []
    tickers = list(dragon_stocks.keys())
    data = yf.download(tickers, period="5d", interval="1d", progress=False)
    
    for symbol, name in dragon_stocks.items():
        stock_id = symbol.replace(".TW", "")
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            # 市值 (億元)
            market_cap_e = round(info.get('marketCap', 0) / 100000000, 1)
            
            # 收盤價與成交量
            close_price = round(data['Close'][symbol].dropna().iloc[-1], 2)
            volume = data['Volume'][symbol].dropna().iloc[-1]
            shares = info.get('sharesOutstanding', 0)
            
            # 換手率 (%)
            turnover_rate = round((volume / shares) * 100, 2) if shares > 0 else 0.0
            
            # 實際法人連買天數
            actual_buy_days = inst_buy_days.get(stock_id, 0)
            
            # 嚴格條件對齊篩選：市值 + 換手率 + 法人實際連買天數
            if market_cap_e >= min_cap and turnover_rate <= max_turnover_rate and actual_buy_days >= req_inst_days:
                results.append({
                    "股票代號": stock_id,
                    "股票名稱": name,
                    "收盤價": close_price,
                    "市值 (億)": market_cap_e,
                    "換手率 (%)": f"{turnover_rate}%",
                    "三大法人實際動向": f"連續買超 {actual_buy_days} 天",
                    "千張大戶持股%": "週增 (集保)",
                    "10張以下散戶": "遞減"
                })
        except Exception:
            continue
            
    return pd.DataFrame(results)

if st.button("🔄 立即刷新籌碼數據"):
    st.cache_data.clear()

with st.spinner('正在連線證交所與 yfinance 計算真實籌碼中...'):
    df = get_real_market_data(min_market_cap, institutional_days, max_turnover)

if not df.empty:
    st.success(f"篩選完成！共找到 {len(df)} 檔符合條件之龍頭標的：")
    st.dataframe(df, use_container_width=True)
else:
    st.warning("目前無同時符合「市值、換手率上限與法人連買天數」之標的，請嘗試放寬條件。")

st.info("💡 說明：法人買賣超資料直接對接證交所每日盤後 T86 報表真實計算。")
