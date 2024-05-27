import os
from flask import Flask, request, render_template, jsonify, session, url_for, redirect
import openai
import fitz  # PyMuPDF, for handling PDF files
from docx import Document  # for handling DOCX files
from waitress import serve
import uuid

def generate_unique_filename(prefix):
    return f"{prefix}_{uuid.uuid4().hex}.txt"

app = Flask(__name__)
app.template_folder = os.path.abspath('templates')
app.secret_key = os.urandom(24)  # Generates a random key, set to a fixed value for production

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
        msg = """
            Olhando as TAP's (Termo de Abertura de Projeto) que foram enviadas, preciso que você analise os documentos, e, utilizando as informações disponíveis, focando em JUSTIFICATIVA e OBJETIVOS. Categorize-as individualmente com alguma dessas possíveis categorias: Cidadões, Servidores, Orgãos e Entidades publicas.

            Objetivo Operacional - Servidores: Definimos e aplicamos uma metodologia para medição da satisfação dos servidores. KR 1 - Aplicamos a metodologia em 38 órgãos do estado. KR 2 - Obtivemos 90% De respostas ao questionário. KR 3 - Consolidamos os resultados da pesquisa. 
            Ou seja, Iniciativas que visam aprimorar a experiência ou capacidade dos funcionários públicos. 

            Objetivo Operacional - Cidadãos: Avançamos na digitalização dos serviços públicos para transformarmos a qualidade de vida dos cidadãos. KR 1 - Realizamos a estruturação das equipes para inicialização das transformações dos serviços públicos. CANCELADO - KR 2 - Pactuamos um acordo com a SGG para saneamento dos fatores para melhoria dos serviços digitais. KR 3 - Pactuamos um acordo com o DETRAN para saneamento dos fatores para melhoria dos serviços digitais. KR 4 - Implementamos as ações necessárias para melhoria do serviço de emissão da Carteira de Identidade Nacional - CIN. KR 5 - Iniciamos o aumento do percentual de avaliação dos canais digitais. KR 6 - Iniciamos a Execução do plano de transformação. 
            Ou seja, projetos focados em melhorar diretamente a vida dos cidadãos através de serviços ou benefícios. Objetivo 

            Operacional - Órgãos e Entidades Públicas: Concluimos a pesquisa e análise das boas práticas em gestão para criação do modelo de maturidade. KR 1 - Identificamos aspectos que validam uma boa maturidade na área de logística e documental. KR2 - Identificamos os aspectos que validam uma boa maturidade na área de Compras. KR 3 - Identificamos aspectos que validam uma boa maturidade na área de Patrimônio Imobiliário. KR 4 - Identificamos aspectos que validam uma boa maturidade na área de Patrimônio Mobiliário. 
            Ou seja, projetos que buscam melhorar as práticas de gestão e eficiência administrativa em uma escala organizacional mais ampla. Notavelmente melhorias de envolvendo a gestão pública. Difusão de cultura sempre será Órgãos e Entidades Públicas.

            Na primeira linha, retorne apenas a categoria da TAP. 
            """
       
        response = openai.ChatCompletion.create(
            model="gpt-4o",
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
            file.seek(0)  # Ensure the stream is at the start
            text_review = extract_text_from_pdf(file)  # Extract text
        elif file.filename.lower().endswith('.docx'):
            file.seek(0)  # Ensure the stream is at the start
            text_review = extract_text_from_docx(file)  # Extract text
        else:
            return jsonify({"error": "Unsupported file format"}), 400

        review_prompt = """
            Revise o documento enviado e retorne APENAS um curto resumo. Caso existam, aponte as devidas correções ortográficas, e caso informações importantes como beneficiário, justificativa e objetivo não estejam claros, recomende alterações. Evite passar de 250 palavras. Retorne a resposta em formato HTML, com as devidas tags.
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": review_prompt},
                {"role": "user", "content": text_review}
            ],
            #max_tokens=300,  # Ensure the response is limited in length
            temperature=0.7  # Adjust temperature if needed
        )

        review_summary = response.choices[0].message['content']

        return jsonify({"review_summary": review_summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route('/explain', methods=['POST'])
def explain_category():
    category = request.form['text']

    if 'document_text' not in session:
        return "Document text not available", 404

    # Map categories to their respective images
    category_images = {
        'Servidores': 'public_workers.jpeg',
        'Cidadãos': 'citizens.png',
        'Órgãos e Entidades Públicas': 'government_buildings.png'
    }

    explanation_prompt = f"Explique de forma objetiva e direta ao ponto, elencando elementos presentes dentro da TAP, o porque desta categoria ter sido escolhida: {category}. Evite passar de 250 palavras. Retorne a resposta em formato HTML, com as devidas tags."
   
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": explanation_prompt},
                  {"role": "user", "content": session['document_text']}],
        #max_tokens=150
    )
    explanation = response.choices[0].message['content']
    if explanation.startswith("```html"):
        explanation = explanation[7:-3]

    image_url = url_for('static', filename=category_images.get(category, 'default_image.jpg'))
    return render_template('explanation.html', explanation=explanation, image_url=image_url)

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
    app.run(debug=True)
    #serve(app, host='0.0.0.0', port=5000)
