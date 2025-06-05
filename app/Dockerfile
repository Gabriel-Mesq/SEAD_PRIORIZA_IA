FROM python:3.11-slim

WORKDIR /code

COPY . /code/app

# Instale as dependências
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir flask flask-session openai pymupdf python-docx pandas html2text reportlab waitress openpyxl

EXPOSE 4567

CMD ["python", "-m", "app.main"]