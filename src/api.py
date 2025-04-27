from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from planner import PlannerBot
from pydantic import BaseModel
from tech_spec import TechSpecBot

app = FastAPI()


class UserMessage(BaseModel):
    message: str


@app.post("/chat/plan/stream")
async def chat_plan_stream(user_message: UserMessage):
    """
    Stream chat responses from PlannerBot.
    """
    bot = PlannerBot()

    async def generate_stream():
        async for chunk in bot.stream(user_message.message):
            yield chunk

    return StreamingResponse(generate_stream(), media_type="text/plain")


@app.post("/chat/tech-spec/stream")
async def chat_tech_spec_stream(user_message: UserMessage):
    """
    Stream chat responses from TechSpecBot.
    """
    bot = TechSpecBot()

    async def generate_stream():
        async for chunk in bot.stream(user_message.message):
            yield chunk

    return StreamingResponse(generate_stream(), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
