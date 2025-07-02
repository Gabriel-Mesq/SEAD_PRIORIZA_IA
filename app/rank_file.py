from cv2 import log
from flask import Flask, request, render_template, jsonify, url_for, send_file
import fitz  # PyMuPDF, for handling PDF files
from docx import Document  # for handling DOCX files
import sqlite3

from app.string_manipulation import get_project_name
from api.llama_client import call_llama  # ADICIONE ESTA LINHA

def ranking():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    uploaded_file = request.files['file']
    if uploaded_file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        text_rank = ""
        if uploaded_file.filename.lower().endswith('.pdf'):
            uploaded_file.seek(0)  # Ensure the stream is at the start
            text_rank = optimize_text(extract_text_from_pdf(uploaded_file))
        elif uploaded_file.filename.lower().endswith('.docx'):
            uploaded_file.seek(0)  # Ensure the stream is at the start
            text_rank = optimize_text(extract_text_from_docx(uploaded_file))
        else:
            return jsonify({"error": "Unsupported file format"}), 400
        
        with open('prompts/ranking.txt', 'r', encoding='utf-8') as prompt_file:
            msg = prompt_file.read()

        print(f"Texto otimizado: {text_rank}")

        # CHAMADA AO LLAMA PARA RANKING
        llama_response = call_llama(f"{msg}\n{text_rank}")
        if "error" in llama_response:
            return jsonify({"error": llama_response["message"]}), 500
        score_text = llama_response["response"]

        # CHAMADA AO LLAMA PARA EXTRAIR SÓ O SCORE
        score_extraction = call_llama("Extraia a pontuação geral deste documento. Retorne apenas o numero da pontuação.\n" + score_text)
        if "error" in score_extraction:
            return jsonify({"error": score_extraction["message"]}), 500
        score = score_extraction["response"].strip()

        # CHAMADA AO LLAMA PARA GERAR DESCRIÇÃO
        description_generation = call_llama(f"Leia o texto abaixo e gere uma descrição concisa e breve.\n{text_rank}")
        if "error" in description_generation:
            return jsonify({"error": description_generation["message"]}), 500
        description = description_generation["response"].strip()

        # Banco de dados
        conn = sqlite3.connect('document_scores.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS document_scores
                     (id INTEGER PRIMARY KEY, document TEXT, score REAL, description TEXT, user_score REAL DEFAULT 0)''')
        
        project_name = get_project_name(text_rank) if get_project_name != None else uploaded_file.filename 

        c.execute("INSERT INTO document_scores (document, score, description, user_score) VALUES (?, ?, ?, ?)",
                  (project_name, float(score), description, 0))
        conn.commit()
        conn.close()

        return jsonify({"score": score, "description": description})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def extract_text_from_pdf(file):
    file_content = file.read()
    doc = fitz.open("pdf", file_content)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text


def extract_text_from_docx(file):
    doc = Document(file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + '\n'
    return text

def optimize_text(text):
    parts = text.split("14. APROVAÇÕES", 1)
    if len(parts) > 1:
        return parts[0]
    else:
        return text
