from flask import Flask, render_template, request, redirect, url_for, session  # Add session to the imports
from database import connect_db
import schedule
import time
from threading import Thread


app = Flask(__name__)

# secret key for session management 
app.secret_key = 'my_secret_key'  


# Email Configuration
import smtplib
from email.mime.text import MIMEText

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_EMAIL = 'aaron.burds@csuglobal.edu'
SENDER_PASSWORD = 'qghd lvoe sbhn nsgs'

def send_email(to_email, subject, message):
    try:
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email

        # Connect to the email server
        print(f"Attempting to send email to {to_email}...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # Secure the connection
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()

        print(f"Email sent to {to_email}!")
    except Exception as e:
        print(f"Failed to send email: {e}")



from datetime import timedelta

def send_task_reminders():
    connection = connect_db()
    cursor = connection.cursor(dictionary=True)

    # Get the current date and tasks due in the next 24 hours
    current_time = datetime.now()
    reminder_time = current_time + timedelta(days=1)
    
    # Query tasks that are due within the next 24 hours and are still pending
    query = """
        SELECT tasks.title, tasks.description, tasks.deadline, users.email
        FROM tasks
        JOIN users ON tasks.assigned_to = users.username
        WHERE tasks.deadline BETWEEN %s AND %s AND tasks.status = 'Pending'
    """
    cursor.execute(query, (current_time, reminder_time))
    tasks = cursor.fetchall()

    cursor.close()
    connection.close()

    for task in tasks:
        # Send reminder email
        email_subject = f"Reminder: Task '{task['title']}' is due soon"
        email_message = f"Hello, your task '{task['title']}' is due by {task['deadline']}. Please make sure to complete it."
        send_email(task['email'], email_subject, email_message)
        print(f"Reminder email sent to {task['email']} for task '{task['title']}'")



def job():
    send_task_reminders()  # Trigger the reminder function
    print("Task reminders sent!")

def run_scheduler():
    schedule.every().day.at("09:00").do(job)  # Scheduled to run daily at 9 AM
    while True:
        schedule.run_pending()  # Check if a scheduled task is ready to run
        time.sleep(1)  # Wait a second between checks




@app.route('/send-task-reminders')
def send_task_reminders_route():
    if 'user_id' in session and session['role'] == 'Manager':
        send_task_reminders()  # Trigger the reminders manually
        flash("Task reminder emails have been sent!", "success")
        return redirect(url_for('home'))
    else:
        return "Access denied. Only Managers can trigger task reminders.", 403





@app.route('/')
def home():
    if 'user_id' in session:
        if session['role'] == 'Manager':
            # Render the 'home.html' template for managers
            return render_template('home.html', username=session['username'], role=session['role'])
        elif session['role'] == 'Employee':
            # Keep the same inline HTML for employees
            return f"Welcome {session['username']}! You are an Employee." + "<br><a href='/view-tasks'>View Tasks</a><br><a href='/logout'>Logout</a>"
    
    # For users not logged in
    return "Welcome to the Employee Task Management System!" + "<br><a href='/login'>Login</a>"






@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get form data
        username = request.form['username']
        password = request.form['password']

        # Connect to database
        connection = connect_db()
        cursor = connection.cursor(dictionary=True)

        # Query the database for the user
        query = "SELECT * FROM users WHERE username = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']

            # Redirect to different pages based on role
            if user['role'] == 'Manager':
                return redirect(url_for('home'))  # Manager home route
            elif user['role'] == 'Employee':
                return redirect(url_for('employee_home'))  # Employee home route
        else:
            return "Invalid username or password."

    return render_template('login.html')



# Add the logout route here
@app.route('/logout')
def logout():
    # Clear the session
    session.clear()
    return redirect(url_for('login'))



from datetime import datetime

@app.route('/create-task', methods=['GET', 'POST'])
def create_task():
    if 'user_id' in session and session['role'] == 'Manager':
        if request.method == 'POST':
            task_title = request.form['title']
            task_description = request.form['description']
            assigned_to = request.form['assigned_to']
            deadline = request.form['deadline']

            # Convert deadline to date object
            deadline_date = datetime.strptime(deadline, '%Y-%m-%d').date()

            # Check if the deadline is in the past
            if deadline_date < datetime.today().date():
                flash("Deadline cannot be in the past.", "error")
                return render_template('create_task.html')

            # Check if the assigned employee exists
            connection = connect_db()
            cursor = connection.cursor(dictionary=True)
            query = "SELECT * FROM users WHERE username = %s AND role = 'Employee'"
            cursor.execute(query, (assigned_to,))
            employee = cursor.fetchone()

            if not employee:
                flash("Assigned employee does not exist.", "error")
                cursor.close()
                connection.close()
                return render_template('create_task.html')

            # Insert the task if validation passes
            query = "INSERT INTO tasks (title, description, assigned_to, deadline) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (task_title, task_description, assigned_to, deadline))
            connection.commit()

            # Send email notification to the assigned employee
            employee_email = employee['email']
            email_subject = "New Task Assigned"
            email_message = f"Hello, a new task '{task_title}' has been assigned to you with a deadline on {deadline}."
            send_email(employee_email, email_subject, email_message)

            cursor.close()
            connection.close()

            flash("Task created successfully!", "success")
            return redirect(url_for('home'))

        return render_template('create_task.html')
    else:
        return "Access denied. Only Managers can create tasks.", 403





from datetime import date

@app.route('/view-tasks')
def view_tasks():
    # Ensure only employees can access this route
    if 'user_id' in session and session['role'] == 'Employee':
        # Get the filter and sort parameters from the query string (default to 'all' and 'created_at')
        task_filter = request.args.get('filter', 'all')
        sort_by = request.args.get('sort', 'created_at')

        # Connect to the database
        connection = connect_db()
        cursor = connection.cursor(dictionary=True)

        # SQL query to fetch tasks based on the filter
        if task_filter == 'pending':
            query = "SELECT * FROM tasks WHERE assigned_to = %s AND status = 'Pending'"
        elif task_filter == 'completed':
            query = "SELECT * FROM tasks WHERE assigned_to = %s AND status = 'Completed'"
        else:
            query = "SELECT * FROM tasks WHERE assigned_to = %s"

        # Sorting logic
        if sort_by == 'deadline':
            query += " ORDER BY deadline"
        elif sort_by == 'status':
            query += " ORDER BY status"
        elif sort_by == 'created_at':
            query += " ORDER BY created_at"  # Make sure this column exists in the database

        # Execute the query and fetch tasks
        cursor.execute(query, (session['username'],))
        tasks = cursor.fetchall()

        cursor.close()
        connection.close()

        # Pass the current date to the template to check for overdue tasks
        today = date.today()

        return render_template('view_tasks.html', tasks=tasks, today=today)
    else:
        return "Access denied. Only Employees can view tasks.", 403





@app.route('/update-task-status/<int:task_id>', methods=['POST'])
def update_task_status(task_id):
    # Ensure only employees can access this route
    if 'user_id' in session and session['role'] == 'Employee':
        # Connect to the database
        connection = connect_db()
        cursor = connection.cursor()

        # Update the status of the task to "Completed"
        query = "UPDATE tasks SET status = 'Completed' WHERE task_id = %s AND assigned_to = %s"
        cursor.execute(query, (task_id, session['username']))
        connection.commit()

        cursor.close()
        connection.close()

        return redirect(url_for('view_tasks'))
    else:
        return "Access denied. Only Employees can update tasks.", 403





@app.route('/edit-task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    # Ensure the user is logged in
    if 'user_id' in session:
        user_role = session['role']

        # Connect to the database
        connection = connect_db()
        cursor = connection.cursor(dictionary=True)

        if request.method == 'POST':
            # Get the new task data from the form
            if user_role == 'Manager':
                new_title = request.form['title']
                new_description = request.form['description']
                new_deadline = request.form['deadline']
                
                # Validate deadline is not in the past
                if new_deadline < str(date.today()):
                    flash("Deadline cannot be in the past!", "error")
                    cursor.close()
                    connection.close()
                    return render_template('edit_task.html', task={'task_id': task_id, 'title': new_title, 'description': new_description, 'deadline': new_deadline})

                # Update task for Managers (title, description, deadline)
                query = "UPDATE tasks SET title = %s, description = %s, deadline = %s WHERE task_id = %s"
                cursor.execute(query, (new_title, new_description, new_deadline, task_id))

            elif user_role == 'Employee':
                # Employees can only update task status
                new_status = request.form['status']
                query = "UPDATE tasks SET status = %s WHERE task_id = %s"
                cursor.execute(query, (new_status, task_id))

            connection.commit()
            cursor.close()
            connection.close()

            return redirect(url_for('view_tasks'))

        # Fetch the current task details to populate the form
        query = "SELECT * FROM tasks WHERE task_id = %s"
        cursor.execute(query, (task_id,))
        task = cursor.fetchone()

        cursor.close()
        connection.close()

        return render_template('edit_task.html', task=task, role=user_role)
    else:
        return "Access denied. You must be logged in to edit tasks.", 403



@app.route('/view-users')
def view_users():
    # Ensure only managers can access this page
    if 'user_id' in session and session['role'] == 'Manager':
        # Connect to the database
        connection = connect_db()
        cursor = connection.cursor(dictionary=True)

        # Fetch all users (employees)
        query = "SELECT * FROM users WHERE role = 'Employee'"
        cursor.execute(query)
        users = cursor.fetchall()

        cursor.close()
        connection.close()

        return render_template('view_users.html', users=users)
    else:
        return "Access denied. Only Managers can view this page.", 403



@app.route('/create-user', methods=['GET', 'POST'])
def create_user():
    if 'user_id' in session and session['role'] == 'Manager':
        if request.method == 'POST':
            # Get form data
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']

            # Insert new user into the database
            connection = connect_db()
            cursor = connection.cursor()
            query = "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, 'Employee')"
            cursor.execute(query, (username, email, password))
            connection.commit()

            cursor.close()
            connection.close()

            return redirect(url_for('view_users'))

        return render_template('create_user.html')
    else:
        return "Access denied. Only Managers can create users.", 403



@app.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'user_id' in session and session['role'] == 'Manager':
        connection = connect_db()
        cursor = connection.cursor(dictionary=True)

        if request.method == 'POST':
            # Get the updated user details from the form
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']

            # Update user in the database
            query = "UPDATE users SET username = %s, email = %s, password = %s WHERE user_id = %s"
            cursor.execute(query, (username, email, password, user_id))
            connection.commit()

            cursor.close()
            connection.close()

            return redirect(url_for('view_users'))

        # Fetch the user details to pre-fill the form
        query = "SELECT * FROM users WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()

        cursor.close()
        connection.close()

        return render_template('edit_user.html', user=user)
    else:
        return "Access denied. Only Managers can edit users.", 403




@app.route('/delete-user/<int:user_id>', methods=['GET'])
def delete_user(user_id):
    if 'user_id' in session and session['role'] == 'Manager':
        # Connect to the database
        connection = connect_db()
        cursor = connection.cursor()

        # Delete the user
        query = "DELETE FROM users WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        connection.commit()

        cursor.close()
        connection.close()

        return redirect(url_for('view_users'))
    else:
        return "Access denied. Only Managers can delete users.", 403
    



@app.route('/view-tasks-manager')
def view_tasks_manager():
    if 'user_id' in session and session['role'] == 'Manager':
        connection = connect_db()
        cursor = connection.cursor(dictionary=True)

        # Fetch all tasks (make sure no filter is applied that hides tasks)
        query = "SELECT * FROM tasks"
        cursor.execute(query)
        tasks = cursor.fetchall()

        cursor.close()
        connection.close()

        return render_template('view_tasks_manager.html', tasks=tasks)
    else:
        return "Access denied. Only Managers can view this page.", 403





from flask import flash

@app.route('/edit-task-manager/<int:task_id>', methods=['GET', 'POST'])
def edit_task_manager(task_id):
    if 'user_id' in session and session['role'] == 'Manager':
        connection = connect_db()
        cursor = connection.cursor(dictionary=True)

        if request.method == 'POST':
            # Get the updated task details from the form
            title = request.form['title']
            description = request.form['description']
            deadline = request.form['deadline']

            # Check if any fields are empty 
            if not title or not description or not deadline:
                flash("All fields are required!", "error")
                return render_template('edit_task_manager.html', task={'task_id': task_id, 'title': title, 'description': description, 'deadline': deadline})

            # Update the task in the database
            query = "UPDATE tasks SET title = %s, description = %s, deadline = %s WHERE task_id = %s"
            cursor.execute(query, (title, description, deadline, task_id))
            connection.commit()

            cursor.close()
            connection.close()

            # Flash a success message and redirect
            flash("Task successfully updated!", "success")
            return redirect(url_for('view_tasks_manager'))

        # Fetch the task details to pre-fill the form
        query = "SELECT * FROM tasks WHERE task_id = %s"
        cursor.execute(query, (task_id,))
        task = cursor.fetchone()

        cursor.close()
        connection.close()

        return render_template('edit_task_manager.html', task=task)
    else:
        return "Access denied. Only Managers can edit tasks.", 403




@app.route('/employee-home')
def employee_home():
    if 'user_id' in session and session['role'] == 'Employee':
        # Connect to the database
        connection = connect_db()
        cursor = connection.cursor(dictionary=True)
        
        # Query tasks assigned to the employee
        query = """
            SELECT task_id, title, description, deadline, status
            FROM tasks
            WHERE assigned_to = %s
        """
        cursor.execute(query, (session['username'],))
        tasks = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return render_template('employee_home.html', username=session['username'], tasks=tasks)
    else:
        return redirect(url_for('login'))




# Report Generation Route

@app.route('/generate-report', methods=['GET', 'POST'])
def generate_report():
    if 'user_id' in session and session['role'] == 'Manager':
        if request.method == 'POST':
            report_type = request.form['report_type']

            # Connect to the database and fetch data based on the selected report type
            connection = connect_db()
            cursor = connection.cursor(dictionary=True)

            if report_type == "completed_tasks":
                query = "SELECT * FROM tasks WHERE status = 'Completed'"
            elif report_type == "pending_tasks":
                query = "SELECT * FROM tasks WHERE status = 'Pending'"
            elif report_type == "tasks_by_employee":
                query = """
                SELECT users.username, tasks.title, tasks.description, tasks.status, tasks.deadline
                FROM tasks
                JOIN users ON tasks.assigned_to = users.username
                ORDER BY users.username
                """

            cursor.execute(query)
            tasks = cursor.fetchall()
            cursor.close()
            connection.close()

            return render_template('report.html', tasks=tasks, report_type=report_type)
        
        return render_template('generate_report.html')
    else:
        return redirect(url_for('login'))



# Export PDF
from fpdf import FPDF

@app.route('/export-pdf/<report_type>')
def export_pdf(report_type):
    if 'user_id' in session and session['role'] == 'Manager':
        connection = connect_db()
        cursor = connection.cursor(dictionary=True)

        # Fetch the data based on the report type
        if report_type == "completed_tasks":
            query = "SELECT * FROM tasks WHERE status = 'Completed'"
        elif report_type == "pending_tasks":
            query = "SELECT * FROM tasks WHERE status = 'Pending'"
        elif report_type == "tasks_by_employee":
            query = """
            SELECT users.username, tasks.title, tasks.description, tasks.status, tasks.deadline
            FROM tasks
            JOIN users ON tasks.assigned_to = users.username
            ORDER BY users.username
            """
        else:
            return "Invalid report type"

        cursor.execute(query)
        tasks = cursor.fetchall()
        cursor.close()
        connection.close()

        # Create PDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Title
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, f"Report: {report_type.replace('_', ' ').title()}", 0, 1, 'C')

        # Column headers
        pdf.set_font("Arial", 'B', 12)
        if report_type == "tasks_by_employee":
            headers = ["Title", "Description", "Status", "Deadline", "Assigned Employee"]
        else:
            headers = ["Title", "Description", "Status", "Deadline"]
        
        for header in headers:
            pdf.cell(40, 10, header, 1)
        pdf.ln()

        # Table content
        pdf.set_font("Arial", '', 12)
        for task in tasks:
            pdf.cell(40, 10, str(task['title']), 1)
            pdf.cell(40, 10, str(task['description']), 1)
            pdf.cell(40, 10, str(task['status']), 1)

            # Convert deadline to string
            deadline_str = str(task['deadline']) if task['deadline'] else "None"
            pdf.cell(40, 10, deadline_str, 1)

            if report_type == "tasks_by_employee":
                pdf.cell(40, 10, str(task['username']), 1)
            pdf.ln()

        # Save PDF
        pdf_file_name = f"{report_type}_report.pdf"
        pdf.output(pdf_file_name)

        return f'Report has been exported as PDF: <a href="/download-pdf/{pdf_file_name}">Download {pdf_file_name}</a>'

    else:
        return redirect(url_for('login'))

# Allow user to download PDF
from flask import send_file

@app.route('/download-pdf/<filename>')
def download_pdf(filename):
    return send_file(filename, as_attachment=True)







if __name__ == "__main__":
    # Start the scheduler thread
    scheduler_thread = Thread(target=run_scheduler)
    scheduler_thread.daemon = True  # Ensures the thread exits when the main program does
    scheduler_thread.start()

    # Start the Flask app
    app.run(debug=True)
