import os
from flask import Flask, request, render_template, jsonify
import openai

app = Flask(__name__)

# Set the path to the templates directory
app.template_folder = os.path.abspath('templates')

# Configure OpenAI API
openai.api_key = ""

# Define a route to render the abada.html template
@app.route('/')
def index():
    return render_template('abada.html')

# Route to process user messages and get bot responses
@app.route('/process_message', methods=['POST'])
def process_message():
    # Get the user's message from the request
    user_message = request.json.get('message')

    # Send the user's message to the GPT-3.5 API
    response = openai.Completion.create(
        engine="text-davinci-002",  # Choose the engine you want to use
        prompt=user_message,
        max_tokens=50  # Adjust as needed
    )

    # Extract the bot's response from the API response
    if response and 'choices' in response.data and len(response.data['choices']) > 0:
        bot_response = response.data['choices'][0]['text']
        return jsonify({"response": bot_response})
    else:
        return jsonify({"response": "Sorry, I couldn't process your message."})

if __name__ == '__main__':
    app.run(debug=True)
