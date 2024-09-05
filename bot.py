#!/usr/bin/env python3

# https://www.instagram.com/reel/C-zF1hRtyhB/?igsh=Y2ZvcjdpMWI3aTFz

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
import hashlib

tg_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

def generate_md5_hash(value):
    md5 = hashlib.md5()
    md5.update(value.encode('utf-8'))
    return md5.hexdigest()

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

# final_filename = None
# def yt_dlp_monitor(d):
#     print(d)
#     final_filename  = d.get('info_dict').get('_filename')
#     print(final_filename)

async def msg_urls_processor(update: Update, context) -> None:
    urls = extract_urls_from_message(update)
    # print(urls)
    ig_urls = filter_ig_urs(urls)
    print(ig_urls)
    if not ig_urls:
        return
    # print(ig_urls)
    url_to_process = ig_urls[0]
    down_path = f"./downloads/{generate_md5_hash(url_to_process)}"


    download_result = None
    def yt_dlp_monitor(d):
        if d['status'] == 'finished':
            download_result = d

    ydl_opts = {'noprogress': True,
                'outtmpl': down_path,
                "progress_hooks": [yt_dlp_monitor]
                }
    # ydl_opts = {'listformats': True,
    #             'outtmpl': down_path}

    
    with YoutubeDL(ydl_opts) as ydl:
        ret=ydl.download(url_to_process)
        print(download_result)

        if ret == 0:
            await update.message.reply_document(down_path + '.mp4')
        else:
            await update.message.reply_text('Download failed')
        
    
    


app = ApplicationBuilder().token(tg_bot_token).build()

app.add_handler(
    MessageHandler(
        filters.ChatType.GROUPS
        & (filters.Entity("url") | filters.Entity("text_link"))
        & ~filters.COMMAND,
        msg_urls_processor,
    )
)
# app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.ALL, ig_processor))

app.run_polling()
# (MessageEntity(length=65, offset=0, type=<MessageEntityType.URL>),)
