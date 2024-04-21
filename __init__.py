import os
from flask import Flask, request, render_template, jsonify
import openai

app = Flask(__name__)

# Set the path to the templates directory
app.template_folder = os.path.abspath('templates')

# Configure OpenAI API


# Define a route to render the abada.html template
@app.route('/')
def index():
    return render_template('abada.html')

# Route to process user messages and get bot responses

if __name__ == '__main__':
    app.run(debug=True)
