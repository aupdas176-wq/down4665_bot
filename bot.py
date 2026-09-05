import os
import glob
import logging
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

logging.basicConfig(level=logging.INFO)

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Client(
    "media_downloader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user_links = {}

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    await message.reply_text("হ্যালো! যেকোনো ভিডিও লিঙ্ক পাঠান। অডিও অথবা সর্বোচ্চ 720p ভিডিও ডাউনলোড করতে পারবেন।")

@app.on_message(filters.text & filters.private & ~filters.command(["start"]))
async def handle_link(client: Client, message: Message):
    url = message.text.strip()
    user_links[message.chat.id] = url

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data="type_audio"),
            InlineKeyboardButton("🎬 Video (Max 720p)", callback_data="type_video")
        ]
    ])
    await message.reply_text("কী ফরম্যাটে ডাউনলোড করতে চান বেছে নিন:", reply_markup=keyboard)

@app.on_callback_query()
async def process_download(client: Client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    choice = callback_query.data
    url = user_links.get(chat_id)

    if not url:
        await callback_query.message.edit_text("লিঙ্ক পাওয়া যায়নি। দয়া করে আবার লিঙ্ক পাঠান।")
        return

    status_msg = await callback_query.message.edit_text("ডাউনলোড শুরু হচ্ছে, অপেক্ষা করুন...")

    os.makedirs("downloads", exist_ok=True)
    out_template = f"downloads/{chat_id}_%(id)s.%(ext)s"

    if choice == "type_audio":
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }
    else:
        # পারফেক্ট কী-ফ্রেম এবং সার্বজনীন MP4 ফরম্যাট তৈরি
        ydl_opts = {
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
            'outtmpl': out_template,
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'postprocessor_args': {
                'VideoConvertor': [
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    '-crf', '23',
                    '-g', '60',            # প্রতি ২ সেকেন্ড পর পর কী-ফ্রেম (স্কিপ করার সুবিধা)
                    '-keyint_min', '60',
                    '-sc_threshold', '0',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-movflags', '+faststart'
                ]
            },
            'quiet': True,
        }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id')
            title = info.get('title', 'Media File')
            
            # [ফিক্স ২]: ভিডিওর দৈর্ঘ্য এবং রেজোলিউশন সংরক্ষণ
            duration = int(info.get('duration') or 0)
            width = int(info.get('width') or 0)
            height = int(info.get('height') or 0)

        # ডাউনলোড করা ফাইলটি লোকেট করা
        files = glob.glob(f"downloads/{chat_id}_{video_id}.*")
        if not files:
            await status_msg.edit_text("ফাইল প্রসেস করা যায়নি।")
            return

        file_path = files[0]
        file_size_gb = os.path.getsize(file_path) / (1024 * 1024 * 1024)

        if file_size_gb > 2.0:
            await status_msg.edit_text(f"ফাইলের আকার {file_size_gb:.2f} GB, যা টেলিগ্রামের ২ GB লিমিটের চেয়ে বেশি।")
        else:
            await status_msg.edit_text("টেলিগ্রামে আপলোড করা হচ্ছে...")
            if choice == "type_audio":
                await client.send_audio(
                    chat_id=chat_id,
                    audio=file_path,
                    title=title,
                    caption=title
                )
            else:
                # [ফিক্স ৩]: আপলোডের সময় duration, width ও height পাঠানো
                await client.send_video(
                    chat_id=chat_id,
                    video=file_path,
                    caption=title,
                    duration=duration,
                    width=width,
                    height=height,
                    supports_streaming=True
                )
            await status_msg.delete()

        # সার্ভার স্টোরেজ ক্লিনআপ
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        logging.error(f"Error: {e}")
        await status_msg.edit_text("ডাউনলোড করতে সমস্যা হয়েছে। লিঙ্কটি সঠিক কিনা তা নিশ্চিত করুন।")

if __name__ == "__main__":
    app.run()
