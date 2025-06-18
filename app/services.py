import os
import io
import pandas as pd
import sqlite3
from flask import jsonify, send_file

from docx import Document
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_JUSTIFY

from api.llama_client import call_llama

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

def handle_upload(request, session):
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        text = ""
        if file.filename.lower().endswith('.pdf'):
            file.seek(0)
            text = optimize_text(extract_text_from_pdf(file))
        elif file.filename.lower().endswith('.docx'):
            file.seek(0)
            text = optimize_text(extract_text_from_docx(file))
        else:
            return jsonify({"error": "Unsupported file format"}), 400

        session['document_text'] = text

        with open('prompts/tap_category.txt', 'r') as prompt_file:
            msg = prompt_file.read()

        llama_prompt = f"{msg}\n\n{text}"
        llama_response = call_llama(llama_prompt)
        category = llama_response.get("response", "")

        return jsonify({"category": category})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def handle_review(request, session):
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        text_review = ""
        if file.filename.lower().endswith('.pdf'):
            file.seek(0)
            text_review = extract_text_from_pdf(file)
        elif file.filename.lower().endswith('.docx'):
            file.seek(0)
            text_review = extract_text_from_docx(file)
        else:
            return jsonify({"error": "Unsupported file format"}), 400

        session['document_review'] = text_review

        with open('prompts/review.txt', 'r', encoding='latin1') as prompt_file:
            review_prompt = prompt_file.read()

        llama_prompt = f"{review_prompt}\n\n{text_review}"
        llama_response = call_llama(llama_prompt)
        review_summary = llama_response.get("response", "")
        if review_summary.startswith("```html"):
            review_summary = review_summary[7:-3]

        session['review_summary'] = review_summary

        return jsonify({"review_summary": review_summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def handle_download_review(session):
    if 'review_summary' not in session:
        return "No review available", 404

    review_summary_html = session['review_summary']

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    def add_header(canvas):
        logo_path = os.path.join('static', 'logo_pdf.jpg')
        logo_width = 80
        logo_height = 80
        margin_top = 56.7
        logo_x_position = (width - logo_width) / 2
        canvas.drawImage(logo_path, logo_x_position, height - margin_top - logo_height, width=logo_width, height=logo_height)
        header_text = "Secretaria de Estado da Administração"
        canvas.setFont("Helvetica-Bold", 14)
        header_text_width = canvas.stringWidth(header_text, "Helvetica-Bold", 14)
        header_x_position = (width - header_text_width) / 2
        canvas.drawString(header_x_position, height - margin_top - logo_height - 20, header_text)
        canvas.setFont("Helvetica", 12)

    def add_footer(canvas):
        canvas.setFont("Helvetica", 10)
        canvas.drawString(40, 30, "Página %d" % canvas.getPageNumber())

    add_header(c)
    add_footer(c)

    styles = getSampleStyleSheet()
    style = styles["Normal"]
    style.alignment = TA_JUSTIFY
    style.fontName = "Helvetica"
    style.fontSize = 10

    text = review_summary_html.replace('\n', '<br />')
    paragraph = Paragraph(text, style)
    margin = 40
    paragraph_width, paragraph_height = paragraph.wrap(width - 2 * margin, height)
    paragraph.drawOn(c, margin, height - 140 - 56.7 - paragraph_height)

    c.showPage()
    c.save()

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='revisao.pdf', mimetype='application/pdf')

def handle_explain(request, session, url_for, render_template):
    category = request.form['text']

    if 'document_text' not in session:
        return "Document text not available", 404

    category_images = {
        'Servidores': 'public_workers.jpeg',
        'Cidadãos': 'citizens.png',
        'Órgãos e Entidades Públicas': 'government_buildings.jpg'
    }

    explanation_prompt = (
        f"Explique de forma objetiva e direta ao ponto, elencando elementos presentes dentro da TAP, "
        f"o porque desta categoria ter sido escolhida: {category}. Evite passar de 250 palavras. "
        f"Retorne a resposta em formato HTML, com as devidas tags."
    )

    llama_prompt = f"{explanation_prompt}\n\n{session['document_text']}"
    llama_response = call_llama(llama_prompt)
    explanation = llama_response.get("response", "")
    if explanation.startswith("```html"):
        explanation = explanation[7:-3]

    image_url = url_for('static', filename=category_images.get(category, 'default_image.jpg'))
    return render_template('explanation.html', explanation=explanation, image_url=image_url)

def handle_display_rankings(render_template):
    try:
        conn = sqlite3.connect('document_scores.db')
        c = conn.cursor()
        c.execute("SELECT document, score, description FROM document_scores ORDER BY score DESC")
        rows = c.fetchall()
        conn.close()

        if not rows:
            return render_template('ranking_display.html', documents=[], error="Nenhum documento disponível para exibição.")

        documents = [{'document': row[0], 'score': row[1], 'description': row[2]} for row in rows]

        return render_template('ranking_display.html', documents=documents)
    except sqlite3.Error as e:
        return render_template('ranking_display.html', documents=[], error="Nenhum documento disponível para exibição: " + str(e))

def handle_update_score(request):
    try:
        score = request.form['score']
        description = request.form['description']
        document_name = request.form['document']

        conn = sqlite3.connect('document_scores.db')
        c = conn.cursor()
        c.execute("UPDATE document_scores SET score = ?, description = ? WHERE document = ?", (score, description, document_name))
        conn.commit()
        conn.close()

        return jsonify({"success": True})
    except sqlite3.Error as e:
        return jsonify({"success": False, "error": str(e)}), 500

def handle_delete_document(request):
    try:
        data = request.get_json()
        document_name = data['document']

        conn = sqlite3.connect('document_scores.db')
        c = conn.cursor()
        c.execute("DELETE FROM document_scores WHERE document = ?", (document_name,))
        conn.commit()
        conn.close()

        return jsonify({"success": True})
    except sqlite3.Error as e:
        return jsonify({"success": False, "error": str(e)}), 500

def handle_download_rankings(send_file):
    try:
        conn = sqlite3.connect('document_scores.db')
        c = conn.cursor()
        c.execute("SELECT document, score FROM document_scores ORDER BY score DESC")
        rows = c.fetchall()
        conn.close()

        if not rows:
            return "No data available for download"

        df = pd.DataFrame(rows, columns=['Documento', 'Pontuação'])

        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='openpyxl')
        df.to_excel(writer, index=False, sheet_name='Rankings')
        writer._save()
        output.seek(0)

        return send_file(output, download_name="rankings.xlsx", as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500