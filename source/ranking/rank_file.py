from flask import Flask, request, render_template, jsonify, session, url_for, send_file
import openai
import fitz  # PyMuPDF, for handling PDF files
from docx import Document  # for handling DOCX files

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

        session['document_text'] = text_rank  # Store text in session
        
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

        # Save the score and document name in the session
        if 'document_scores' not in session:
            session['document_scores'] = []
        session['document_scores'].append({'document': uploaded_file.filename, 'score': float(score)})

        return jsonify({"score": score})
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
