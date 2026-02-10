import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions
import time
import os

# ---------------------------------------------------------
# ナレッジベース読み込み関数
# ---------------------------------------------------------
def load_knowledge_base():
    try:
        with open("knowledge_base.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "エラー：knowledge_base.txt が見つかりません。"

# ページ設定
st.set_page_config(page_title="TTV Quality Gatekeeper", page_icon=":shield:", layout="wide")

# タイトル
st.title("TTV Quality Gatekeeper")
st.info("""
TTVの最新危機管理規定に基き動画をチェックします。

※本ツールは過去の事例やナレッジに基づき、リスク要因を抽出・提示する支援ツールです。
最終的な公開可否の判断は必ず人間の目視によって行ってください。
""")

# サイドバー：認証設定
with st.sidebar:
    st.header("認証設定")
    user_password = st.text_input("アクセスキーを入力", type="password")
    
    if user_password != st.secrets["APP_PASSWORD"]:
        st.warning(":warning: 正しいアクセスキーを入力してください")
        st.stop()
    
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    st.success("認証成功")
    
    st.divider()
    
    # 現在のルールを表示
    with st.expander("現在の最新危機管理規定を確認"):
        knowledge_text = load_knowledge_base()
        st.text(knowledge_text)

# メインエリア：ファイルアップロード
uploaded_file = st.file_uploader("チェックする動画ファイル (MP4) をアップロード", type=["mp4", "mov"])

if uploaded_file is not None:
    st.video(uploaded_file)
    
    if st.button("品質チェックを実行する", type="primary"):
        status_text = st.empty()
        progress_bar = st.progress(0)

        try:
            # 1. ルールファイルの読み込み
            current_knowledge = load_knowledge_base()
            
            # 2. 動画の一時保存
            status_text.text("動画を読み込んでいます...")
            progress_bar.progress(10)
            temp_file_path = "temp_video.mp4"
            with open(temp_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # 3. Google AIサーバーへアップロード
            status_text.text("AIエンジンへ転送中...")
            progress_bar.progress(30)
            video_file = genai.upload_file(path=temp_file_path)

            # 4. 処理待ち
            while video_file.state.name == "PROCESSING":
                status_text.text("映像処理中... (数分かかる場合があります)")
                time.sleep(2)
                video_file = genai.get_file(video_file.name)

            if video_file.state.name == "FAILED":
                st.error("動画処理に失敗しました。")
                st.stop()

            # 5. 解析実行（ここからリトライ機能）
            status_text.text("ナレッジベースと照合中...")
            progress_bar.progress(60)
            
            # 診断リストにあった安定版モデルを指定
            model = genai.GenerativeModel(model_name="gemini-flash-latest")
            
            prompt = f"""
            あなたは放送局の厳格な品質管理AIです。
            以下の「ナレッジベース（ルール）」に基づき、アップロードされた動画の映像・テロップを解析してください。
            
            ■前提条件
            - 音声はチェック不要です（無音コンテンツのため）。視覚情報のみで判断してください。
            - ナレッジベースに記載されたルール違反を徹底的に抽出してください。

            ■ナレッジベース
            {current_knowledge}

            ■出力形式
            以下のMarkdownテーブル形式のみで出力してください。
            
            | タイムコード | 判定(NG/注意) | 指摘内容 | 該当ナレッジ |
            | :--- | :--- | :--- | :--- |
            """

            # --- リトライロジック ---
            try:
                response = model.generate_content([video_file, prompt])
            except exceptions.ResourceExhausted:
                # 429エラーが出たらここに来る
                status_text.warning(":warning: アクセス集中(Quota)のため、30秒待機してから再試行します...")
                time.sleep(30) # 30秒待つ
                status_text.text("再試行中...")
                response = model.generate_content([video_file, prompt]) # もう一度トライ
            # ---------------------
            
            # 6. 結果表示
            progress_bar.progress(100)
            status_text.text("完了")
            
            st.divider()
            st.subheader(":bar_chart: 解析レポート")
            st.markdown(response.text)

            # ファイル削除
            genai.delete_file(video_file.name)
            os.remove(temp_file_path)

        except Exception as e:
            st.error(f"システムエラーが発生しました: {e}")
