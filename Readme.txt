Overview:
Ganesh Medicals is a web application designed for managing a medical shop. It allows users to handle medicines, create bills, and manage customer information efficiently.

Features:
User Authentication: Admin login to manage the application.
Medicine Management: Add, edit, and delete medicines.
Billing System: Create and manage bills for customers.
Customer Management: Store and retrieve customer details.
Reports: Generate PDF reports for medicines.
Dashboard: View statistics on medicines and recent bills.

Technologies Used:
Frontend: HTML, CSS, JavaScript (jQuery)
Backend: Python (Flask)
Database: MySQL
Email Notifications: Flask-Mail
PDF Generation: Flask-WeasyPrint
Task Scheduling: APScheduler
Installation
Clone the repository: git clone <repository-url> cd ganesh-medicals

Set up a virtual environment (optional but recommended): python -m venv venv source venv/bin/activate # On Windows use venv\Scripts\activate

Install the required packages: pip install -r requirements.txt

Set up the database:

Update the database configuration in config.py with your MySQL credentials.
Run the database.py script to initialize the database.
Run the application: python app.py

Access the application: Open your web browser and go to http://localhost:8080.

Usage
Login: Use the admin credentials to log in.
Manage Medicines: Add new medicines, edit existing ones, or delete them.
Create Bills: Add medicines to the cart and generate bills for customers.
View Reports: Generate and view reports for medicines.
Contributing
Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.

License
This project is licensed under the MIT License - see the LICENSE file for details.

Contact
For any inquiries, please contact:

Email: info@ganeshmedicals.com
Phone: +91 95857 76807