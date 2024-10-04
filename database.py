import mysql.connector

def connect_db():
    connection = mysql.connector.connect(
        host="localhost",      # MySQL host
        user="root",    # MySQL username
        password="JKQL5280303aj!",# MySQL password
        database="employee_task_db" # The database just created
    )
    return connection
