FROM python:3

WORKDIR /src
COPY . .

RUN pip3 install discord

CMD [ "python3", "main.py" ]