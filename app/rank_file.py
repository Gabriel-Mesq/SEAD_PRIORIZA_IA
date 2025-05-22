from flask import Flask, request, render_template, jsonify, url_for, send_file
import openai
import fitz  # PyMuPDF, for handling PDF files
from docx import Document  # for handling DOCX files
import sqlite3

from app.string_manipulation import get_project_name
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

        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": msg},
                      {"role": "user", "content": text_rank}],
        )
        score_text = response.choices[0].message['content']
        
        print(score_text)
        
        score_extraction_response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Extraia a pontuação geral deste documento. Retorne apenas o numero da pontuação."},
                      {"role": "user", "content": score_text}],
        )
        score = score_extraction_response.choices[0].message['content'].strip()

        description_generation_response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Leia o documento e gere uma descrição concisa e breve."},
                      {"role": "user", "content": text_rank}],
        )
        description = description_generation_response.choices[0].message['content'].strip()

        # Generate SQL file and insert the document name, score, and description with user_score defaulting to 0
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
