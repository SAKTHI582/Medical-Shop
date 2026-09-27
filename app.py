import os
import json
import string
import random
import mysql.connector
from config import Config
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
from datetime import date, datetime, timedelta
from flask_weasyprint import HTML, render_pdf
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (Flask, render_template, request, redirect, url_for, session, flash, jsonify, current_app)
from prometheus_flask_exporter import PrometheusMetrics


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)
app.config.from_object(Config)

app.secret_key = Config.SECRET_KEY


# ============================================================
# EXTENSIONS
# ============================================================

mysql = MySQL(app)
mail = Mail(app)
metrics = PrometheusMetrics(app)


# ============================================================
# SCHEDULER
# ============================================================

scheduler = None


# ============================================================
# HOME
# ============================================================

@app.route('/')
def home():
    return render_template('home.html')


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route('/health')
def health():
    """
    Lightweight health endpoint for Docker/Kubernetes.
    """
    return jsonify({
        'status': 'ok'
    })


# ============================================================
# LOGIN
# ============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form.get(
            'username',
            ''
        ).strip()

        password = request.form.get(
            'password',
            ''
        )

        cur = mysql.connection.cursor()

        try:

            cur.execute(
                """
                SELECT *
                FROM admin
                WHERE username = %s
                """,
                (username,)
            )

            admin = cur.fetchone()

        finally:
            cur.close()

        if admin:

            # Existing project stores the default password
            # as plain text, so keep compatibility here.
            if admin['password'] == password:

                session['logged_in'] = True
                session['username'] = username

                flash(
                    'Login successful!',
                    'success'
                )

                check_expired_products()

                return redirect(
                    url_for('dashboard')
                )

            else:

                flash(
                    'Invalid credentials!',
                    'danger'
                )

        else:

            flash(
                'Invalid credentials!',
                'danger'
            )

    return render_template('login.html')


# ============================================================
# CHECK EXPIRED PRODUCTS
# ============================================================

def check_expired_products():

    cur = mysql.connection.cursor()

    try:

        today = datetime.now().date()

        cur.execute(
            """
            SELECT
                name,
                expiry_date
            FROM medicines
            WHERE expiry_date < %s
            """,
            (today,)
        )

        expired_products = cur.fetchall()

        if expired_products:

            product_list = "\n".join(
                [
                    f"{product['name']} "
                    f"(Expiry Date: {product['expiry_date']})"
                    for product in expired_products
                ]
            )

            subject = "Expired Medicines Alert"

            body = (
                "The following medicines have expired:\n\n"
                + product_list
            )

            recipients = [
                email.strip()
                for email in os.getenv(
                    'MAIL_RECIPIENTS',
                    ''
                ).split(',')
                if email.strip()
            ]

            if recipients:

                msg = Message(
                    subject,
                    recipients=recipients
                )

                msg.body = body

                with current_app.app_context():
                    mail.send(msg)

    finally:
        cur.close()


# ============================================================
# OPTIONAL EXPIRY SCHEDULER
# ============================================================

if os.getenv(
    'ENABLE_EXPIRY_SCHEDULER',
    'false'
).lower() == 'true':

    scheduler = BackgroundScheduler()

    scheduler.add_job(
        check_expired_products,
        trigger='interval',
        days=1,
        id='expiry-alert',
        replace_existing=True
    )

    scheduler.start()


# ============================================================
# LOGOUT
# ============================================================

@app.route('/logout')
def logout():

    session.clear()
    session.pop('_flashes', None)

    return redirect(
        url_for('login')
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route('/dashboard')
def dashboard():

    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    today = datetime.now().date()

    try:

        # ------------------------------------------------------
        # TOTAL MEDICINES
        # ------------------------------------------------------

        cur.execute(
            "SELECT COUNT(*) AS count FROM medicines"
        )

        result = cur.fetchone()

        medicines_count = (
            result['count']
            if result
            else 0
        )


        # ------------------------------------------------------
        # EXPIRED
        # ------------------------------------------------------

        cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM medicines
            WHERE expiry_date < %s
            """,
            (today,)
        )

        result = cur.fetchone()

        expired_count = (
            result['count']
            if result
            else 0
        )


        # ------------------------------------------------------
        # EXPIRING WITHIN 30 DAYS
        # ------------------------------------------------------

        cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM medicines
            WHERE expiry_date BETWEEN %s AND %s
            """,
            (
                today,
                today + timedelta(days=30)
            )
        )

        result = cur.fetchone()

        warning_count = (
            result['count']
            if result
            else 0
        )


        # ------------------------------------------------------
        # SAFE
        # ------------------------------------------------------

        cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM medicines
            WHERE expiry_date > %s
            """,
            (
                today + timedelta(days=30),
            )
        )

        result = cur.fetchone()

        safe_count = (
            result['count']
            if result
            else 0
        )


        # ------------------------------------------------------
        # RECENT BILLS
        # ------------------------------------------------------

        cur.execute(
            """
            SELECT
                b.id,
                b.bill_number,
                b.bill_date,
                b.grand_total
            FROM bills b
            ORDER BY b.bill_date DESC
            LIMIT 5
            """
        )

        recent_bills = cur.fetchall()


        # ------------------------------------------------------
        # EXPIRING MEDICINES
        # ------------------------------------------------------

        cur.execute(
            """
            SELECT
                name,
                expiry_date,
                quantity
            FROM medicines
            WHERE expiry_date BETWEEN %s AND %s
            ORDER BY expiry_date ASC
            LIMIT 5
            """,
            (
                today,
                today + timedelta(days=30)
            )
        )

        expiring_soon = cur.fetchall()

    finally:
        cur.close()


    return render_template(
        'dashboard.html',
        medicines_count=medicines_count,
        expired_count=expired_count,
        warning_count=warning_count,
        safe_count=safe_count,
        recent_bills=recent_bills,
        expiring_soon=expiring_soon,
        today=today
    )


# ============================================================
# MEDICINES
# ============================================================

@app.route('/medicines')
def medicines():

    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    try:

        cur.execute(
            """
            SELECT *
            FROM medicines
            ORDER BY name
            """
        )

        medicines = cur.fetchall()

    finally:
        cur.close()

    today = datetime.now().date()

    return render_template(
        'medicines.html',
        medicines=medicines,
        today=today
    )


# ============================================================
# ADD MEDICINE
# ============================================================

@app.route('/add_medicine', methods=['GET', 'POST'])
def add_medicine():

    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':

        try:

            # --------------------------------------------------
            # FORM DATA
            # --------------------------------------------------

            name = request.form.get(
                'name',
                ''
            ).strip()

            category = request.form.get(
                'category',
                ''
            ).strip()

            batch_number = request.form.get(
                'batch_number',
                ''
            ).strip()

            quantity = int(
                request.form.get(
                    'quantity',
                    '0'
                )
            )

            price = Decimal(
                request.form.get(
                    'price',
                    '0'
                )
            )

            mfg_date = request.form.get(
                'mfg_date'
            )

            expiry_date = request.form.get(
                'expiry_date'
            )


            # --------------------------------------------------
            # VALIDATION
            # --------------------------------------------------

            if not name:
                raise Exception(
                    'Medicine name is required.'
                )

            if not category:
                raise Exception(
                    'Category is required.'
                )

            if quantity < 0:
                raise Exception(
                    'Quantity cannot be negative.'
                )

            if price < 0:
                raise Exception(
                    'Price cannot be negative.'
                )

            if not mfg_date:
                raise Exception(
                    'Manufacturing date is required.'
                )

            if not expiry_date:
                raise Exception(
                    'Expiry date is required.'
                )


            # --------------------------------------------------
            # DATE VALIDATION
            # --------------------------------------------------

            mfg = datetime.strptime(
                mfg_date,
                '%Y-%m-%d'
            ).date()

            expiry = datetime.strptime(
                expiry_date,
                '%Y-%m-%d'
            ).date()

            if expiry <= mfg:
                raise Exception(
                    'Expiry date must be after manufacturing date.'
                )


            # --------------------------------------------------
            # INSERT MEDICINE
            # --------------------------------------------------

            cur = mysql.connection.cursor()

            try:

                cur.execute(
                    """
                    INSERT INTO medicines
                    (
                        name,
                        category,
                        batch_number,
                        quantity,
                        price,
                        mfg_date,
                        expiry_date
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        name,
                        category,
                        batch_number,
                        quantity,
                        price,
                        mfg_date,
                        expiry_date
                    )
                )

                mysql.connection.commit()

            finally:
                cur.close()


            flash(
                'Medicine added successfully!',
                'success'
            )

            return redirect(
                url_for('medicines')
            )

        except (
            ValueError,
            InvalidOperation
        ) as e:

            flash(
                f'Invalid medicine data: {str(e)}',
                'danger'
            )

        except Exception as e:

            mysql.connection.rollback()

            flash(
                f'Error adding medicine: {str(e)}',
                'danger'
            )


    return render_template(
        'add_medicine.html'
    )


# ============================================================
# EDIT MEDICINE
# ============================================================

@app.route(
    '/edit_medicine/<int:id>',
    methods=['GET', 'POST']
)
def edit_medicine(id):

    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    try:

        if request.method == 'POST':

            # --------------------------------------------------
            # FORM DATA
            # --------------------------------------------------

            name = request.form.get(
                'name',
                ''
            ).strip()

            category = request.form.get(
                'category',
                ''
            ).strip()

            batch_number = request.form.get(
                'batch_number',
                ''
            ).strip()

            quantity = int(
                request.form.get(
                    'quantity',
                    '0'
                )
            )

            price = Decimal(
                request.form.get(
                    'price',
                    '0'
                )
            )

            mfg_date = request.form.get(
                'mfg_date'
            )

            expiry_date = request.form.get(
                'expiry_date'
            )


            # --------------------------------------------------
            # VALIDATION
            # --------------------------------------------------

            if not name:
                raise Exception(
                    'Medicine name is required.'
                )

            if not category:
                raise Exception(
                    'Category is required.'
                )

            if quantity < 0:
                raise Exception(
                    'Quantity cannot be negative.'
                )

            if price < 0:
                raise Exception(
                    'Price cannot be negative.'
                )

            if not mfg_date:
                raise Exception(
                    'Manufacturing date is required.'
                )

            if not expiry_date:
                raise Exception(
                    'Expiry date is required.'
                )


            # --------------------------------------------------
            # DATE VALIDATION
            # --------------------------------------------------

            mfg = datetime.strptime(
                mfg_date,
                '%Y-%m-%d'
            ).date()

            expiry = datetime.strptime(
                expiry_date,
                '%Y-%m-%d'
            ).date()

            if expiry <= mfg:
                raise Exception(
                    'Expiry date must be after manufacturing date.'
                )


            # --------------------------------------------------
            # UPDATE
            # --------------------------------------------------

            cur.execute(
                """
                UPDATE medicines
                SET
                    name = %s,
                    category = %s,
                    batch_number = %s,
                    quantity = %s,
                    price = %s,
                    mfg_date = %s,
                    expiry_date = %s
                WHERE id = %s
                """,
                (
                    name,
                    category,
                    batch_number,
                    quantity,
                    price,
                    mfg_date,
                    expiry_date,
                    id
                )
            )

            mysql.connection.commit()

            flash(
                'Medicine updated successfully!',
                'success'
            )

            return redirect(
                url_for('medicines')
            )


        # ------------------------------------------------------
        # GET MEDICINE
        # ------------------------------------------------------

        cur.execute(
            """
            SELECT *
            FROM medicines
            WHERE id = %s
            """,
            (id,)
        )

        medicine = cur.fetchone()

    except Exception as e:

        mysql.connection.rollback()

        flash(
            f'Error updating medicine: {str(e)}',
            'danger'
        )

        medicine = None

    finally:
        cur.close()


    if not medicine:

        flash(
            'Medicine not found!',
            'danger'
        )

        return redirect(
            url_for('medicines')
        )


    return render_template(
        'edit_medicine.html',
        medicine=medicine
    )


# ============================================================
# DELETE MEDICINE
# ============================================================

@app.route(
    '/delete_medicine/<int:id>',
    methods=['POST']
)
def delete_medicine(id):

    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    try:

        cur.execute(
            """
            DELETE FROM bill_items
            WHERE medicine_id = %s
            """,
            (id,)
        )

        cur.execute(
            """
            DELETE FROM medicines
            WHERE id = %s
            """,
            (id,)
        )

        mysql.connection.commit()

        flash(
            'Medicine deleted successfully!',
            'success'
        )

    except mysql.connector.Error as e:

        mysql.connection.rollback()

        flash(
            f'Error deleting medicine: {str(e)}',
            'danger'
        )

    except Exception as e:

        mysql.connection.rollback()

        flash(
            f'An unexpected error occurred: {str(e)}',
            'danger'
        )

    finally:
        cur.close()

    return redirect(
        url_for('medicines')
    )


# ============================================================
# MEDICINE PDF REPORT
# ============================================================

@app.route('/medicine_report')
def medicine_report():

    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    try:

        cur.execute(
            """
            SELECT *
            FROM medicines
            ORDER BY name
            """
        )

        medicines = cur.fetchall()

    finally:
        cur.close()

    current_date = datetime.now()

    html = render_template(
        'medicine_report.html',
        medicines=medicines,
        current_date=current_date
    )

    return render_pdf(
        HTML(string=html)
    )


# ============================================================
# BILLING
# ============================================================

@app.route('/billing', methods=['GET', 'POST'])
def billing():

    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # ==========================================================
    # POST - CREATE BILL
    # ==========================================================
    if request.method == 'POST':

        try:
            customer_name = request.form.get(
                'customer_name', ''
            ).strip()

            customer_phone = request.form.get(
                'customer_phone', ''
            ).strip()

            payment_method = request.form.get(
                'payment_method', 'Cash'
            ).strip()

            prescription_notes = request.form.get(
                'prescription_notes', ''
            ).strip()

            cart_json = request.form.get(
                'cart_items', '[]'
            )

            discount = Decimal(
                request.form.get('discount', '0') or '0'
            )


            # --------------------------------------------------
            # VALIDATE DISCOUNT
            # --------------------------------------------------

            if discount < 0:
                raise ValueError(
                    "Discount cannot be negative."
                )


            # --------------------------------------------------
            # LOAD CART JSON
            # --------------------------------------------------

            try:
                cart = json.loads(cart_json)

            except (json.JSONDecodeError, TypeError):
                raise ValueError(
                    "Invalid cart data."
                )


            if not isinstance(cart, list) or len(cart) == 0:
                raise ValueError(
                    "Cart is empty."
                )


            # --------------------------------------------------
            # START TRANSACTION
            # --------------------------------------------------

            subtotal = Decimal('0.00')

            verified_items = []


            # ==================================================
            # VERIFY EVERY MEDICINE FROM DATABASE
            # ==================================================

            for item in cart:

                medicine_id = item.get('id')

                try:
                    medicine_id = int(medicine_id)

                except (TypeError, ValueError):
                    raise ValueError(
                        "Invalid medicine ID."
                    )


                try:
                    requested_quantity = int(
                        item.get('quantity', 0)
                    )

                except (TypeError, ValueError):
                    raise ValueError(
                        "Invalid medicine quantity."
                    )


                if requested_quantity <= 0:
                    raise ValueError(
                        "Medicine quantity must be greater than zero."
                    )


                # --------------------------------------------------
                # LOCK MEDICINE ROW
                # --------------------------------------------------

                cur.execute(
                    """
                    SELECT
                        id,
                        name,
                        price,
                        quantity,
                        mfg_date,
                        expiry_date
                    FROM medicines
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (medicine_id,)
                )

                medicine = cur.fetchone()


                if not medicine:

                    raise ValueError(
                        f"Medicine ID {medicine_id} was not found."
                    )


                # --------------------------------------------------
                # GET VALUES
                # --------------------------------------------------

                medicine_name = medicine['name']

                db_price = Decimal(
                    str(medicine['price'])
                )

                available_stock = int(
                    medicine['quantity']
                )

                mfg_date = medicine['mfg_date']

                expiry_date = medicine['expiry_date']


                # --------------------------------------------------
                # STOCK VALIDATION
                # --------------------------------------------------

                if available_stock <= 0:

                    raise ValueError(
                        f"{medicine_name} is out of stock."
                    )


                if requested_quantity > available_stock:

                    raise ValueError(
                        f"Only {available_stock} units of "
                        f"{medicine_name} are available."
                    )


                # ==================================================
                # IMPORTANT: EXPIRY VALIDATION
                # ==================================================

                if expiry_date is not None:

                    today = date.today()

                    if expiry_date <= today:

                        raise ValueError(
                            f"{medicine_name} is expired "
                            f"({expiry_date.strftime('%d-%m-%Y')}) "
                            f"and cannot be billed."
                        )


                # --------------------------------------------------
                # CALCULATE ITEM TOTAL
                # --------------------------------------------------

                item_total = (
                    db_price *
                    Decimal(requested_quantity)
                )

                subtotal += item_total


                # --------------------------------------------------
                # SAVE VERIFIED ITEM
                # --------------------------------------------------

                verified_items.append({
                    'medicine_id': medicine_id,
                    'name': medicine_name,
                    'quantity': requested_quantity,
                    'price': db_price,
                    'amount': item_total,
                    'mfg_date': mfg_date,
                    'expiry_date': expiry_date
                })


            # ==================================================
            # DISCOUNT VALIDATION
            # ==================================================

            if discount > subtotal:

                raise ValueError(
                    "Discount cannot be greater than subtotal."
                )


            # ==================================================
            # GST CALCULATION
            # ==================================================

            taxable_amount = subtotal - discount

            gst_rate = Decimal('0.18')

            gst_amount = (
                taxable_amount * gst_rate
            ).quantize(
                Decimal('0.01')
            )


            grand_total = (
                taxable_amount + gst_amount
            ).quantize(
                Decimal('0.01')
            )


            # ==================================================
            # CUSTOMER
            # ==================================================

            customer_id = None


            # Both empty = walk-in customer
            if not customer_name and not customer_phone:

                customer_id = None


            # One field missing
            elif not customer_name or not customer_phone:

                raise ValueError(
                    "Please enter both customer name and "
                    "phone number, or leave both empty."
                )


            # Both present
            else:

                cur.execute(
                    """
                    SELECT id
                    FROM customers
                    WHERE phone = %s
                    LIMIT 1
                    """,
                    (customer_phone,)
                )

                existing_customer = cur.fetchone()


                if existing_customer:

                    customer_id = existing_customer['id']

                    cur.execute(
                        """
                        UPDATE customers
                        SET name = %s
                        WHERE id = %s
                        """,
                        (
                            customer_name,
                            customer_id
                        )
                    )

                else:

                    cur.execute(
                        """
                        INSERT INTO customers
                        (
                            name,
                            phone
                        )
                        VALUES
                        (
                            %s,
                            %s
                        )
                        """,
                        (
                            customer_name,
                            customer_phone
                        )
                    )

                    customer_id = cur.lastrowid


            # ==================================================
            # GENERATE BILL NUMBER
            # ==================================================

            import random

            bill_number = None

            while True:

                candidate = (
                    'BIL' +
                    str(random.randint(100000, 999999))
                )

                cur.execute(
                    """
                    SELECT id
                    FROM bills
                    WHERE bill_number = %s
                    LIMIT 1
                    """,
                    (candidate,)
                )

                if not cur.fetchone():

                    bill_number = candidate
                    break


            # ==================================================
            # INSERT BILL
            # ==================================================

            cur.execute(
                """
                INSERT INTO bills
                (
                    customer_id,
                    bill_number,
                    bill_date,
                    total_amount,
                    discount,
                    tax,
                    grand_total,
                    payment_method,
                    prescription_notes
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    customer_id,
                    bill_number,
                    date.today(),
                    subtotal,
                    discount,
                    gst_amount,
                    grand_total,
                    payment_method,
                    prescription_notes
                )
            )

            bill_id = cur.lastrowid


            # ==================================================
            # INSERT BILL ITEMS + REDUCE STOCK
            # ==================================================

            for item in verified_items:

                cur.execute(
                    """
                    INSERT INTO bill_items
                    (
                        bill_id,
                        medicine_id,
                        quantity,
                        price,
                        amount,
                        mfg_date,
                        expiry_date
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        bill_id,
                        item['medicine_id'],
                        item['quantity'],
                        item['price'],
                        item['amount'],
                        item['mfg_date'],
                        item['expiry_date']
                    )
                )


                # --------------------------------------------------
                # REDUCE STOCK
                # --------------------------------------------------

                cur.execute(
                    """
                    UPDATE medicines
                    SET quantity = quantity - %s
                    WHERE id = %s
                    """,
                    (
                        item['quantity'],
                        item['medicine_id']
                    )
                )


            # ==================================================
            # COMMIT
            # ==================================================

            mysql.connection.commit()


            flash(
                f"Bill {bill_number} created successfully.",
                "success"
            )


            return redirect(
                url_for(
                    'view_bill',
                    bill_id=bill_id
                )
            )


        except Exception as e:

            mysql.connection.rollback()

            flash(
                f"Billing failed: {str(e)}",
                "danger"
            )

            return redirect(
                url_for('billing')
            )


        finally:

            cur.close()


    # ==========================================================
    # GET - SHOW MEDICINES
    # ==========================================================

    cur.execute(
        """
        SELECT
            id,
            name,
            category,
            batch_number,
            quantity,
            price,
            mfg_date,
            expiry_date
        FROM medicines
        WHERE quantity > 0
        ORDER BY name ASC
        """
    )

    medicines = cur.fetchall()

    cur.close()


    return render_template(
        'billing.html',
        medicines=medicines,
        today=date.today()
)


# ============================================================
# BILLS
# ============================================================

@app.route('/bills')
def bills():

    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    try:

        cur.execute(
            """
            SELECT
                b.id,
                b.bill_number,
                b.bill_date,
                b.grand_total,
                c.name AS customer_name
            FROM bills b
            LEFT JOIN customers c
                ON b.customer_id = c.id
            ORDER BY b.bill_date DESC
            """
        )

        bills = cur.fetchall()

    finally:
        cur.close()


    return render_template(
        'bills.html',
        bills=bills
    )


# ============================================================
# VIEW BILL
# ============================================================

@app.route('/bill/<int:bill_id>')
def view_bill(bill_id):

    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()


    try:

        # ------------------------------------------------------
        # BILL + CUSTOMER
        # ------------------------------------------------------

        cur.execute(
            """
            SELECT
                b.*,
                c.name AS customer_name,
                c.phone AS customer_phone
            FROM bills b
            LEFT JOIN customers c
                ON b.customer_id = c.id
            WHERE b.id = %s
            """,
            (bill_id,)
        )

        bill = cur.fetchone()


        if not bill:

            flash(
                'Bill not found!',
                'danger'
            )

            return redirect(
                url_for('bills')
            )


        # ------------------------------------------------------
        # BILL ITEMS
        # ------------------------------------------------------

        cur.execute(
            """
            SELECT
                bi.*,
                m.name AS medicine_name
            FROM bill_items bi
            JOIN medicines m
                ON bi.medicine_id = m.id
            WHERE bi.bill_id = %s
            ORDER BY bi.id
            """,
            (bill_id,)
        )

        items = cur.fetchall()

    finally:

        cur.close()


    return render_template(
        'view_bill.html',
        bill=bill,
        items=items
    )


# ============================================================
# DELETE BILL
# ============================================================

@app.route(
    '/delete_bill/<int:bill_id>',
    methods=['POST']
)
def delete_bill(bill_id):

    if 'logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    try:

        cur.execute(
            """
            DELETE FROM bill_items
            WHERE bill_id = %s
            """,
            (bill_id,)
        )


        cur.execute(
            """
            DELETE FROM bills
            WHERE id = %s
            """,
            (bill_id,)
        )


        mysql.connection.commit()


        flash(
            'Bill deleted successfully!',
            'success'
        )

    except Exception as e:

        mysql.connection.rollback()

        flash(
            f'Error deleting bill: {str(e)}',
            'danger'
        )

    finally:

        cur.close()


    return redirect(
        url_for('bills')
    )


# ============================================================
# MEDICINES API
# ============================================================

@app.route('/api/medicines')
def api_medicines():

    if 'logged_in' not in session:

        return jsonify({
            'error': 'Unauthorized'
        }), 401


    search = request.args.get(
        'search',
        ''
    ).strip()


    cur = mysql.connection.cursor()


    try:

        query = """
            SELECT
                id,
                name,
                price,
                quantity,
                mfg_date,
                expiry_date
            FROM medicines
            WHERE quantity > 0
        """

        params = []


        if search:

            query += """
                AND name LIKE %s
            """

            params.append(
                f"%{search}%"
            )


        query += """
            ORDER BY name
            LIMIT 10
        """


        cur.execute(
            query,
            params
        )

        medicines = cur.fetchall()

    finally:

        cur.close()


    return jsonify(medicines)


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == '__main__':

    app.run(
        debug=True
    )