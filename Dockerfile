FROM python:3.11-slim

WORKDIR /code

COPY ./app /code/app
COPY ./api /code/api
COPY ./prompts /code/prompts

ENV PYTHONPATH="/code/app:/code/api"

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir flask flask-session openai pymupdf python-docx pandas html2text reportlab waitress openpyxl requests

EXPOSE 4567

CMD ["python", "-m", "app.main"]