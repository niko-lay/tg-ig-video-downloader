#!/usr/bin/env python3

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
from yt_dlp import YoutubeDL
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# exeption if no token not provided
tg_bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
download_folder = os.environ.get("DOWNLOAD_FOLDER", "./downloads")

CAPTION_MAX_LEN = 1024
CAPTION_MAX_CROP_TEXT = "\n ...cropped by bot"
TG_BOT_MAX_UPLOAD_SIZE = 50 * 1024 * 1024


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
    urls = [s for s in in_urls if re.search("https://www\.instagram\.com(?:[_0-9a-z./]+)?/reel",s)]
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


async def msg_urls_processor(update: Update, context) -> None:
    urls = extract_urls_from_message(update)
    ig_urls = filter_ig_urs(urls)
    if not ig_urls:
        return

    url_to_process = ig_urls[0]

    await update.message.reply_chat_action(action="typing")

    ydl_opts = {
        "noprogress": True,
        "paths": {"home": download_folder},
        "format": "[protocol!*=dash]",
    }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(url_to_process, download=True)
        except:
            await update.message.reply_text("Download failed")

        await update.message.reply_chat_action(action="upload_video")
        output_filename = ydl.prepare_filename(info_dict)
        video_size = os.path.getsize(output_filename)
        if video_size > TG_BOT_MAX_UPLOAD_SIZE:
            msg = f"Video is too big (~{video_size//(1024*1024)}Mb) to upload, use <a href=\"{info_dict['url']}\">direct link</a> instead"
            msg += "\n___________\nOriginal description:\n"
            msg += info_dict["description"]
            message = await update.message.reply_html(msg)
        else:
            if (
                info_dict["description"]
                and len(info_dict["description"]) >= CAPTION_MAX_LEN
            ):
                msg = (
                    info_dict["description"][
                        : CAPTION_MAX_LEN - len(CAPTION_MAX_CROP_TEXT)
                    ]
                    + CAPTION_MAX_CROP_TEXT
                )
            else:
                msg = info_dict["description"]

            message = await update.message.reply_video(
                output_filename,
                caption=msg,
                write_timeout=600,
                width=info_dict["width"],
                height=info_dict["height"],
                duration=info_dict["duration_string"],
            )

            file_id = message.video.file_id
            print(f"file_id={file_id}")


app = ApplicationBuilder().write_timeout(300).token(tg_bot_token).build()

app.add_handler(
    MessageHandler(
        filters.ChatType.GROUPS
        & (filters.Entity("url") | filters.Entity("text_link"))
        & ~filters.COMMAND,
        msg_urls_processor,
    )
)

app.run_polling()
