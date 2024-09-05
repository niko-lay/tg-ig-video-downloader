#!/usr/bin/env python3

import os
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
download_folder = os.environ.get("DOWNLOAD_FOLDER", './downloads')

def extract_urls_from_message(update: Update):
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


def filter_ig_urs(in_urls):
    urls = []
    urls = [s for s in in_urls if s.startswith("https://www.instagram.com/reel")]
    urls = [remove_query_param_from_url(url) for url in urls]
    return urls


def remove_query_param_from_url(in_url, param_to_remove="igsh"):

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

    ydl_opts = {'noprogress': True,
                'paths': {'home': download_folder}
                }

    with YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(url_to_process, download=True)
        except:
            await update.message.reply_text('Download failed')
            
        output_filename = ydl.prepare_filename(info_dict)
        
        message = await update.message.reply_video(output_filename, caption=info_dict['description'], protect_content=True)
        file_id = message.video.file_id
        print(file_id)
            
        
    
app = ApplicationBuilder().write_timeout(180).token(tg_bot_token).build()

app.add_handler(
    MessageHandler(
        filters.ChatType.GROUPS
        & (filters.Entity("url") | filters.Entity("text_link"))
        & ~filters.COMMAND,
        msg_urls_processor,
    )
)

app.run_polling()
