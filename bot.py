#!/usr/bin/env python3

import json
import os
import re
from telegram import Update, MessageEntity
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ChatMemberHandler,
    filters,
)
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import requests
import logging
import tempfile

# exeption if no token not provided
tg_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]

CAPTION_MAX_LEN = 1024
CAPTION_MAX_CROP_TEXT = "\n ...cropped by bot"
TG_BOT_MAX_UPLOAD_SIZE = 50 * 1024 * 1024
TG_BOT_MAX_DOWNLOAD_BY_URL_ZISE = 20 * 1024 * 1024
BOT_OWNER_CHAT_ID = os.environ.get("BOT_OWNER_CHAT_ID", None)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def extract_urls_from_message(update: Update) -> list[str]:
    """ Extract IG urls from message """
    urls = []
    if update.message and update.message.entities:
        for entity in update.message.entities:
            if (
                entity.type == MessageEntity.URL
                or entity.type == MessageEntity.TEXT_LINK
            ):
                if entity.type == MessageEntity.URL:
                    url = update.message.text[
                        entity.offset : entity.offset + entity.length
                    ]
                elif entity.type == MessageEntity.TEXT_LINK:
                    url = entity.url
                urls.append(url)
    return urls

def unsort_urls(in_irls: list[str]) -> list[str]:
    """ get actual link to IG post, reels or image
        https://www.instagram.com/share/XXYYZZ => https://www.instagram.com/reel/AABBCC/
    """
    session = requests.Session()
    return [session.head(u, allow_redirects=True).url for u in in_irls]


def filter_ig_urs(in_urls: list[str]) -> list[str]:
    return [u for u in in_urls if u.startswith(('https://www.instagram.com', 'https://instagram.com'))]

def get_video_ids_from_url(in_urls: list[str]) -> list[str]:
    video_id_str = "https:\/\/www\.instagram\.com(?:[_0-9a-z.\/]+)?\/reel\/(.+)\/"
    video_ids = []
    for url in in_urls:
        match = re.findall(video_id_str, url)
        if len(match):
            video_ids.append(match[0])
    return video_ids


def get_video_data_by_video_id(video_id: str) -> str:
    ig_query_url = "https://www.instagram.com/graphql/query"

    variable = {"shortcode": video_id}
    payload = {
        "variables": json.dumps(variable),
        "doc_id": "8845758582119845",
    }

    response = requests.post(ig_query_url, data=payload)
    response_json = response.json()

    video_url = response_json.get("data").get("xdt_shortcode_media").get("video_url")
    try:
        video_description = response_json["data"]["xdt_shortcode_media"][
            "edge_media_to_caption"
        ]["edges"][0]["node"]["text"]
    except:
        video_description = ""

    video_duration = (
        response_json.get("data").get("xdt_shortcode_media").get("video_duration")
    )

    return video_url, video_description


def get_file_size(url: str) -> int:
    response = requests.head(url)
    size_in_bytes = response.headers.get("content-length")
    return int(size_in_bytes)


def download_file_to_temp(url: str):
    """
    Downloads a file from a given URL and saves it to a temporary folder.

    Parameters:
        url (str): The URL of the file to download.

    Returns:
        str: The path to the downloaded file in the temporary directory.
    """
    try:
        # Send a GET request to the URL
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an error for bad status codes

        temp_file_path = tempfile.mktemp(prefix="igg_video_downloader_", suffix=".mp4")

        # Write the content to the temporary file
        with open(temp_file_path, "wb") as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)

        return temp_file_path

    except requests.exceptions.RequestException as e:
        logger.warning(f"Error downloading file: {e}")
        return None


def clip_msg(in_msg: str) -> str:
    if in_msg and len(in_msg) >= CAPTION_MAX_LEN:
        msg = (
            in_msg[: CAPTION_MAX_LEN - len(CAPTION_MAX_CROP_TEXT)]
            + CAPTION_MAX_CROP_TEXT
        )
    else:
        msg = in_msg

    return msg


async def msg_urls_processor(update: Update, context) -> None:
    urls = extract_urls_from_message(update)
    ig_urls = filter_ig_urs(urls)
    ig_urls = unsort_urls(ig_urls)
    if not ig_urls:
        return

    video_id = get_video_ids_from_url(ig_urls)[0]

    await update.message.reply_chat_action(action="upload_video")
    video_link, video_description = get_video_data_by_video_id(video_id)
    msg = clip_msg(video_description)

    size_in_bytes = get_file_size(video_link)

    if size_in_bytes >= TG_BOT_MAX_UPLOAD_SIZE:
        logger.info(
            f"File is too big ({size_in_bytes} bytes) to be uploaded to TG ({TG_BOT_MAX_UPLOAD_SIZE}) use direct link to view it"
        )
        too_big_msg = f"""Video is too big to upload it via bot, please use <a href="{video_link}">direct link</a>. _____ Original post description: {video_description}"""
        msg = clip_msg(too_big_msg)
        message = await update.message.reply_text(msg)

    elif size_in_bytes >= TG_BOT_MAX_DOWNLOAD_BY_URL_ZISE:
        logger.info(
            f"File is too big ({size_in_bytes} bytes) to be dowloaded by TG ({TG_BOT_MAX_DOWNLOAD_BY_URL_ZISE}), downloading it on my own..."
        )
        downloded_file = download_file_to_temp(video_link)
        try:
            message = await update.message.reply_video(downloded_file, caption=msg)
        finally:
            os.remove(downloded_file)
    else:
        message = await update.message.reply_video(video_link, caption=msg)

    file_id = message.video.file_id
    logger.info(
        msg=f"""File was uploaded to TG with file_id: {file_id}. Chat: "{message.chat.title}" with id: {message.chat.id}"""
    )


async def post_init(app) -> None:
    me = await app.bot.getMe()
    logger.info(
        msg=f"Bot @{me.username} started sucssesfully. Bot name: {me.first_name}"
    )


async def send_message_to_owner(msg: str, context):
    if BOT_OWNER_CHAT_ID:
        await context.bot.send_message(chat_id=BOT_OWNER_CHAT_ID, text=msg)


async def on_new_start(update: Update, context) -> None:
    logger.info(f"new bot startup in: {update}")
    await send_message_to_owner(update, context)


async def new_group_added(update: Update, context) -> None:
    # double check if it was bot
    if update.my_chat_member.new_chat_member.user.id == context.bot.id:
        logger.info(f"bot was added to the gruop: {update}")
        await send_message_to_owner(update, context)


def main() -> None:
    """Run the bot."""

    app = ApplicationBuilder().token(tg_bot_token).post_init(post_init).build()

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & (filters.Entity("url") | filters.Entity("text_link"))
            & ~filters.COMMAND,
            msg_urls_processor,
        )
    )
    app.add_handler(CommandHandler("start", on_new_start))
    app.add_handler(
        ChatMemberHandler(new_group_added, ChatMemberHandler.MY_CHAT_MEMBER)
    )

    app.run_polling()


if __name__ == "__main__":
    main()
