# Event Planning and Management System

A web-based application developed using **Flask**, **MySQL**, and **HTML/CSS/JavaScript** to efficiently manage events, participants, organizers, venues, and payments within an organization.

---

## 📌 Project Overview

The Event Planning and Management System is designed to automate and simplify event management processes. It provides a centralized platform to handle event scheduling, participant registrations, venue bookings, and payment tracking.

---

## 🚀 Features

* Event creation, update, and deletion (CRUD)
* Organizer management
* Participant registration
* Venue management
* Payment tracking
* Dashboard with summary statistics
* Relational database with foreign key constraints

---

## 🛠️ Tech Stack

* **Frontend:** HTML, CSS, JavaScript
* **Backend:** Flask (Python)
* **Database:** MySQL
* **Query Language:** SQL

---

## 📂 Project Structure

event-management/
│
├── app.py
├── config.py
├── requirements.txt
├── schema.sql
│
├── templates/
│   ├── index.html
│   ├── dashboard.html
│   ├── events.html
│   ├── participants.html
│   ├── venues.html
│   ├── organizers.html
│   └── payments.html
│
├── static/
│   ├── style.css
│   └── script.js

---

## ⚙️ Setup Instructions

### 1. Clone or Download the Project

Download the project folder and open it in your terminal.

---

### 2. Navigate to Project Directory

```bash
cd "/d/EVENT MANAGEMENT SYSTEM/event-management"
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Setup MySQL Database

Open MySQL Workbench or MySQL CLI and run:

```sql
SOURCE "D:/EVENT MANAGEMENT SYSTEM/event-management/schema.sql";
```

This will:

* Create database
* Create tables
* Insert sample data

---

### 5. Configure Database Connection

Edit `config.py`:

```python
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = "your_password"
DB_NAME = "event_management"
```

---

### 6. Run the Application

```bash
python app.py
```

---

### 7. Open in Browser

```
http://127.0.0.1:5000
```

---

## 🗄️ Database Design

The system includes the following tables:

* organizers
* venues
* events
* participants
* registrations
* payments

Key DBMS concepts used:

* Primary Keys
* Foreign Keys
* Constraints
* Normalization
* Relationships (One-to-Many)

---

## 📊 Sample Functionalities

* Add and manage events
* Register participants for events
* Assign venues and organizers
* Track payments and registrations
* View dashboard analytics

---

## 🔮 Future Enhancements

* User authentication system
* Email notifications
* QR-based event entry
* Online payment integration
* Advanced reporting dashboard

---

## 👨‍💻 Author

**M.V Srujan**
B.Tech CSE
SRM University – AP

---

## 📄 License

This project is developed for academic purposes.
