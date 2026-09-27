import mysql.connector
from config import Config
from mysql.connector import Error


def init_db():
    conn = None
    cursor = None

    try:
        # ---------------------------------------------------------
        # Connect to MySQL server
        # ---------------------------------------------------------
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD
        )

        cursor = conn.cursor()

        # ---------------------------------------------------------
        # Create database if it does not exist
        # ---------------------------------------------------------
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DB}`"
        )

        cursor.execute(
            f"USE `{Config.MYSQL_DB}`"
        )

        # =========================================================
        # MEDICINES TABLE
        # =========================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                category VARCHAR(50) NOT NULL,
                batch_number VARCHAR(50),
                quantity INT NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                mfg_date DATE NULL,
                expiry_date DATE NOT NULL,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ---------------------------------------------------------
        # Add mfg_date to existing medicines table if missing
        # ---------------------------------------------------------
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'medicines'
              AND COLUMN_NAME = 'mfg_date'
        """, (Config.MYSQL_DB,))

        mfg_exists = cursor.fetchone()[0]

        if not mfg_exists:
            cursor.execute("""
                ALTER TABLE medicines
                ADD COLUMN mfg_date DATE NULL
                AFTER price
            """)

            print("Added mfg_date column to medicines table.")

        # =========================================================
        # CUSTOMERS TABLE
        # =========================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (name, phone)
            )
        """)

        # =========================================================
        # BILLS TABLE
        # =========================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_id INT NULL,
                bill_number VARCHAR(50) NOT NULL UNIQUE,
                bill_date DATE NOT NULL,
                total_amount DECIMAL(10, 2) NOT NULL,
                discount DECIMAL(10, 2) DEFAULT 0,
                tax DECIMAL(10, 2) DEFAULT 0,
                grand_total DECIMAL(10, 2) NOT NULL,
                payment_method VARCHAR(50),
                prescription_notes TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (customer_id)
                    REFERENCES customers(id)
                    ON DELETE SET NULL
            )
        """)

        # ---------------------------------------------------------
        # Add prescription_notes to existing bills table if missing
        # ---------------------------------------------------------
        cursor.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = 'bills'
              AND COLUMN_NAME = 'prescription_notes'
        """, (Config.MYSQL_DB,))

        prescription_exists = cursor.fetchone()[0]

        if not prescription_exists:
            cursor.execute("""
                ALTER TABLE bills
                ADD COLUMN prescription_notes TEXT NULL
                AFTER payment_method
            """)

            print("Added prescription_notes column to bills table.")

        # =========================================================
        # BILL ITEMS TABLE
        # =========================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bill_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                bill_id INT NOT NULL,
                medicine_id INT NOT NULL,
                quantity INT NOT NULL,
                price DECIMAL(10, 2) NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                mfg_date DATE NOT NULL,
                expiry_date DATE NOT NULL,

                FOREIGN KEY (bill_id)
                    REFERENCES bills(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (medicine_id)
                    REFERENCES medicines(id)
            )
        """)

        # =========================================================
        # ADMIN TABLE
        # =========================================================
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL
            )
        """)

        # ---------------------------------------------------------
        # Create default admin account if it does not exist
        # ---------------------------------------------------------
        cursor.execute(
            "SELECT id FROM admin WHERE username = %s",
            ("admin",)
        )

        if not cursor.fetchone():
            cursor.execute(
                """
                INSERT INTO admin (username, password)
                VALUES (%s, %s)
                """,
                ("admin", "admin123")
            )

            print("Default admin account created.")

        # ---------------------------------------------------------
        # Save all changes
        # ---------------------------------------------------------
        conn.commit()

        print("Database initialized successfully!")

        return True

    except mysql.connector.Error as err:

        if conn:
            conn.rollback()

        print(f"Database initialization error: {err}")

        return False

    finally:

        if cursor:
            cursor.close()

        if conn and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    raise SystemExit(0 if init_db() else 1)