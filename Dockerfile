# Usar imagem oficial do Python
FROM python:3.13-slim

# Definir diretório de trabalho
WORKDIR /api

# Copiar arquivos
COPY ./api /api
COPY requirements.txt .

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# Expor porta
EXPOSE 8000

# Comando para rodar a API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]