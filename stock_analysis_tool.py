import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime, timedelta
import yfinance as yf

st.set_page_config(page_title="信用残分析ツール", layout="wide")
st.title("📈 銘柄別 信用残高（買い・売り）分析ツール")

# ========================
# 1. サイドバー設定
# ========================
with st.sidebar:
    st.header("⚙️ 設定")
    
    # 銘柄コード入力
    ticker = st.text_input("銘柄コードを入力 (例: 7974.T)", "7974.T")
    
    # 期間選択
    period_options = {
        "1ヶ月": "1mo",
        "3ヶ月": "3mo",
        "6ヶ月": "6mo",
        "1年": "1y",
        "2年": "2y"
    }
    selected_period = st.selectbox("分析期間を選択", list(period_options.keys()), index=1)
    period = period_options[selected_period]
    
    # グラフ表示オプション
    show_ma = st.checkbox("移動平均線を表示（5日/20日/60日）", value=True)
    show_volume = st.checkbox("出来高を表示", value=True)

# ========================
# 2. データ取得関数
# ========================
@st.cache_data(ttl=3600)  # 1時間キャッシュ
def get_stock_data(ticker, period):
    """yfinanceから株価データを取得"""
    try:
        data = yf.download(ticker, period=period, progress=False)
        if data.empty:
            st.error(f"❌ 銘柄 '{ticker}' のデータが見つかりません")
            return None
        return data
    except Exception as e:
        st.error(f"❌ データ取得エラー: {str(e)}")
        return None

@st.cache_data(ttl=3600)
def get_margin_data(ticker_base):
    """日本株の信用残データを取得（ダミーデータ）
    実際にはJ-Quants APIなどを使用"""
    try:
        dates = pd.date_range(end=datetime.today(), periods=100, freq="B")  # 営業日
        
        # トレンド付きダミーデータ
        base_buy = 1500000
        base_sell = 400000
        
        margin_buy = base_buy + np.cumsum(np.random.randn(len(dates)) * 50000)
        margin_sell = base_sell + np.cumsum(np.random.randn(len(dates)) * 30000)
        
        df_margin = pd.DataFrame({
            "Date": dates,
            "Margin_Buy": np.maximum(margin_buy, base_buy * 0.5),
            "Margin_Sell": np.maximum(margin_sell, base_sell * 0.3)
        })
        return df_margin
    except Exception as e:
        st.error(f"❌ 信用残データ取得エラー: {str(e)}")
        return None

# ========================
# 3. 移動平均線の計算
# ========================
def add_moving_averages(df, windows=[5, 20, 60]):
    """移動平均線を追加"""
    for window in windows:
        df[f'MA{window}'] = df['Close'].rolling(window=window).mean()
    return df

# ========================
# 4. メインロジック
# ========================
st.subheader(f"📊 {ticker} の分析")

# データ取得
with st.spinner("📥 データを取得中..."):
    df_stock = get_stock_data(ticker, period)
    df_margin = get_margin_data(ticker)

if df_stock is None or df_margin is None:
    st.stop()

# インデックスをリセット
df_stock = df_stock.reset_index()
df_stock.columns = [col.lower() for col in df_stock.columns]

# 移動平均線を追加
if show_ma:
    df_stock = add_moving_averages(df_stock)

# データの同期（共通の日付に合わせる）
df_stock['date'] = pd.to_datetime(df_stock['date']).dt.date
df_margin['Date'] = df_margin['Date'].dt.date

# ========================
# 5. メイングラフト作成
# ========================
fig = make_subplots(
    rows=3, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    row_heights=[0.5, 0.25, 0.25],
    subplot_titles=(
        f"[{ticker}] 株価推移",
        "信用買い残(青) / 売り残(赤)",
        "出来高" if show_volume else ""
    )
)

# 【第1段】株価グラフ
fig.add_trace(
    go.Scatter(
        x=df_stock["date"],
        y=df_stock["close"],
        name="終値",
        line=dict(color="black", width=2),
        hovertemplate="<b>%{x}</b><br>終値: ¥%{y:.0f}<extra></extra>"
    ),
    row=1, col=1
)

# 移動平均線
if show_ma:
    colors = ["#FFA500", "#00CED1", "#FF69B4"]  # オレンジ、シアン、ホットピンク
    windows = [5, 20, 60]
    for window, color in zip(windows, colors):
        fig.add_trace(
            go.Scatter(
                x=df_stock["date"],
                y=df_stock[f"MA{window}"],
                name=f"MA{window}",
                line=dict(color=color, width=1, dash="dash"),
                hovertemplate="<b>MA{window}:</b> ¥%{y:.0f}<extra></extra>"
            ),
            row=1, col=1
        )

# 【第2段】信用残グラフ
fig.add_trace(
    go.Bar(
        x=df_margin["Date"],
        y=df_margin["Margin_Buy"],
        name="信用買い残",
        marker_color="#1f77b4",
        hovertemplate="<b>買い残:</b> %{y:,.0f} 株<extra></extra>"
    ),
    row=2, col=1
)

fig.add_trace(
    go.Bar(
        x=df_margin["Date"],
        y=df_margin["Margin_Sell"],
        name="信用売り残",
        marker_color="#d62728",
        hovertemplate="<b>売り残:</b> %{y:,.0f} 株<extra></extra>"
    ),
    row=2, col=1
)

# 【第3段】出来高（オプション）
if show_volume:
    fig.add_trace(
        go.Bar(
            x=df_stock["date"],
            y=df_stock["volume"],
            name="出来高",
            marker_color="rgba(100, 150, 200, 0.5)",
            hovertemplate="<b>出来高:</b> %{y:,.0f}<extra></extra>"
        ),
        row=3, col=1
    )

# ========================
# 6. レイアウト調整
# ========================
fig.update_layout(
    height=900,
    barmode='group',
    hovermode="x unified",
    showlegend=True,
    template="plotly_white",
    font=dict(size=11)
)

# Y軸ラベル設定
fig.update_yaxes(title_text="株価（円）", row=1, col=1)
fig.update_yaxes(title_text="信用残（株）", row=2, col=1)
if show_volume:
    fig.update_yaxes(title_text="出来高", row=3, col=1)

st.plotly_chart(fig, use_container_width=True)

# ========================
# 7. 分析指標の表示
# ========================
st.divider()
st.subheader("💡 分析指標")

# 最新データ取得
latest_stock = df_stock.iloc[-1]
latest_margin = df_margin.iloc[-1]

# 指標計算
price_change = ((latest_stock["close"] - df_stock.iloc[0]["close"]) / df_stock.iloc[0]["close"]) * 100
taishaku_ratio = latest_margin["Margin_Buy"] / latest_margin["Margin_Sell"] if latest_margin["Margin_Sell"] > 0 else 0
ma5 = latest_stock.get("MA5", None)
ma20 = latest_stock.get("MA20", None)

# メトリクス表示（2行）
col1, col2, col3, col4 = st.columns(4)
col1.metric("現在株価", f"¥{latest_stock['close']:.0f}", f"{price_change:+.2f}%")
col2.metric("信用買い残", f"{int(latest_margin['Margin_Buy']):,} 株")
col3.metric("信用売り残", f"{int(latest_margin['Margin_Sell']):,} 株")
col4.metric("信用倍率", f"{taishaku_ratio:.2f}倍")

# 詳細情報テーブル
st.subheader("📋 詳細情報")

with st.expander("📊 統計情報を表示"):
    stats_data = {
        "指標": [
            "現在価格",
            "52週高値",
            "52週安値",
            "平均出来高",
            "高値/安値比率",
            "MA5/終値比率",
            "MA20/終値比率",
            "信用買い残 (最新)",
            "信用売り残 (最新)",
            "信用倍率"
        ],
        "値": [
            f"¥{latest_stock['close']:.2f}",
            f"¥{df_stock['high'].max():.2f}",
            f"¥{df_stock['low'].min():.2f}",
            f"{df_stock['volume'].mean():,.0f}",
            f"{df_stock['high'].max() / df_stock['low'].min():.3f}",
            f"{(ma5 / latest_stock['close']):.3f}" if ma5 else "N/A",
            f"{(ma20 / latest_stock['close']):.3f}" if ma20 else "N/A",
            f"{int(latest_margin['Margin_Buy']):,}",
            f"{int(latest_margin['Margin_Sell']):,}",
            f"{taishaku_ratio:.2f}倍"
        ]
    }
    st.dataframe(pd.DataFrame(stats_data), use_container_width=True)

# ========================
# 8. 相場判断ロジック
# ========================
st.subheader("🎯 相場判断")

judgment_col1, judgment_col2 = st.columns(2)

with judgment_col1:
    if taishaku_ratio > 1.5:
        st.success("📈 買い優勢（信用倍率が高い = 買い残が多い）")
    elif taishaku_ratio < 0.5:
        st.info("📉 売り優勢（売り残が多い）")
    else:
        st.warning("⚖️ 均衡状態")

with judgment_col2:
    if ma5 and ma20:
        if ma5 > ma20:
            st.success("✅ 短期トレンド：上昇（MA5 > MA20）")
        else:
            st.error("❌ 短期トレンド：下降（MA5 < MA20）")

# ========================
# 9. データテーブル表示
# ========================
with st.expander("📊 生データを表示"):
    tab1, tab2 = st.tabs(["株価データ", "信用残データ"])
    
    with tab1:
        st.dataframe(df_stock.tail(20), use_container_width=True)
    
    with tab2:
        st.dataframe(df_margin.tail(20), use_container_width=True)

st.divider()
st.caption(f"📅 最終更新: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
