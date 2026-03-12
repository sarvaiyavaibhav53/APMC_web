import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='apmc'
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None

if __name__ == '__main__':
    conn = get_connection()
    if conn and conn.is_connected():
        print("Database Connected Successfully!")
        conn.close()
