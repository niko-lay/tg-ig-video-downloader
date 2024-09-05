FROM python:3.10

RUN set -x; \
	apt-get -q update && \
	apt-get -qy --no-install-recommends install ffmpeg && \
	apt-get -q clean && \
	rm -rf /var/cache/debconf /var/lib/apt/lists

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip3 install -r /app/requirements.txt

RUN mkdir /app/downloads

COPY bot.py /app/bot.py

VOLUME [ "/app/downloads" ]
CMD [ "/app/bot.py" ]