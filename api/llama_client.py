import requests
import os
import time

# Cache simples em memória
_token_cache = {
    "token": None,
    "expires_at": 0
}

def get_token():
    """
    Obtém o token da API do governo usando Basic Auth, com cache.
    """
    global _token_cache
    now = time.time()

    # Se ainda é válido, retorna
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    url = "https://api.go.gov.br/token"
    headers = {
        "Authorization": f"Basic {os.getenv('BASIC_AUTH')}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials"
    }
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        token_data = response.json()
        token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)  # fallback para 1 hora

        # Atualiza o cache
        _token_cache = {
            "token": token,
            "expires_at": now + expires_in - 60  # margem de segurança de 1 min
        }
        return token
    else:
        raise Exception(f"Erro ao obter token: {response.status_code} - {response.text}")

def call_llama(prompt: str):
    """
    Chama a API do Llama usando o token obtido.
    """
    token = get_token()
    url = "https://api.go.gov.br/ia/modelos-linguagem-natural/v2.0/generate"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3.2:3b",
        "prompt": prompt,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9
        }
    }
    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 200:
        return {"response": response.text} 
    else:
        return {"error": response.status_code, "message": response.text}
