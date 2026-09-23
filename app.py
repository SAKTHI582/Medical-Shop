import os
import json
import string
import random
import mysql.connector
from config import Config
from flask_mysqldb import MySQL
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from flask_weasyprint import HTML, render_pdf 
from apscheduler.schedulers.background import BackgroundScheduler 
from werkzeug.security import generate_password_hash, check_password_hash 
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
app.config.from_object(Config)

# Mail settings are loaded from Config/environment variables.
# Do not hard-code SMTP credentials in source control.

# Initialize MySQL
mysql = MySQL(app)
mail = Mail(app)
metrics = PrometheusMetrics(app)

# Scheduler is optional. In Kubernetes, use the CronJob manifest instead of
# running a scheduler in every Gunicorn worker.
scheduler = None

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/health')
def health():
    """Lightweight Kubernetes/Docker health endpoint."""
    return jsonify({'status': 'ok'})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM admin WHERE username = %s", (username,))
        admin = cur.fetchone()
        cur.close()
        
        if admin:
            if admin['password'] == password:
                session['logged_in'] = True
                session['username'] = username
                flash('Login successful!', 'success')
                
                # Check for expired medicines and send alert
                check_expired_products()  # Call the function to check for expired medicines
                
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid credentials!', 'danger')
        else:
            flash('Invalid credentials!', 'danger')
    
    return render_template('login.html')

def check_expired_products():
    cur = mysql.connection.cursor()
    today = datetime.now().date()
    
    # Query to find expired medicines
    cur.execute("SELECT name, expiry_date FROM medicines WHERE expiry_date < %s", (today,))
    expired_products = cur.fetchall()
    
    if expired_products:
        product_list = "\n".join([f"{product['name']} (Expiry Date: {product['expiry_date']})" for product in expired_products])
        subject = "Expired Medicines Alert"
        body = f"The following medicines have expired:\n\n{product_list}"
        
        # Send email alert
        recipients = [email.strip() for email in os.getenv('MAIL_RECIPIENTS', '').split(',') if email.strip()]
        if recipients:
            msg = Message(subject, recipients=recipients)
            msg.body = body
            with current_app.app_context():
                mail.send(msg)  # Ensure mail is sent within the app context
    
    cur.close()


if os.getenv('ENABLE_EXPIRY_SCHEDULER', 'false').lower() == 'true':
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_expired_products, trigger='interval', days=1, id='expiry-alert', replace_existing=True)
    scheduler.start()


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    today = datetime.now().date()
    
    # Get counts for dashboard cards
    cur.execute("SELECT COUNT(*) as count FROM medicines")
    result = cur.fetchone()
    medicines_count = result['count'] if result else 0  # Use named access if using DictCursor

    cur.execute("SELECT COUNT(*) as count FROM medicines WHERE expiry_date < %s", (today,))
    result = cur.fetchone()
    expired_count = result['count'] if result else 0

    cur.execute("SELECT COUNT(*) as count FROM medicines WHERE expiry_date BETWEEN %s AND %s", 
               (today, today + timedelta(days=30)))
    result = cur.fetchone()
    warning_count = result['count'] if result else 0

    cur.execute("SELECT COUNT(*) as count FROM medicines WHERE expiry_date > %s", 
               (today + timedelta(days=30),))
    result = cur.fetchone()
    safe_count = result['count'] if result else 0

    # Get recent bills
    cur.execute("""SELECT b.id, b.bill_number, b.bill_date, b.grand_total
                   FROM bills b ORDER BY b.bill_date DESC LIMIT 5""")
    recent_bills = cur.fetchall()
    
    # Get medicines expiring soon (within 30 days)
    cur.execute("""SELECT name, expiry_date, quantity 
                   FROM medicines 
                   WHERE expiry_date BETWEEN %s AND %s
                   ORDER BY expiry_date ASC LIMIT 5""", (today, today + timedelta(days=30)))
    expiring_soon = cur.fetchall()
    
    cur.close()
    
    return render_template('dashboard.html', 
                         medicines_count=medicines_count,
                         expired_count=expired_count,
                         warning_count=warning_count,
                         safe_count=safe_count,
                         recent_bills=recent_bills,
                         expiring_soon=expiring_soon,
                         today=today)

@app.route('/medicines')
def medicines():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM medicines ORDER BY name")
    medicines = cur.fetchall()
    cur.close()
    
    today = datetime.now().date()
    return render_template('medicines.html', medicines=medicines, today=today)

@app.route('/add_medicine', methods=['GET', 'POST'])
def add_medicine():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        batch_number = request.form['batch_number']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])
        expiry_date = request.form['expiry_date']
        
        cur = mysql.connection.cursor()
        cur.execute("""INSERT INTO medicines (name, category, batch_number, quantity, price, expiry_date)
                       VALUES (%s, %s, %s, %s, %s, %s)""", (name, category, batch_number, quantity, price, expiry_date))
        mysql.connection.commit()
        cur.close()
        
        flash('Medicine added successfully!', 'success')
        return redirect(url_for('medicines'))
    
    return render_template('add_medicine.html')

@app.route('/edit_medicine/<int:id>', methods=['GET', 'POST'])
def edit_medicine(id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        batch_number = request.form['batch_number']
        quantity = int(request.form['quantity'])
        price = float(request.form['price'])
        expiry_date = request.form['expiry_date']
        
        cur.execute("""UPDATE medicines 
                       SET name=%s, category=%s, batch_number=%s, quantity=%s, price=%s, expiry_date=%s
                       WHERE id=%s""", (name, category, batch_number, quantity, price, expiry_date, id))
        mysql.connection.commit()
        cur.close()
        
        flash('Medicine updated successfully!', 'success')
        return redirect(url_for('medicines'))
    
    cur.execute("SELECT * FROM medicines WHERE id = %s", (id,))
    medicine = cur.fetchone()
    cur.close()
    
    if not medicine:
        flash('Medicine not found!', 'danger')
        return redirect(url_for('medicines'))
    
    return render_template('edit_medicine.html', medicine=medicine)

@app.route('/delete_medicine/<int:id>', methods=['POST'])
def delete_medicine(id):
    cur = mysql.connection.cursor()
    
    try:
        # First, delete all items associated with the medicine
        cur.execute("DELETE FROM bill_items WHERE medicine_id = %s", (id,))
        
        # Now, delete the medicine itself
        cur.execute("DELETE FROM medicines WHERE id = %s", (id,))
        
        # Commit the changes
        mysql.connection.commit()
        flash('Medicine deleted successfully!', 'success')
    except mysql.connector.Error as e:
        mysql.connection.rollback()  # Rollback in case of error
        flash(f'Error deleting medicine: {str(e)}', 'danger')
    except Exception as e:
        mysql.connection.rollback()  # Rollback in case of any other error
        flash(f'An unexpected error occurred: {str(e)}', 'danger')
    finally:
        cur.close()  # Ensure cursor is closed
    
    return redirect(url_for('medicines'))

@app.route('/medicine_report')
def medicine_report():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM medicines")  # Fetch the necessary data for the report
    medicines = cur.fetchall()
    cur.close()
    
    # Render the PDF
    return render_pdf(HTML(string=render_template('medicine_report.html', medicines=medicines)))

@app.route('/billing', methods=['GET', 'POST'])
def billing():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    
    if request.method == 'POST':
        try:
            customer_name = request.form.get('customer_name')
            customer_phone = request.form.get('customer_phone')
            payment_method = request.form.get('payment_method', 'Cash')
            discount = float(request.form.get('discount', 0))
            prescription_notes = request.form.get('prescription_notes', '')  # Capture prescription notes
            
            cart_items_json = request.form.get('cart_items')
            if not cart_items_json:
                flash('No items in the bill!', 'danger')
                return redirect(url_for('billing'))
            
            cart_items = json.loads(cart_items_json)
            subtotal = sum(item['total'] for item in cart_items)
            
            # Calculate tax (assuming a fixed tax rate of 18%)
            TAX_RATE = 0.18
            tax = subtotal * TAX_RATE  # Calculate tax based on subtotal
            
            # Calculate grand total
            grand_total = subtotal + tax - discount
            
            # Check if the customer already exists
            customer_id = None
            if customer_name:
                cur.execute("""SELECT id FROM customers WHERE name = %s AND phone = %s""", (customer_name, customer_phone))
                customer = cur.fetchone()
                
                if customer:
                    customer_id = customer['id']  # Get the existing customer ID
                else:
                    # If the customer does not exist, create a new record
                    if customer_phone:  # Only create a new customer if phone number is provided
                        cur.execute("""INSERT INTO customers (name, phone) VALUES (%s, %s)""", (customer_name, customer_phone))
                        customer_id = cur.lastrowid  # Get the ID of the newly created customer
                    else:
                        flash('Customer does not exist. Please provide a phone number to create a new customer record.', 'danger')
                        return redirect(url_for('billing'))
            
            # Generate a unique bill number
            bill_number = 'BIL' + ''.join(random.choices(string.digits, k=6))
            
            # Insert the bill into the bills table, including prescription notes
            cur.execute("""INSERT INTO bills (customer_id, bill_number, bill_date, total_amount, discount, tax, grand_total, payment_method, prescription_notes)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                           (customer_id, bill_number, datetime.now().date(), subtotal, discount, tax, grand_total, payment_method, prescription_notes))
            bill_id = cur.lastrowid
            
            # Insert bill items
            for item in cart_items:
                cur.execute("""INSERT INTO bill_items (bill_id, medicine_id, quantity, price, amount, expiry_date)
                               VALUES (%s, %s, %s, %s, %s, %s)""", 
                               (bill_id, item['id'], item['quantity'], item['price'], item['total'], item['expiry_date']))
                
                # Update medicine quantity
                cur.execute("""UPDATE medicines SET quantity = quantity - %s WHERE id = %s""", (item['quantity'], item['id']))
            
            # Commit the changes
            mysql.connection.commit()
            flash(f'Bill #{bill_number} created successfully!', 'success')
            return redirect(url_for('view_bill', bill_id=bill_id))
        
        except Exception as e:
            mysql.connection.rollback()  # Rollback in case of error
            flash(f'Error creating bill: {str(e)}', 'danger')
            return redirect(url_for('billing'))
        finally:
            cur.close()  # Ensure cursor is closed

    # Fetch medicines from the database
    cur.execute("SELECT id, name, price, quantity, expiry_date FROM medicines WHERE quantity > 0 ORDER BY name")
    medicines = cur.fetchall()
    cur.close()
    
    today = datetime.now().date()  # Get today's date
    return render_template('billing.html', medicines=medicines, today=today)

@app.route('/bills')
def bills():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("""SELECT b.id, b.bill_number, b.bill_date, b.grand_total, c.name as customer_name
                   FROM bills b LEFT JOIN customers c ON b.customer_id = c.id
                   ORDER by b.bill_date DESC""")
    bills = cur.fetchall()
    cur.close()
    
    return render_template('bills.html', bills=bills)

@app.route('/bill/<int:bill_id>')
def view_bill(bill_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    
    # Fetch the bill and customer details
    cur.execute("""
        SELECT b.*, c.name AS customer_name, c.phone AS customer_phone
        FROM bills b
        LEFT JOIN customers c ON b.customer_id = c.id
        WHERE b.id = %s
    """, (bill_id,))
    bill = cur.fetchone()

    if not bill:
        flash('Bill not found!', 'danger')
        return redirect(url_for('bills'))
    
    # Fetch the bill items
    cur.execute("""
        SELECT bi.*, m.name AS medicine_name
        FROM bill_items bi
        JOIN medicines m ON bi.medicine_id = m.id
        WHERE bi.bill_id = %s
    """, (bill_id,))
    items = cur.fetchall()
    
    cur.close()
    
    return render_template('view_bill.html', bill=bill, items=items)

@app.route('/delete_bill/<int:bill_id>', methods=['POST'])
def delete_bill(bill_id):
    cur = mysql.connection.cursor()
    
    # First, delete all items associated with the bill
    cur.execute("DELETE FROM bill_items WHERE bill_id = %s", (bill_id,))
    
    # Now, delete the bill itself
    cur.execute("DELETE FROM bills WHERE id = %s", (bill_id,))
    mysql.connection.commit()
    cur.close()
    
    flash('Bill deleted successfully!', 'success')
    return redirect(url_for('bills'))

# API Endpoints
@app.route('/api/medicines')
def api_medicines():
    if 'logged_in' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    search = request.args.get('search', '')
    cur = mysql.connection.cursor()
    query = "SELECT id, name, price, quantity FROM medicines WHERE quantity > 0"
    params = []
    
    if search:
        query += " AND name LIKE %s"
        params.append(f"%{search}%")
    
    query += " ORDER BY name LIMIT 10"
    cur.execute(query, params)
    medicines = cur.fetchall()
    cur.close()
    
    return jsonify(medicines)

if __name__ == '__main__':
    app.secret_key = Config.SECRET_KEY
    app.run(debug=True)