import streamlit as st
import google.generativeai as genai

st.title("🔧 AIモデル接続診断")

# 1. APIキーの読み込み確認
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    st.success("✅ APIキーは正常に読み込まれています")
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"❌ APIキーの設定エラー: {e}")
    st.stop()

# 2. 利用可能なモデル一覧を取得
st.write("Googleサーバーに問い合わせ中...")

try:
    models = genai.list_models()
    available_models = []
    
    st.markdown("### 📋 あなたの環境で使えるモデル一覧")
    for m in models:
        # 動画やテキスト生成ができるモデルだけを表示
        if 'generateContent' in m.supported_generation_methods:
            st.code(f"モデル名: {m.name}")
            available_models.append(m.name)
            
    if not available_models:
        st.error("⚠️ 利用可能なモデルが1つも見つかりませんでした。APIキーの権限を確認してください。")
    else:
        st.success(f"🎉 {len(available_models)} 個のモデルが見つかりました！")
        st.info("上記リストの中にある `models/gemini-1.5-flash-001` などの名前をメモしてください。")

except Exception as e:
    st.error(f"❌ サーバー通信エラー: {e}")
