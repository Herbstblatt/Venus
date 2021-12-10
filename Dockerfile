FROM python:3.8

ENV PYTHONPATH=/usr/local/bin

WORKDIR /usr/local/bin/venus

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "-m", "venus", "run" ]