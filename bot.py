import os
import sys
import asyncio
import io
import logging
import types
import time
from pydantic import Field
from pydantic_settings import BaseSettings
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import CommandStart
from pydub import AudioSegment


class Settings(BaseSettings):
    TOKEN: str = Field(validation_alias="TOKEN")
    OPENAI_API_KEY: str = Field(validation_alias="OPENAI_API_KEY")


settings = Settings()
bot = Bot(token=settings.TOKEN)
dp = Dispatcher()
router = Router()
client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY
)


async def save_voice(bot: Bot, voice: types.Voice) -> str:
    voice_file_info = await bot.get_file(voice.file_id)
    voice_ogg = io.BytesIO()
    await bot.download_file(voice_file_info.file_path, voice_ogg)

    voice_mp3_path = f"voice_files/voice-{voice.file_unique_id}.mp3"
    AudioSegment.from_file(voice_ogg, format="ogg").export(
        voice_mp3_path, format="mp3"
    )

    with open(voice_mp3_path, "rb") as audio_file:
        transcript = await client.audio.transcriptions.create(model="whisper-1", file=audio_file, response_format="text")
    os.remove(voice_mp3_path)

    assistant = await client.beta.assistants.create(
        tools=[{"type": "code_interpreter"}],
        model="gpt-4o"
    )
    thread = await client.beta.threads.create()
    message = await client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=transcript
    )
    run = await client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )
    run_status = await client.beta.threads.runs.retrieve(thread_id=thread.id,
                                                   run_id=run.id)
    
    while True:
        run_status = await client.beta.threads.runs.retrieve(thread_id=thread.id, 
                                                       run_id=run.id)
        if run_status.status == "completed":
            break
        elif run_status.status == "failed":
            print("Run failed:", run_status.last_error)
            break
        time.sleep(2)
    
    messages = await client.beta.threads.messages.list(
        thread_id=thread.id
    )

    for message in reversed(messages.data): 
        for content in message.content:
            if content.type == "text":
                text = content.text.value 
                
    speech_file_path = f"voice_files/speech-{voice.file_unique_id}.mp3"
    response = await client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text
    )
    
    response.stream_to_file(speech_file_path)
    speech_ogg_file = f"voice_files/speech-{voice.file_unique_id}.ogg"
    AudioSegment.from_file(speech_file_path, format="mp3").export(
        speech_ogg_file, format="ogg"
    )
    os.remove(speech_file_path)

    return speech_ogg_file


@dp.message(CommandStart())
async def start(message: types.Message) -> None:
    await message.answer("Привет! Это ChatGPT который отвечает на ваши голосовые команды.")


@dp.message(F.content_type == "voice")
async def precess_voice_message(message: types.Message, bot: Bot) -> None:
    voice_path = await save_voice(bot, message.voice)
    if voice_path:
        voice = types.FSInputFile(voice_path)
        await bot.send_voice(message.chat.id, voice)
        os.remove(f"voice_files/speech-{message.voice.file_unique_id}.ogg")


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
