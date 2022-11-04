FROM python:3.10-slim

WORKDIR /usr/local/bin/venus

RUN pip install "pipenv<2022.11.4"
RUN apt-get update && apt-get install -y git

COPY Pipfile .
COPY Pipfile.lock .
RUN pipenv install --ignore-pipfile

COPY . .

ENV PYTHONPATH=/usr/local/bin

CMD [ "pipenv", "run", "start" ]