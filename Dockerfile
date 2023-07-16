FROM python:3.8-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY ./src ./src
ENV PYTHONPATH=/app
CMD [ "python", "./src/main.py" ]
