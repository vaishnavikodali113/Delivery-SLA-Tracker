import sqlite3
import os

DB_PATH = os.environ.get("SQLITE_DB_PATH")
if not DB_PATH:
    DB_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "delivery_oltp.db")
    )
if os.environ.get("TESTING") == "true":
    DB_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "delivery_oltp_test.db")
    )
# Ensure directory for DB exists
db_dir = os.path.dirname(DB_PATH)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)


def get_db_connection():
    """Returns a connection to the SQLite OLTP database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the SQLite database tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create order_events table for transactional events
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            weather TEXT NOT NULL,
            order_volume INTEGER NOT NULL,
            customer_id TEXT NOT NULL,
            restaurant_id TEXT NOT NULL,
            rider_id TEXT NOT NULL,
            latitude REAL,
            longitude REAL
        )
    ''')

    # Create dq_logs table for data quality checks
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dq_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            rule_name TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            timestamp TEXT NOT NULL
        )
    ''')

    # Indexing for faster reads during ETL
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_events_order_id ON order_events(order_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_events_timestamp ON order_events(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dq_logs_order_id ON dq_logs(order_id)')

    conn.commit()
    conn.close()
    print(f"OLTP Database initialized at: {DB_PATH}")

if __name__ == "__main__":
    init_db()
