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
    
    if st.button("🗑️ チャット履歴を消去"):
        st.session_state.messages = []
        st.rerun()

# ---------------------------------------------------------
# メイン画面
# ---------------------------------------------------------
st.title("🛡️ TTV Quality Gatekeeper")
st.info("""
TTVの最新危機管理規定に基き、動画・画像のチェックおよび規定に関する照会を行います。

※本ツールは過去の事例やナレッジに基づき、リスク要因を抽出・提示する支援ツールです。
最終的な公開可否の判断は必ず人間の目視によって行ってください。
""")

tab1, tab2 = st.tabs(["📁 素材チェック (動画/画像)", "💬 規定照会チャット"])

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
        current_knowledge = load_knowledge_base()
        
        # --- 画像の場合 ---
        if "image" in file_type:
            image = Image.open(uploaded_file)
            st.image(image, caption="アップロードされた画像", use_column_width=True)
            
            if st.button("🚀 画像チェックを実行", type="primary"):
                with st.spinner("画像内の文字と描写を解析中..."):
                    try:
                        model = genai.GenerativeModel(model_name="gemini-flash-latest")
                        
                        # ★ここが重要：解釈を許可するプロンプト
                        prompt = f"""
                        あなたはTTVの厳格な校閲・コンプライアンス担当AIです。
                        以下のナレッジベース（ルールブック）に基づき、画像内の「文字」と「描写」をチェックしてください。

                        ■判定ガイドライン（重要）
                        1. **ルールの適用:** ナレッジベースに記載された禁止事項（例：「差別表現」）については、具体的な記述がなくても、一般的定義に照らして違反（例：「肌の色を揶揄」など）があれば指摘してください。
                        2. **範囲の限定:** ナレッジベースに全くカテゴリが存在しない事項（例：ルールにない「服装のセンス」や「個人的な感想」）については、一切指摘しないでください。

                        ■ナレッジベース
                        {current_knowledge}

                        ■出力
                        違反箇所のみを箇条書きで指摘してください。
                        違反がない場合は必ず「指摘事項なし」とのみ出力してください。
                        """
                        
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
                    status_text.text("AIサーバーへ転送中...")
                    progress_bar.progress(20)
                    temp_file_path = "temp_video.mp4"
                    with open(temp_file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    video_file = genai.upload_file(path=temp_file_path)

                    while video_file.state.name == "PROCESSING":
                        status_text.text("映像処理中... (数分かかる場合があります)")
                        time.sleep(2)
                        video_file = genai.get_file(video_file.name)

                    if video_file.state.name == "FAILED":
                        st.error("動画処理に失敗しました。")
                        st.stop()

                    status_text.text("ナレッジベースと照合中...")
                    progress_bar.progress(60)
                    
                    model = genai.GenerativeModel(model_name="gemini-flash-latest")
                    
                    # ★ここが重要：解釈を許可するプロンプト（動画版）
                    prompt = f"""
                    あなたはTTVの厳格な校閲・コンプライアンス担当AIです。
                    以下のナレッジベース（ルールブック）に基づき動画を解析してください。

                    ■判定ガイドライン（重要）
                    1. **ルールの適用:** ナレッジベースに記載された禁止事項（例：「差別表現」）については、具体的な記述がなくても、一般的定義に照らして違反（例：「肌の色を揶揄」など）があれば指摘してください。
                    2. **範囲の限定:** ナレッジベースに全くカテゴリが存在しない事項（例：ルールにない「服装のセンス」や「個人的な感想」）については、一切無視してください。

                    ■ナレッジベース
                    {current_knowledge}

                    ■出力形式 (Markdownテーブル)
                    違反がない場合は「指摘事項なし」と出力してください。
                    
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
                    
                    st.warning("""
                    **TTVの最新危機管理規定に基き動画をチェックします。**
                    
                    本ツールは過去の事例やナレッジに基づき、リスク要因を抽出・提示する支援ツールです。
                    **最終的な公開可否の判断は必ず人間の目視によって行ってください。**
                    """)

                    genai.delete_file(video_file.name)
                    os.remove(temp_file_path)

                except Exception as e:
                    st.error(f"システムエラー: {e}")

# =========================================================
# タブ2：規定照会チャット
# =========================================================
with tab2:
    st.subheader("💬 規定照会チャット")
    st.caption("現在登録されている「チェックルール（ナレッジベース）」の内容についてのみ回答します。")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("規定について質問を入力してください..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                current_knowledge = load_knowledge_base()
                model = genai.GenerativeModel(model_name="gemini-flash-latest")
                
                # チャット用プロンプトも「適用」と「限定」のバランスを取る
                system_instruction = f"""
                あなたはTTVの「規定照会専用AI」です。
                以下の【ナレッジベース】に記載されている内容のみに基づいて、ユーザーの質問に答えてください。
                
                ■回答ルール
                1. 質問内容がナレッジベースの項目の「具体例」である場合は、ナレッジベースを根拠に回答してください。（例：「肌の色の揶揄はダメ？」→「差別の禁止規定に基づきNGです」）
                2. 質問内容に関連する項目がナレッジベースに全く無い場合は、「規定に記載がありません」と回答してください。
                
                ■ナレッジベース
                {current_knowledge}
                """
                
                chat = model.start_chat(history=[])
                full_prompt = f"{system_instruction}\n\nユーザーの質問: {prompt}"
                
                response = model.generate_content(full_prompt)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                
            except Exception as e:
                st.error(f"エラー: {e}")
