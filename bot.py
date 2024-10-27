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
    filters,
)
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import requests
import logging

# exeption if no token not provided
tg_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]

CAPTION_MAX_LEN = 1024
CAPTION_MAX_CROP_TEXT = "\n ...cropped by bot"
TG_BOT_MAX_UPLOAD_SIZE = 50 * 1024 * 1024
BOT_OWNER_CHAT_ID = os.environ.get("BOT_OWNER_CHAT_ID", None)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def extract_urls_from_message(update: Update) -> list[str]:
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


def filter_ig_urs(in_urls: list[str]) -> list[str]:
    urls = []
    urls = [
        s
        for s in in_urls
        if re.search("https://www\.instagram\.com(?:[_0-9a-z./]+)?/reel", s)
    ]
    urls = [remove_query_param_from_url(url) for url in urls]
    return urls


def remove_query_param_from_url(in_url: str, param_to_remove="igsh") -> str:

    parsed_url = urlparse(in_url)

    query_params = parse_qs(parsed_url.query)

    if param_to_remove in query_params:
        del query_params[param_to_remove]

    new_query_string = urlencode(query_params, doseq=True)

    new_url = urlunparse(
        (
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query_string,
            parsed_url.fragment,
        )
    )

    return new_url


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


async def msg_urls_processor(update: Update, context) -> None:
    urls = extract_urls_from_message(update)
    ig_urls = filter_ig_urs(urls)
    if not ig_urls:
        return

    video_id = get_video_ids_from_url(ig_urls)[0]

    await update.message.reply_chat_action(action="upload_video")
    video_link, video_description = get_video_data_by_video_id(video_id)
    if video_description and len(video_description) >= CAPTION_MAX_LEN:
        msg = (
            video_description[: CAPTION_MAX_LEN - len(CAPTION_MAX_CROP_TEXT)]
            + CAPTION_MAX_CROP_TEXT
        )
    else:
        msg = video_description

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


async def on_new_start(update: Update, context) -> None:
    logger.info(f"new bot startup in: {update}")
    if BOT_OWNER_CHAT_ID:
        await context.bot.send_message(chat_id=BOT_OWNER_CHAT_ID, text=update)


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

    app.run_polling()


if __name__ == "__main__":
    main()
