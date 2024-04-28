import os
from flask import Flask, request, render_template, jsonify
import openai
import fitz  # PyMuPDF, for handling PDF files
from docx import Document  # for handling DOCX files

app = Flask(__name__)
app.template_folder = os.path.abspath('templates')

# Configure OpenAI API
openai.api_key = "abada"

# Define a route to render the HTML template
@app.route('/')
def index():
    return render_template('abada.html')

# Route to handle file uploads and process them
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        text = ""
        if file.filename.endswith('.pdf'):
            file.seek(0)  # Ensure the stream is at the start
            text = optimize_text(extract_text_from_pdf(file))
        elif file.filename.endswith('.docx'):
            file.seek(0)  # Ensure the stream is at the start
            text = optimize_text(extract_text_from_docx(file))
        else:
            return jsonify({"error": "Unsupported file format"}), 400

        msg = """
            Olhando as TAP's (Termo de Abertura de Projeto) que foram enviadas, preciso que você analise os documentos, e, utilizando as informações disponíveis, focando em JUSTIFICATIVA e OBJETIVOS. Categorize-as individualmente com alguma dessas possíveis categorias: Cidadões, Servidores, Orgãos e Entidades publicas.

            Objetivo Operacional - Servidores: Definimos e aplicamos uma metodologia para medição da satisfação dos servidores. KR 1 - Aplicamos a metodologia em 38 órgãos do estado. KR 2 - Obtivemos 90% De respostas ao questionário. KR 3 - Consolidamos os resultados da pesquisa. 
            Ou seja, Iniciativas que visam aprimorar a experiência ou capacidade dos funcionários públicos. 

            Objetivo Operacional - Cidadãos: Avançamos na digitalização dos serviços públicos para transformarmos a qualidade de vida dos cidadãos. KR 1 - Realizamos a estruturação das equipes para inicialização das transformações dos serviços públicos. CANCELADO - KR 2 - Pactuamos um acordo com a SGG para saneamento dos fatores para melhoria dos serviços digitais. KR 3 - Pactuamos um acordo com o DETRAN para saneamento dos fatores para melhoria dos serviços digitais. KR 4 - Implementamos as ações necessárias para melhoria do serviço de emissão da Carteira de Identidade Nacional - CIN. KR 5 - Iniciamos o aumento do percentual de avaliação dos canais digitais. KR 6 - Iniciamos a Execução do plano de transformação. 
            Ou seja, projetos focados em melhorar diretamente a vida dos cidadãos através de serviços ou benefícios. Objetivo 

            Operacional - Órgãos e Entidades Públicas: Concluimos a pesquisa e análise das boas práticas em gestão para criação do modelo de maturidade. KR 1 - Identificamos aspectos que validam uma boa maturidade na área de logística e documental. KR2 - Identificamos os aspectos que validam uma boa maturidade na área de Compras. KR 3 - Identificamos aspectos que validam uma boa maturidade na área de Patrimônio Imobiliário. KR 4 - Identificamos aspectos que validam uma boa maturidade na área de Patrimônio Mobiliário. 
            Ou seja, projetos que buscam melhorar as práticas de gestão e eficiência administrativa em uma escala organizacional mais ampla. Notavelmente melhorias de envolvendo a gestão pública. Difusão de cultura sempre será Órgãos e Entidades Públicas.

            Na primeira linha, retorne apenas a categoria da TAP, nas linhas seguintes, explique a justificativa. 
            """

        # Analyze the text using OpenAI GPT-4 with a specific prompt in chat completions
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo-2024-04-09",
            messages=[{"role": "system", "content": msg},
                      {"role": "user", "content": text}],
            max_tokens = 50
        )
        return jsonify({"response": response.choices[0].message['content']})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def extract_text_from_pdf(file):
    # Read the stream into a bytes object and open the PDF from bytes
    file_content = file.read()
    doc = fitz.open("pdf", file_content)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def extract_text_from_docx(file):
    # Ensure the file stream is at the beginning and load the DOCX file
    doc = Document(file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + '\n'
    return text

def optimize_text(text):

    parts = text.split("14. APROVAÇÕES", 1)
    if len(parts) > 1:
        print(parts[0])
        return parts[0]
    else:
        return text
    
if __name__ == '__main__':
    app.run(debug=True)
