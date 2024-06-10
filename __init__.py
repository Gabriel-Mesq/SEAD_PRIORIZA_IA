import os
from flask import Flask, request, render_template, jsonify, session, url_for, send_file
import openai
import fitz  # PyMuPDF, for handling PDF files
from docx import Document  # for handling DOCX files
from waitress import serve
import uuid
import io
import html2text
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from flask_session import Session

def generate_unique_filename(prefix):
    return f"{prefix}_{uuid.uuid4().hex}.txt"

app = Flask(__name__)
app.template_folder = os.path.abspath('templates')
app.secret_key = os.urandom(24)  # Generates a random key, set to a fixed value for production

# Configure OpenAI API
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configure Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

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

        review_prompt = """
            Revise o texto enviado, sendo desnecessário resumir o conteúdo. Verifique com atenção informações importantes como beneficiário, justificativa e objetivo, caso estas informações não estejam claras ou estejam incompletas, recomende alterações. Este é um exemplo de como uma TAP deve ser estruturada corretamente, faça a análise com base nesta estrutura:
             
            1. IDENTIFICAÇÃO
            NOME DO PROJETO	[Nome do projeto]
            UNIDADE RESPONSÁVEL	[Nome órgão/entidade/unidade responsável – SIGLA]
GERENTE DO PROJETO	[Nome do gerente do projeto]
2. ALINHAMENTO ESTRATÉGICO
[Ex.: Plano de Governo, Meta GEPI, Plano Estratégico do órgão/entidade, PPA (Produto, Programa, Ação)]
3. PROGRAMA VINCULADO

4. JUSTIFICATIVA
[Por que o projeto deve ser feito? Quais os problemas que existem que justificam a existência do projeto?]
Qual é a motivação para a realização do projeto, por que ele deve ser desenvolvido? A justificativa deve demonstrar uma ação de mudança, onde saímos de uma determinada situação antes da execução do projeto para um novo cenário após sua realização. Um projeto pode ser justificado por diversas razões, mas de forma geral pode-se identificar duas possibilidades, ou é criado para resolver um problema ou para aproveitar/potencializar uma oportunidade.  Neste tópico, elementos como estudos, alinhamento estratégico e/ou político, viabilidade técnica e/ou econômica, contexto de negócio e/ou oportunidade, embasamentos científicos, indicadores, percepção do público-alvo etc. podem ser detalhadas e apresentadas. Em síntese, devem ser apontados os elementos que validam sua execução.
5. ESCOPO DO PROJETO
5.1. OBJETIVOS
[O que será executado/realizado neste projeto? O que se pretende obter com este projeto?]
Escreva os objetivos de uma maneira SMART, ou seja, que possa ser facilmente medido ou identificado.
S.M.A.R.T. (Specific, Measurable, Attainable, Realistic, Time Based)
Específico
Mensurável (tem indicador)
Atingível
Realista
Quando? (tem base de tempo)
5.2. PÚBLICO-ALVO
[Qual o público que será beneficiado ou atingido pelas ações/objetivos do projeto?]
5.3. BENEFÍCIOS ESPERADOS
[São os resultados associados aos objetivos do projeto]
O que vai ser entregue quando o projeto for concluído? Eles podem ser tangíveis ou intangíveis, diretos ou indiretos. Inclusive eles podem ser insumos para outras iniciativas futuras.
5.4. EXCLUSÕES (NÃO ESCOPO)
[O que este projeto não inclui? O que não será feito neste projeto, mas que tange os objetivos?]
As exclusões de um projeto são todos os requisitos que estão explicitamente fora do escopo do projeto. Declarar explicitamente o que está fora do escopo do projeto ajuda no gerenciamento das expectativas das partes interessadas
6. PREMISSAS
[Fatores que são consideradas como verdadeiros, reais ou certos sem prova ou demonstração. Em tese, toda premissa possui um risco associado]
Escreva aqui os fatores ou situações que você irá considerar como certas ou verdadeiras, apenas para fins de planejamento. Exemplo: Para iniciar a obra de reforma do telhado. Consideramos que no centro-oeste não chove no mês de julho. Consideramos a queda sazonal dos preços de materiais de construção.
7. RESTRIÇÕES
[Limites que já são conhecidos, que impactarão no projeto. A exemplo, restrições de prazo, orçamento, pessoas etc.]
8. CRITÉRIOS DE ACEITAÇÃO
[Condições para que as entregas do projeto sejam aceitas]
São aqueles critérios, incluindo requisitos de desempenho e as condições essenciais, que devem ser atendidas antes das entregas do projeto serem aceitas. Eles determinam as circunstâncias específicas sob as quais o resultado do projeto será aceito.
9. RISCOS
[Tudo o que for identificado e que pode impactar diretamente na execução ou andamento do projeto tanto positivamente quanto negativamente para toda de ações caso necessário]
10. CRONOGRAMA DE ENTREGAS MACRO
[Essas entregas macros estão associadas às entregas do projeto. Pode ser utilizado data de início e de fim de cada entrega macro entrega]
Marcos/Entregas	Responsável	Início Previsto	Término Previsto	Custo
				
				
				
				
				
11. CUSTO TOTAL ESTIMADO DO PROJETO

12. IDENTIFICAÇÃO DAS PARTES ENVOLVIDAS NO PROJETO
12.1 PARTES INTERESSADAS
[Pessoas, Órgãos /Entidades, Parceiros que não tenham tarefas no projeto]
12.2 EQUIPE DO PROJETO
[Pessoas que tem atividades/responsabilidades de execução no projeto]
Nome	 Órgão/Unidade
	
	
13. INDICADORES DE RESULTADO
Indicador	 Valor Inicial	 Data Ref. Inicial	 Valor Final	Data Ref. Final
				
				
14. APROVAÇÕES
[Considerando o planejamento aprovado, os responsáveis abaixo assinam e concordam com o conteúdo apresentado neste documento para início da execução do projeto]



[Assinatura do Gerente do Projeto]



[Assinatura do Patrocinador (dirigente do órgão/entidade)]




               
             Além disso, caso existam, aponte as devidas correções ortográficas (Com exceção de nomes proprios). Evite passar de 250 palavras. Caso não hajam erros e tudo esteja claro, basta retornar uma mensagem aprovando a qualidade. Retorne a sua resposta em formato HTML, com as devidas tags.
        """  
             
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

    review_summary = html2text.html2text(review_summary_html)

    # Create a PDF using reportlab
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    def add_header(canvas):
        logo_path = os.path.join(app.static_folder, 'logo_pdf.jpg')
        logo_width = 80
        logo_height = 80
        margin_top = 56.7 
        # Draw the logo centered
        logo_x_position = (width - logo_width) / 2
        canvas.drawImage(logo_path, logo_x_position, height - margin_top - logo_height, width=logo_width, height=logo_height)
        # Draw the header text centered below the logo
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
    indent = 40  # Indentation for each paragraph
    text_y_position = height - 140 - 56.7  # Adjust start position below the header, logo, and margin
    max_lines_per_page = int((height - 160 - 56.7) / 14)  # Adjust this number based on the font size and page dimensions
    line_height = 14  # Adjust line height according to the font size
    line_count = 0
    max_width = width - 80 - indent  # Adjust width to account for indentation

    lines = review_summary.split('\n\n')  # Split the text into paragraphs

    for paragraph in lines:
        # Split the paragraph into lines that fit within the page width
        wrapped_lines = simpleSplit(paragraph, "Helvetica", 12, max_width)

        for i, wrapped_line in enumerate(wrapped_lines):
            if line_count >= max_lines_per_page:
                c.showPage()
                add_footer(c)  # Add footer on each new page
                text_y_position = height - 140 - 56.7  # Reset start position below the header, logo, and margin
                line_count = 0

            if i == 0:  # Indent the first line of each paragraph
                text_object = c.beginText(40 + indent, text_y_position)
            else:
                text_object = c.beginText(40, text_y_position)

            # Check for headers, set the font accordingly, and remove '#' symbols
            if wrapped_line.startswith('###'):
                text_object.setFont("Helvetica", 14)
                wrapped_line = wrapped_line[3:].strip()
            elif wrapped_line.startswith('##'):
                text_object.setFont("Helvetica", 14)
                wrapped_line = wrapped_line[2:].strip()
            elif wrapped_line.startswith('#'):
                text_object.setFont("Helvetica", 14)
                wrapped_line = wrapped_line[1:].strip()
            elif wrapped_line.startswith('* **'):
                text_object.setFont("Helvetica-Bold", 10)
                wrapped_line = wrapped_line[4:].strip()
            else:
                text_object.setFont("Helvetica", 10)

            text_object.textLine(wrapped_line)
            c.drawText(text_object)
            text_y_position -= line_height
            line_count += 1

        # Add an extra line for paragraph separation
        text_y_position -= line_height
        line_count += 1

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
