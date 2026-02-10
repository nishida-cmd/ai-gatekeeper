import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions
from PIL import Image
import time
import os

# ---------------------------------------------------------
# 設定・関数定義
# ---------------------------------------------------------
st.set_page_config(page_title="TTV Quality Gatekeeper", page_icon="🛡️", layout="wide")

def load_knowledge_base():
    try:
        with open("knowledge_base.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "エラー：knowledge_base.txt が見つかりません。"

# ---------------------------------------------------------
# サイドバー：認証 & 設定
# ---------------------------------------------------------
with st.sidebar:
    st.header("認証設定")
    user_password = st.text_input("アクセスキー", type="password")
    if user_password != st.secrets["APP_PASSWORD"]:
        st.warning("⚠️ 正しいキーを入力してください")
        st.stop()
    
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    st.success("認証成功")
    
    st.divider()
    with st.expander("現在のチェックルール"):
        st.text(load_knowledge_base())
    
    # 履歴クリアボタン（チャット用）
    if st.button("🗑️ チャット履歴を消去"):
        st.session_state.messages = []
        st.rerun()

# ---------------------------------------------------------
# メイン画面：タブ切り替え
# ---------------------------------------------------------
st.title("🛡️ TTV Quality Gatekeeper")
st.info("""
TTVの最新危機管理規定に基き、動画・画像のチェックおよびコンプライアンス相談を行います。
※AIの判定は支援情報です。最終判断は必ず人間が行ってください。
""")

# タブの作成
tab1, tab2 = st.tabs(["📁 素材チェック (動画/画像)", "💬 コンプラ相談チャット"])

# =========================================================
# タブ1：素材チェック機能 (動画 & 画像)
# =========================================================
with tab1:
    st.subheader("メディア品質チェック")
    uploaded_file = st.file_uploader(
        "チェックしたいファイル (MP4, MOV, JPG, PNG) をアップロード", 
        type=["mp4", "mov", "jpg", "jpeg", "png", "webp"]
    )

    if uploaded_file is not None:
        file_type = uploaded_file.type
        
        # --- 画像の場合 ---
        if "image" in file_type:
            image = Image.open(uploaded_file)
            st.image(image, caption="アップロードされた画像", use_column_width=True)
            
            if st.button("🚀 画像チェックを実行", type="primary"):
                with st.spinner("画像内の文字と描写を解析中..."):
                    try:
                        current_knowledge = load_knowledge_base()
                        model = genai.GenerativeModel(model_name="gemini-flash-latest")
                        
                        prompt = f"""
                        あなたはTTVの厳格な校閲・コンプライアンス担当AIです。
                        以下のナレッジベースに基づき、画像内の「文字（テロップ）」と「描写」をチェックしてください。

                        ■チェック項目
                        1. 誤字脱字、常用漢字以外の使用（「苺」「綺麗」など）
                        2. 不適切な画像表現、リスクのある映り込み
                        3. その他ナレッジベースへの違反

                        ■ナレッジベース
                        {current_knowledge}

                        ■出力
                        問題点のみを箇条書きで指摘してください。問題なければ「指摘事項なし」としてください。
                        """
                        
                        # 画像解析実行
                        response = model.generate_content([image, prompt])
                        
                        st.success("解析完了")
                        st.markdown("### 📊 画像判定レポート")
                        st.markdown(response.text)
                        
                    except Exception as e:
                        st.error(f"エラーが発生しました: {e}")

        # --- 動画の場合 ---
        elif "video" in file_type:
            st.video(uploaded_file)
            
            if st.button("🚀 動画チェックを実行", type="primary"):
                status_text = st.empty()
                progress_bar = st.progress(0)

                try:
                    current_knowledge = load_knowledge_base()
                    
                    # 保存とアップロード
                    status_text.text("AIサーバーへ転送中...")
                    progress_bar.progress(20)
                    temp_file_path = "temp_video.mp4"
                    with open(temp_file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    video_file = genai.upload_file(path=temp_file_path)

                    # 処理待ち
                    while video_file.state.name == "PROCESSING":
                        status_text.text("映像処理中... (数分かかる場合があります)")
                        time.sleep(2)
                        video_file = genai.get_file(video_file.name)

                    if video_file.state.name == "FAILED":
                        st.error("動画処理に失敗しました。")
                        st.stop()

                    # 解析実行
                    status_text.text("ナレッジベースと照合中...")
                    progress_bar.progress(60)
                    
                    model = genai.GenerativeModel(model_name="gemini-flash-latest")
                    
                    prompt = f"""
                    あなたはTTVの厳格な校閲・コンプライアンス担当AIです。
                    以下のナレッジベースに基づき動画を解析してください。

                    ■ナレッジベース
                    {current_knowledge}

                    ■出力形式 (Markdownテーブル)
                    | タイムコード | 判定(NG/注意) | 指摘内容 | 該当ナレッジ |
                    | :--- | :--- | :--- | :--- |
                    """

                    try:
                        response = model.generate_content([video_file, prompt])
                    except exceptions.ResourceExhausted:
                        status_text.warning("⚠️ アクセス集中。30秒待機して再試行します...")
                        time.sleep(30)
                        status_text.text("再試行中...")
                        response = model.generate_content([video_file, prompt])
                    
                    progress_bar.progress(100)
                    status_text.text("完了")
                    
                    st.divider()
                    st.markdown("### 📊 動画判定レポート")
                    st.markdown(response.text)

                    # 掃除
                    genai.delete_file(video_file.name)
                    os.remove(temp_file_path)

                except Exception as e:
                    st.error(f"システムエラー: {e}")

# =========================================================
# タブ2：コンプラ相談チャット
# =========================================================
with tab2:
    st.subheader("💬 AIコンプライアンス相談室")
    st.caption("「この表現は大丈夫？」「常用漢字か教えて」など、制作中の疑問をAIに相談できます。")

    # チャット履歴の初期化
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 履歴の表示
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ユーザー入力
    if prompt := st.chat_input("質問を入力してください..."):
        # ユーザーのメッセージを表示
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # AIの回答生成
        with st.chat_message("assistant"):
            try:
                current_knowledge = load_knowledge_base()
                model = genai.GenerativeModel(model_name="gemini-flash-latest")
                
                # チャット用プロンプト（ナレッジベースを背景知識として持たせる）
                system_instruction = f"""
                あなたはTTVの放送規定に詳しい「コンプライアンス・アドバイザー」です。
                以下のナレッジベース（規定）を熟知しています。
                ユーザーの質問に対し、この規定に基づいて的確にアドバイスをしてください。
                規定にないことでも、一般的な放送倫理やリスク管理の観点から回答してください。
                
                ■ナレッジベース
                {current_knowledge}
                """
                
                # 会話履歴を含めて送信（文脈維持のため）
                chat = model.start_chat(history=[])
                # ※簡易化のため、毎回システムプロンプト+直近の質問で問い合わせる形式にします
                full_prompt = f"{system_instruction}\n\nユーザーの質問: {prompt}"
                
                response = model.generate_content(full_prompt)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                
            except Exception as e:
                st.error(f"エラー: {e}")
