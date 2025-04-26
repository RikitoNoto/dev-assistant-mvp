import chainlit as cl
from planner import PlannerBot  # planner.py から PlannerBot をインポート
from dotenv import load_dotenv
import asyncio

# .envファイルから環境変数を読み込む (PlannerBot内でも読み込まれるが念のため)
load_dotenv()

# グローバルなPlannerBotインスタンス
planner_bot = None


@cl.on_chat_start
async def start_chat():
    """
    チャット開始時の処理。PlannerBotインスタンスを作成します。
    """
    global planner_bot
    try:
        # PlannerBotのインスタンスを作成
        planner_bot = PlannerBot()
        await cl.Message(
            content="こんにちは！プロダクトの企画について、どのようなことを考えましょうか？"
        ).send()
    except ValueError as e:
        # APIキーがない場合などの初期化エラー
        await cl.Message(content=f"ボットの初期化中にエラーが発生しました: {e}").send()
        print(f"Initialization Error: {e}")
    except Exception as e:
        # その他の予期せぬエラー
        await cl.Message(content=f"予期せぬエラーが発生しました: {e}").send()
        print(f"Unexpected Error on start: {e}")


@cl.on_message
async def main(message: cl.Message):
    """
    ユーザーからのメッセージ受信時の処理。
    PlannerBotのチェーンを使用してストリーミング応答を生成します。
    """
    global planner_bot
    if planner_bot is None:
        await cl.Message(
            content="ボットが初期化されていません。チャットを開始し直してください。"
        ).send()
        return

    user_input = message.content
    if not user_input:
        return

    # 新しいメッセージオブジェクトを作成して送信準備
    msg = cl.Message(content="")
    await msg.send()

    # PlannerBotのチェーンから直接ストリームを取得
    async for chunk in planner_bot.stream(user_input):
        # 受け取ったチャンクをメッセージにストリーミング
        await msg.stream_token(chunk)

    # ストリーミング完了後にメッセージを更新 (任意)
    await msg.update()


# Chainlitアプリケーションを実行するためのコマンド: chainlit run app.py -w
