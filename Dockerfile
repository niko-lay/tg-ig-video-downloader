FROM python:3.11

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip3 install -r /app/requirements.txt

COPY bot.py /app/bot.py

CMD [ "/app/bot.py" ]
