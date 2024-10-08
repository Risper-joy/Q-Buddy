from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO, emit # for real-time updates
import mysql.connector # used to connect to MySQL database
from mysql.connector import Error
from datetime import datetime
from haversine import haversine
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Necessary for session management
socketio = SocketIO(app)
CORS(app)

# MySQL database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',  # replace with your MySQL username
    'password': '',  # replace with your MySQL password
    'database': 'q-buddy-main'  # replace with your MySQL database name
}

# Hardcoded venue location for location-based queue joining
venue_lat = -1.2640637
venue_lon = 36.9077355

# Office codes for different services
office_codes = {
    'General Consultation': 'GC',
    'Dental': 'DT',
    'Dermatologist': 'DE',
    'Labaratory': 'LA',
    'Emergency Room': 'ER'
}

# Counter for ticket numbers
office_counters = {
    'GC': 1,
    'DT': 1,
    'LA': 1,
    'ER': 1
}

def create_connection():
    """Create a MySQL database connection."""
    try:
        conn = mysql.connector.connect(**db_config)
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"Error: {e}")
    return None

def get_queue_size():
    """Fetch the number of people in the queue."""
    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM queues")
        queue_size = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return queue_size
    return 0
def get_count_from_table(table_name):
    conn = create_connection()  # Assuming create_connection() is already defined
    cursor = conn.cursor()
    
    # Ensure the table name is safely included in the SQL statement
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/handle_button_click', methods=['POST'])
def handle_button_click():
    action = request.form['action']
    if action == 'register':
        return redirect(url_for('register'))
    elif action == 'join_remotely':
        return redirect(url_for('join_remotely'))

@app.route('/register')
def register():
    return render_template('Registration.html')

@app.route('/join_remotely')
def join_remotely():
    return render_template('join_remotely.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', office_codes=office_codes)

@app.route('/submit', methods=['POST'])
def submit():
    if request.method == 'POST':
        name = request.form['name']
        reg_no = request.form['reg-no']
        institution = request.form['institution']
        registration_time = datetime.utcnow()  # Capture the current UTC time

        conn = create_connection()
        if conn is None:
            flash("Database connection failed!", "error")
            return redirect(url_for('register'))

        try:
            cursor = conn.cursor()
            insert_query = """
            INSERT INTO users2 (name, reg_no, institution, registration_time)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(insert_query, (name, reg_no, institution, registration_time))
            conn.commit()

            flash("Registration successful!", "success")
            return redirect(url_for('dashboard'))

        except Error as e:
            flash(f"Error while inserting data: {e}", "error")
            conn.rollback()
            return redirect(url_for('register'))

        finally:
            cursor.close()
            conn.close()

@app.route('/generate_ticket', methods=['POST'])
def generate_ticket():
    office_code = request.form['office_code']
    ticket_number = f"{office_code}{office_counters[office_code]:03d}"  # Format as 3-digit number with leading zeros
    office_counters[office_code] += 1
    
    try:
        conn = create_connection()
        cursor = conn.cursor()
        
        # Fetch the most recent user
        cursor.execute("SELECT id, name FROM users2 ORDER BY id DESC LIMIT 1")
        user = cursor.fetchone()
        
        if user:
            user_id, name = user
            cursor.execute("INSERT INTO queues (user_id, name, ticket_number, processed) VALUES (%s, %s, %s, %s)", 
                           (user_id, name, ticket_number, False))
            conn.commit()

            # Fetch the created_at timestamp of the inserted ticket
            cursor.execute(
                "SELECT created_at FROM queues WHERE ticket_number = %s ORDER BY id DESC LIMIT 1", 
                (ticket_number,)
            )
            created_at = cursor.fetchone()[0]
            created_at = created_at.strftime('%Y-%m-%d %H:%M:%S')

        cursor.close()
        conn.close()
    except Error as e:
        print(f"Error: {e}")
    
    return render_template('tickets.html', ticket_number=ticket_number, created_at=created_at)

# Dynamic queue joining based on user location and queue size
@app.route('/join_queue', methods=['POST'])
def join_queue():
    data = request.json
    user_lat = data['lat']
    user_lon = data['lon']

    # Calculate distance
    distance = haversine((user_lat, user_lon), (venue_lat, venue_lon))

    # Get current queue size and determine the allowed range
    queue_size = get_queue_size()
    allowed_range = queue_size if queue_size <= 20 else 20  # Maximum range is capped at 20km

    if distance <= allowed_range:
        return jsonify({
            "status": "success",
            "message": f"You can join the queue. Allowed range: {allowed_range} km",
            "show_register_button": True  # Add this flag to show the "Register" button
        }), 200
    else:
        # User is outside the allowed range
        return jsonify({
            "status": "failure",
            "message": f"You are too far from the venue. Current allowed range: {allowed_range} km",
            "show_register_button": False
        }), 403

@app.route('/register_staff', methods=['GET', 'POST'])
def register_staff():
    if request.method == 'POST':
        name = request.form['Name']
        office = request.form['office']
        email = request.form['email']
        password = request.form['password']
        agreed_terms = 'iAgree' in request.form

        hashed_password = generate_password_hash(password)  # Hash the password

        conn = create_connection()
        if conn is None:
            flash("Database connection failed!", "error")
            return redirect(url_for('register'))

        try:
            cursor = conn.cursor()

            insert_query = """
            INSERT INTO staff (name, office, email, password, agreed_terms)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (name, office, email, hashed_password, agreed_terms))
            conn.commit()

            flash("Staff registration successful!", "success")
            return redirect(url_for('staff_dashboard'))

        except Error as e:
            flash(f"Error while inserting data: {e}", "error")
            conn.rollback()
            return redirect(url_for('register'))

        finally:
            cursor.close()
            conn.close()

    return render_template('staff-registration.html')

@app.route('/login_staff', methods=['GET', 'POST'])
def login_staff():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = create_connection()
        if conn is None:
            flash("Database connection failed!", "error")
            return redirect(url_for('login_staff'))

        try:
            cursor = conn.cursor()

            # Check if the user exists in the 'staff' table (registered staff)
            cursor.execute("SELECT email, password, office FROM staff WHERE email = %s", (email,))
            staff = cursor.fetchone()

            if staff:
                # User exists, now check if the password matches
                stored_password, staff_office = staff[1], staff[2]  # Fetch hashed password and office
                if check_password_hash(stored_password, password):
                    # Password matches, log the login attempt
                    cursor.execute("""
                    INSERT INTO staff_login (email, login_time)
                    VALUES (%s, NOW())
                    """, (email,))  # Log the login time (don't store password again)
                    conn.commit()

                    # Set the session variables and redirect to dashboard
                    session['email'] = email
                    session['office'] = staff_office  # Store staff office in session
                    flash("Login successful!", "success")
                    return redirect(url_for('staff_dashboard'))

                else:
                    flash("Invalid password. Please try again.", "error")
                    return redirect(url_for('login_staff'))

            else:
                flash("This email is not registered. Please register first.", "error")
                return redirect(url_for('register_staff'))

        except Error as e:
            flash(f"Error: {e}", "error")
            return redirect(url_for('login_staff'))

        finally:
            cursor.close()
            conn.close()

    return render_template('login.html')

@app.route('/staff_dashboard')
def staff_dashboard():
    if 'email' in session:
        email = session['email']
        office = session['office']  # The office of the logged-in staff

        # Query database for tickets based on staff office
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM queues WHERE ticket_number LIKE %s", (office + '%',))
        tickets = cursor.fetchall()

        # Fetch the count for people in queue, served, and skipped
        queue_count = get_count_from_table('queues')  # For the queues table
        served_count = get_count_from_table('served')  # For the served table
        skipped_count = get_count_from_table('skipped')  # For the skipped table

        cursor.close()
        conn.close()

        # Pass the counts and tickets data to the template
        return render_template('staff-dashboard.html', tickets=tickets, queue_count=queue_count, served_count=served_count, skipped_count=skipped_count)
    else:
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for('login_staff'))


    #route to show queues in queue list on staff side
@app.route('/view_queues')
def view_queues():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM queues")
    queues = cursor.fetchall()
    return render_template('queue-list.html', queues=queues)

#where it shows the current and next ticket to be served
@app.route('/queue-screen', methods=['GET', 'POST'])
def queue_screen():
    conn = create_connection()
    cursor = conn.cursor()

    # Fetch the current ticket (the first unprocessed one)
    cursor.execute("SELECT id, ticket_number FROM queues WHERE processed = 0 ORDER BY id LIMIT 1")
    current_ticket = cursor.fetchone()

    # Fetch the next ticket in the queue
    if current_ticket:
        cursor.execute("SELECT ticket_number FROM queues WHERE processed = 0 AND id > %s ORDER BY id LIMIT 1", (current_ticket[0],))
        next_ticket = cursor.fetchone()
    else:
        next_ticket = None

    cursor.close()
    conn.close()

    return render_template('queue-screen.html', current_ticket=current_ticket, next_ticket=next_ticket)

@app.route('/done/<int:ticket_id>', methods=['POST'])
def done(ticket_id):
    conn = create_connection()
    cursor = conn.cursor()

    # Move record from queues to served
    cursor.execute("""
        INSERT INTO served (user_id, name, ticket_number, served_at)
        SELECT user_id, name, ticket_number, NOW()
        FROM queues
        WHERE id = %s
    """, (ticket_id,))

    # Update processed status in queues
    cursor.execute("""
        UPDATE queues
        SET processed = TRUE
        WHERE id = %s
    """, (ticket_id,))

    # Delete the record from queues
    cursor.execute("""
        DELETE FROM queues
        WHERE id = %s
    """, (ticket_id,))


    return redirect(url_for('queue_screen'))

@app.route('/skip/<int:id>', methods=['POST'])
def skip_ticket(id):
    conn = create_connection()
    cursor = conn.cursor()

    # Move the skipped ticket to the skipped table
    cursor.execute("SELECT ticket_number, user_id FROM queues WHERE id = %s", (id,))
    skipped_ticket = cursor.fetchone()

    if skipped_ticket:
        cursor.execute("INSERT INTO skipped (ticket_number, user_id, reason) VALUES (%s, %s, %s)", (skipped_ticket[0], skipped_ticket[1], 'Skipped'))

        # Remove from the queues table
        cursor.execute("DELETE FROM queues WHERE id = %s", (id,))
        conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('queue_screen'))

#code to show skipped records 
@app.route('/skipped')
def skipped_list():
    conn = create_connection()
    cursor = conn.cursor()

    # Fetch all records from the skipped table
    cursor.execute("SELECT id, ticket_number, user_id FROM skipped ORDER BY timestamp DESC")
    skipped_records = cursor.fetchall()

    cursor.close()
    conn.close()

    # Pass the skipped records to the skipped.html template
    return render_template('skipped.html', skipped_records=skipped_records)

@app.route('/transfer_back/<int:id>', methods=['POST'])
def transfer_back(id):
    conn = create_connection()
    cursor = conn.cursor()

    # Fetch the skipped ticket details
    cursor.execute("SELECT ticket_number, user_id FROM skipped WHERE id = %s", (id,))
    skipped_ticket = cursor.fetchone()

    if skipped_ticket:
        # Insert the ticket back into the queue
        cursor.execute("INSERT INTO queues (ticket_number, user_id, processed) VALUES (%s, %s, %s)", 
                       (skipped_ticket[0], skipped_ticket[1], False))

        # Remove the ticket from the skipped table
        cursor.execute("DELETE FROM skipped WHERE id = %s", (id,))
        conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('skipped_list'))

@app.route('/remove_skipped/<int:id>', methods=['POST'])
def remove_skipped(id):
    conn = create_connection()
    cursor = conn.cursor()

    # Remove the ticket from the skipped table
    cursor.execute("DELETE FROM skipped WHERE id = %s", (id,))
    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for('skipped_list'))
#
@app.route('/graphs')
def generate_graphs():
    conn = create_connection()
    cursor = conn.cursor()

    # Fetch data for people who visited (from users2 table)
    cursor.execute("SELECT DAYOFWEEK(registration_time), COUNT(*) FROM users2 GROUP BY DAYOFWEEK(registration_time)")
    visitors_by_day = defaultdict(int, cursor.fetchall())

    # Fetch data for people who were served (from served table)
    cursor.execute("SELECT DAYOFWEEK(served_at), COUNT(*) FROM served GROUP BY DAYOFWEEK(served_at)")
    served_by_day = defaultdict(int, cursor.fetchall())

    # Fetch data for people who were skipped (from skipped table)
    cursor.execute("SELECT DAYOFWEEK(timestamp), COUNT(*) FROM skipped GROUP BY DAYOFWEEK(timestamp)")
    skipped_by_day = defaultdict(int, cursor.fetchall())

    cursor.close()
    conn.close()

    # Create the graphs
    img1, img2, img3 = generate_graph(visitors_by_day, served_by_day, skipped_by_day)

    return render_template('report.html', img1=img1, img2=img2, img3=img3)

def generate_graph(visitors_by_day, served_by_day, skipped_by_day):
    days_of_week = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    # Convert defaultdicts to lists for plotting
    visitors = [visitors_by_day[i] for i in range(1, 8)]
    served = [served_by_day[i] for i in range(1, 8)]
    skipped = [skipped_by_day[i] for i in range(1, 8)]

    # Graph 1: People who visited
    plt.figure()
    plt.bar(days_of_week, visitors)
    plt.title('People who Visited per Day')
    plt.xlabel('Day of the Week')
    plt.ylabel('Count')
    img1 = get_graph()

    # Graph 2: People who were served
    plt.figure()
    plt.bar(days_of_week, served)
    plt.title('People who Were Served per Day')
    plt.xlabel('Day of the Week')
    plt.ylabel('Count')
    img2 = get_graph()

    # Graph 3: People who were skipped
    plt.figure()
    plt.bar(days_of_week, skipped)
    plt.title('People who Were Skipped per Day')
    plt.xlabel('Day of the Week')
    plt.ylabel('Count')
    img3 = get_graph()

    return img1, img2, img3

def get_graph():
    # Convert the plot to a PNG image and encode it to base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    img = base64.b64encode(buffer.getvalue()).decode('utf-8')
    buffer.close()
    plt.close()  # Close the plot to free memory
    return img
# Route for the user to see their ticket and position in the queue
@app.route('/ticket_status/<string:ticket_number>')
def ticket_status(ticket_number):
    try:
        conn = create_connection()
        cursor = conn.cursor()

        # Fetch current ticket data
        cursor.execute("SELECT COUNT(*) FROM queues WHERE ticket_number < %s AND processed = FALSE AND ticket_number LIKE %s", 
                       (ticket_number, ticket_number[:2] + '%'))
        position = cursor.fetchone()[0]

        # Call queue_screen to get the current ticket
        current_ticket = queue_screen()

        cursor.close()
        conn.close()
    except Error as e:
        print(f"Error: {e}")
        position = None
        current_ticket = None

    return render_template('ticket-status.html',ticket_number=ticket_number, current_ticket=current_ticket, position=position)

@socketio.on('request_queue_update')
def handle_queue_update(office_code):
    # Logic to fetch queue status for the office_code
    data = {
        'current_ticket': 'Some ticket data',
        'people_in_queue': 42
    }
    emit('queue_status_update', data)

@socketio.on('request_user_position')
def handle_user_position(data):
    ticket_number = data['ticket_number']
    office_code = data['office_code']
    # Logic to fetch user position
    data = {
        'people_ahead': 5
    }
    emit('user_position_update', data)
    
@socketio.on('connect')
def handle_connect():
    print('Client connected')
if __name__ == '__main__':
    socketio.run(app, debug=True)
