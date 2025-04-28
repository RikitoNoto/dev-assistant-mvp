import json
from chatbot import Chatbot
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from planner import PlannerBot
from pydantic import BaseModel
from tech_spec import TechSpecBot

app = FastAPI()


class UserMessage(BaseModel):
    message: str


async def process_stream(bot: Chatbot, message: str):
    """
    Processes the bot stream and yields JSON chunks.
    Detects the separator '===============' to switch keys.
    """
    buffer = ""
    is_file_content = False
    separator = "==============="

    async for chunk in bot.stream(message):
        buffer += chunk

        # Process complete lines or the end of the stream
        while True:
            if is_file_content:
                # If already processing file content, yield everything in buffer
                if buffer:
                    # Ensure newline for ndjson format
                    yield json.dumps({"file": buffer}, ensure_ascii=False) + "\n"
                    buffer = ""
                break # Continue to next chunk

            # Check for separator
            separator_index = buffer.find(separator)
            if separator_index != -1:
                # Yield message part before separator
                message_part = buffer[:separator_index]
                if message_part:
                     # Ensure newline for ndjson format
                    yield json.dumps({"message": message_part}, ensure_ascii=False) + "\n"

                # Update buffer to content after separator
                # Skip the separator itself
                buffer = buffer[separator_index + len(separator):]
                # Handle potential leading newline if separator was \n\n# file\n
                if buffer.startswith('\n'):
                    buffer = buffer[1:]

                is_file_content = True
                # Continue checking the rest of the buffer in the next iteration
            else:
                # No separator found yet. Since we stream chunk by chunk,
                # we yield the current buffer content as message.
                # If a separator exists across chunks, it will be handled
                # when the next chunk arrives and completes the separator pattern.
                if buffer:
                    # Ensure newline for ndjson format
                    yield json.dumps({"message": buffer}, ensure_ascii=False) + "\n"
                    buffer = "" # Clear buffer after yielding
                break # Continue to next chunk

    # Yield any remaining buffer content after the loop finishes
    if buffer:
        key = "file" if is_file_content else "message"
         # Ensure newline for ndjson format
        yield json.dumps({key: buffer}, ensure_ascii=False) + "\n"


@app.post("/chat/plan/stream")
async def chat_plan_stream(user_message: UserMessage):
    """
    Stream chat responses from PlannerBot in JSON format (ndjson).
    Switches key from 'message' to 'file' after '\n\n# file' separator.
    """
    bot = PlannerBot()
    # Use application/x-ndjson for newline delimited JSON
    return StreamingResponse(process_stream(bot, user_message.message), media_type="application/x-ndjson")


@app.post("/chat/tech-spec/stream")
async def chat_tech_spec_stream(user_message: UserMessage):
    """
    Stream chat responses from TechSpecBot in JSON format (ndjson).
    Switches key from 'message' to 'file' after '\n\n# file' separator.
    """
    bot = TechSpecBot()
     # Use application/x-ndjson for newline delimited JSON
    return StreamingResponse(process_stream(bot, user_message.message), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
