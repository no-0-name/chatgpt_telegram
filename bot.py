import os
import sys
import asyncio
import io
import logging
import types
from dotenv import load_dotenv
from openai import OpenAI
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import CommandStart
from pydub import AudioSegment


load_dotenv()
TOKEN = os.getenv('TOKEN')
OPENAI_API_KEY = os.getenv('OPENAIP_API_KEY')

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
client = OpenAI(
    api_key=OPENAI_API_KEY
)


def audio_to_text(audio_file_path: str) -> str:
    with open(audio_file_path, 'rb') as audio_file:
        transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file, response_format="text")
    
    text = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": transcript},
        ]
    )

    speech_file_path = "voice_files/speech.mp3"
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text.choices[0].message.content
    )
    
    response.stream_to_file(speech_file_path)
    speech_ogg_file = "voice_files/speech.ogg"
    AudioSegment.from_file(speech_file_path, format="mp3").export(
        speech_ogg_file, format="ogg"
    )

    return speech_file_path


async def save_voice(bot: Bot, voice: types.Voice) -> str:
    voice_file_info = await bot.get_file(voice.file_id)
    voice_ogg = io.BytesIO()
    await bot.download_file(voice_file_info.file_path, voice_ogg)

    voice_mp3_path = f"voice_files/voice.mp3"
    AudioSegment.from_file(voice_ogg, format="ogg").export(
        voice_mp3_path, format="mp3"
    )
    return voice_mp3_path


@dp.message(CommandStart())
async def start(message: types.Message) -> None:
    await message.answer('Привет! Это ChatGPT который отвечает на ваши голосовые команды.')


@dp.message(F.content_type == 'voice')
async def precess_voice_message(message: types.Message, bot: Bot) -> None:
    voice_path = await save_voice(bot, message.voice)
    transcripted_voice_text = audio_to_text(voice_path)

    if transcripted_voice_text:
        voice = types.FSInputFile(transcripted_voice_text)
        await bot.send_voice(message.chat.id, voice)


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())

    