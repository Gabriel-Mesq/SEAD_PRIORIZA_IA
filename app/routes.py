from flask import Blueprint, render_template, request, jsonify, session, url_for, send_file
from .services import (
    extract_text_from_pdf, extract_text_from_docx, optimize_text,
    handle_upload, handle_review, handle_explain, handle_download_review,
    handle_display_rankings, handle_update_score, handle_delete_document,
    handle_download_rankings
)
from .rank_file import ranking  # Adicione esta linha

routes = Blueprint('routes', __name__)

@routes.route('/')
def index():
    return render_template('home.html')

@routes.route('/revisar')
def review():
    return render_template('review.html')

@routes.route('/categorizar')
def categorize():
    return render_template('home.html')

@routes.route('/ranquear')
def rank():
    return render_template('rank.html')

@routes.route('/sobre')
def about():
    return render_template('about.html')

@routes.route('/upload', methods=['POST'])
def upload_file():
    return handle_upload(request, session)

@routes.route('/review', methods=['POST'])
def review_document():
    return handle_review(request, session)

@routes.route('/download_review', methods=['GET'])
def download_review():
    return handle_download_review(session)

@routes.route('/explain', methods=['POST'])
def explain_category():
    return handle_explain(request, session, url_for, render_template)

@routes.route('/display_rankings', methods=['GET'])
def display_rankings():
    return handle_display_rankings(render_template)

@routes.route('/update_score', methods=['POST'])
def update_score():
    return handle_update_score(request)

@routes.route('/delete_document', methods=['POST'])
def delete_document():
    return handle_delete_document(request)

@routes.route('/download_rankings')
def download_rankings():
    return handle_download_rankings(send_file)

@routes.route('/ranking', methods=['POST'])  # Adicione esta rota
def ranking_route():
    return ranking()