from flask import Flask, request, jsonify, render_template
from haversine import haversine
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Hardcoded venue location
venue_lat =  -1.2640637
venue_lon =  36.9077355

@app.route('/')
def index():
    # Render the index.html file in the templates folder
    return render_template('index.html')

# Route to render the login form
@app.route('/login_form')
def login_form():
    return render_template('login_form.html')

# Route to handle queue joining
@app.route('/join_queue', methods=['POST'])
def join_queue():
    data = request.json
    user_lat = data['lat']
    user_lon = data['lon']

    # Calculate distance
    distance = haversine((user_lat, user_lon), (venue_lat, venue_lon))
    
    if distance <= 20:
        return jsonify({"status": "success", "message": "You can join the queue"}), 200
    else:
        return jsonify({"status": "failure", "message": "You are too far from the venue"}), 403

# Route to process the login form data
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    name = data.get('name')
    registration_number = data.get('registration_number')
    institution = data.get('institution')

    # Here, you can add logic to save this data in a database or process it further.
    if name and registration_number and institution:
        return jsonify({"status": "success", "message": "Login successful!"}), 200
    else:
        return jsonify({"status": "failure", "message": "Please fill in all the fields."}), 400

if __name__ == '__main__':
    app.run(debug=True)
