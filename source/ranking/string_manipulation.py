import re


def get_project_name(text):
    match = re.search(r"NOME DO PROJETO\s*(.*?)\s*UNIDADE RESPONSÁVEL", text, re.DOTALL)

    if match:
        nome_projeto = match.group(1).strip()
        return nome_projeto
    else:
        return None

