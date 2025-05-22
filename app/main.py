import os
from flask import Flask, request, render_template, jsonify, session, url_for, send_file, redirect
import openai
import fitz  # PyMuPDF, for handling PDF files
from docx import Document  # for handling DOCX files
from waitress import serve
import uuid
import io
import pandas as pd
import html2text
import sqlite3
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from flask_session import Session
from . import create_app

from app.rank_file import ranking

def generate_unique_filename(prefix):
    return f"{prefix}_{uuid.uuid4().hex}.txt"

app = create_app()

# Configure OpenAI API
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route('/')
def index():
    return render_template('home.html')


@app.route('/revisar')
def review():
    return render_template('review.html')


@app.route('/categorizar')
def categorize():
    return render_template('home.html')


@app.route('/ranquear')
def rank():
    return render_template('rank.html')

@app.route('/sobre')
def about():
    return render_template('about.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        text = ""
        if file.filename.lower().endswith('.pdf'):
            file.seek(0)  # Ensure the stream is at the start
            text = optimize_text(extract_text_from_pdf(file))
        elif file.filename.lower().endswith('.docx'):
            file.seek(0)  # Ensure the stream is at the start
            text = optimize_text(extract_text_from_docx(file))
        else:
            return jsonify({"error": "Unsupported file format"}), 400

        session['document_text'] = text  # Store text in session

        # Specific prompt for categorizing the document
        with open('prompts/tap_category.txt', 'r') as file:
            msg = file.read()
        # leia o arquivo txt
       
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": msg},
                      {"role": "user", "content": text}],
            max_tokens=50
        )
        category = response.choices[0].message['content']
        return jsonify({"category": category})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/review', methods=['POST'])
def review_document():
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

        with open('prompts/review.txt', 'r', encoding='latin1') as file:
            review_prompt = file.read()
        # leia o arquivo txt
             
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content":  review_prompt},
                {"role": "user", "content": text_review}
            ],
            #max_tokens=250
        )

        review_summary = response.choices[0].message['content']
        if review_summary.startswith("```html"):
            review_summary = review_summary[7:-3]

        session['review_summary'] = review_summary

        return jsonify({"review_summary": review_summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/download_review', methods=['GET'])
def download_review():

    if 'review_summary' not in session:
        return "No review available", 404

    review_summary_html = session['review_summary']

    # Create a PDF using reportlab
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    def add_header(canvas):
        logo_path = os.path.join(app.static_folder, 'logo_pdf.jpg')
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

    # Initial header and footer
    add_header(c)
    add_footer(c)

    # Add text to the PDF
    styles = getSampleStyleSheet()
    style = styles["Normal"]
    style.alignment = TA_JUSTIFY  # Justify the text
    style.fontName = "Helvetica"
    style.fontSize = 10

    text = review_summary_html.replace('\n', '<br />')  # Convert newlines to HTML line breaks
    paragraph = Paragraph(text, style)
    width, height = letter
    margin = 40

    # Add paragraph to canvas with centering
    paragraph_width, paragraph_height = paragraph.wrap(width - 2 * margin, height)
    paragraph.drawOn(c, margin, height - 140 - 56.7 - paragraph_height)

    c.showPage()
    c.save()

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='revisao.pdf', mimetype='application/pdf')


@app.route('/explain', methods=['POST'])
def explain_category():
    category = request.form['text']

    if 'document_text' not in session:
        return "Document text not available", 404

    # Map categories to their respective images
    category_images = {
        'Servidores': 'public_workers.jpeg',
        'Cidadãos': 'citizens.png',
        'Órgãos e Entidades Públicas': 'government_buildings.jpg'
    }

    explanation_prompt = f"Explique de forma objetiva e direta ao ponto, elencando elementos presentes dentro da TAP, o porque desta categoria ter sido escolhida: {category}. Evite passar de 250 palavras. Retorne a resposta em formato HTML, com as devidas tags."
   
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=[{"role": "system", "content": explanation_prompt},
                  {"role": "user", "content": session['document_text']}],
        #max_tokens=150
    )
    explanation = response.choices[0].message['content']
    if explanation.startswith("```html"):
        explanation = explanation[7:-3]

    image_url = url_for('static', filename=category_images.get(category, 'default_image.jpg'))
    return render_template('explanation.html', explanation=explanation, image_url=image_url)

@app.route('/ranking', methods=['POST'])
def rank_file():
    return ranking()

@app.route('/display_rankings', methods=['GET'])
def display_rankings():
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

    
@app.route('/update_score', methods=['POST'])
def update_score():
    try:
        score = request.form['score']
        description = request.form['description']
        document_name = request.form['document']
        
        print(f"Updating document {document_name} with score {score} and description {description}")  # Log the request data

        conn = sqlite3.connect('document_scores.db')
        c = conn.cursor()
        c.execute("UPDATE document_scores SET score = ?, description = ? WHERE document = ?", (score, description, document_name))
        conn.commit()
        conn.close()

        return jsonify({"success": True})
    except sqlite3.Error as e:
        print(f"Error: {str(e)}") 
        return jsonify({"success": False, "error": str(e)}), 500

    
@app.route('/delete_document', methods=['POST'])
def delete_document():
    try:
        data = request.get_json()
        document_name = data['document']
        
        print(f"Deleting document {document_name}")  

        conn = sqlite3.connect('document_scores.db')
        c = conn.cursor()
        c.execute("DELETE FROM document_scores WHERE document = ?", (document_name,))
        conn.commit()
        conn.close()

        return jsonify({"success": True})
    except sqlite3.Error as e:
        print(f"Error: {str(e)}")  
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/download_rankings')
def download_rankings():
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


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 4567))
    app.run(debug=True, port=port)
    print(f"Server is running on port {port}")
    #serve(app, host='0.0.0.0', port=port)

