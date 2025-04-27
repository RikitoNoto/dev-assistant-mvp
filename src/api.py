from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from planner import PlannerBot
import asyncio

app = FastAPI()


@app.post("/chat/stream")
async def stream_chat(user_message: str):
    """
    Stream chat responses from PlannerBot.
    """
    bot = PlannerBot()

    async def generate_stream():
        async for chunk in bot.stream(user_message):
            yield chunk

    return StreamingResponse(generate_stream(), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
