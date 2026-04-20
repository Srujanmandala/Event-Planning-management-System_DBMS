from functools import wraps
from io import BytesIO

from flask import Flask, flash, redirect, render_template, request, session, url_for, send_file
import mysql.connector
from mysql.connector import Error
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from config import DB_CONFIG, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY

USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "user": {"password": "user123", "role": "user"},
}


def get_db_connection():
    """Create and return a MySQL connection."""
    return mysql.connector.connect(**DB_CONFIG)


def column_exists(table_name, column_name):
    """Check whether a column exists in the active database."""
    row = fetch_one(
        """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        LIMIT 1
        """,
        (DB_CONFIG["database"], table_name, column_name),
    )
    return row is not None


def ensure_schema_updates():
    """
    Apply minimal schema updates required by the current code.
    This keeps old databases compatible without full reset.
    """
    # participants.email
    if not column_exists("participants", "email"):
        execute_query("ALTER TABLE participants ADD COLUMN email VARCHAR(120) NULL AFTER name")
        execute_query(
            """
            UPDATE participants
            SET email = CONCAT('participant', participant_id, '@example.com')
            WHERE email IS NULL OR email = ''
            """
        )
        execute_query("ALTER TABLE participants MODIFY COLUMN email VARCHAR(120) NOT NULL")

    # registrations fields
    if not column_exists("registrations", "registration_fee"):
        execute_query(
            """
            ALTER TABLE registrations
            ADD COLUMN registration_fee DECIMAL(10,2) NOT NULL DEFAULT 0.00
            AFTER registration_date
            """
        )
    if not column_exists("registrations", "payment_status"):
        execute_query(
            """
            ALTER TABLE registrations
            ADD COLUMN payment_status ENUM('Pending','Paid','Failed') NOT NULL DEFAULT 'Pending'
            AFTER registration_fee
            """
        )

    # payments enum compatibility: allow both values, migrate data, then tighten enum.
    try:
        execute_query(
            """
            ALTER TABLE payments
            MODIFY COLUMN payment_status ENUM('Pending','Completed','Paid','Failed') NOT NULL DEFAULT 'Pending'
            """
        )
    except Error:
        pass
    execute_query("UPDATE payments SET payment_status = 'Paid' WHERE payment_status = 'Completed'")
    try:
        execute_query(
            """
            ALTER TABLE payments
            MODIFY COLUMN payment_status ENUM('Pending','Paid','Failed') NOT NULL DEFAULT 'Pending'
            """
        )
    except Error:
        pass

    # Add uniqueness constraints only if missing.
    try:
        execute_query("ALTER TABLE participants ADD UNIQUE KEY uq_participant_email (email)")
    except Error:
        pass
    try:
        execute_query("ALTER TABLE organizers ADD UNIQUE KEY uq_organizer_phone (phone)")
    except Error:
        pass
    try:
        execute_query("ALTER TABLE events ADD UNIQUE KEY uq_event_name_date (event_name, event_date)")
    except Error:
        pass
    try:
        execute_query("ALTER TABLE venues ADD UNIQUE KEY uq_venue_location (venue_name, location)")
    except Error:
        pass


def fetch_all(query, params=None):
    """Execute SELECT query and return all rows as dictionaries."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(query, params or ())
    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    return rows


def fetch_one(query, params=None):
    """Execute SELECT query and return one row as dictionary."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute(query, params or ())
    row = cursor.fetchone()
    cursor.close()
    connection.close()
    return row


def execute_query(query, params=None):
    """Execute INSERT/UPDATE/DELETE query with safe transaction handling."""
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(query, params or ())
        connection.commit()
    except Error:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


# Ensure compatibility even when app is started via `flask run`.
try:
    ensure_schema_updates()
except Error as schema_error:
    print(f"Schema update warning: {schema_error}")


def duplicate_exists(query, params=None):
    """Return True if duplicate record is found."""
    return fetch_one(query, params) is not None


def has_paid_access(participant_id):
    """Participant access requires payment_status = Paid."""
    paid_record = fetch_one(
        """
        SELECT payment_id FROM payments
        WHERE participant_id = %s AND payment_status IN ('Paid', 'Completed')
        LIMIT 1
        """,
        (participant_id,),
    )
    return paid_record is not None


def login_required(route_fn):
    """Protect routes and allow access only for logged-in users."""
    @wraps(route_fn)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            flash("Please login first.", "error")
            return redirect(url_for("login"))
        return route_fn(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_user_context():
    return {
        "is_logged_in": "username" in session,
        "current_username": session.get("username"),
        "current_role": session.get("role"),
    }


@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = USERS.get(username)
        if user and user["password"] == password:
            session["username"] = username
            session["role"] = user["role"]
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    counts = {
        "events": fetch_one("SELECT COUNT(*) AS total FROM events")["total"],
        "participants": fetch_one("SELECT COUNT(*) AS total FROM participants")["total"],
        "organizers": fetch_one("SELECT COUNT(*) AS total FROM organizers")["total"],
        "venues": fetch_one("SELECT COUNT(*) AS total FROM venues")["total"],
        "payments": fetch_one("SELECT COUNT(*) AS total FROM payments")["total"],
    }
    return render_template("dashboard.html", counts=counts)


@app.route("/events")
@login_required
def events():
    all_events = fetch_all(
        """
        SELECT e.event_id, e.event_name, e.event_date, e.event_type,
               v.venue_name, o.organizer_name
        FROM events e
        JOIN venues v ON e.venue_id = v.venue_id
        JOIN organizers o ON e.organizer_id = o.organizer_id
        ORDER BY e.event_date ASC
        """
    )
    venues_data = fetch_all("SELECT venue_id, venue_name FROM venues ORDER BY venue_name")
    organizers_data = fetch_all(
        "SELECT organizer_id, organizer_name FROM organizers ORDER BY organizer_name"
    )

    event_to_edit = None
    edit_id = request.args.get("edit_id")
    if edit_id:
        event_to_edit = fetch_one("SELECT * FROM events WHERE event_id = %s", (edit_id,))

    return render_template(
        "events.html",
        events=all_events,
        venues=venues_data,
        organizers=organizers_data,
        event_to_edit=event_to_edit,
    )


@app.route("/add_event", methods=["POST"])
@login_required
def add_event():
    form = request.form
    if duplicate_exists(
        """
        SELECT event_id FROM events
        WHERE event_name = %s AND event_date = %s
        LIMIT 1
        """,
        (form["event_name"], form["event_date"]),
    ):
        flash("Duplicate record: event name with this date already exists.", "error")
        return redirect(url_for("events"))

    execute_query(
        """
        INSERT INTO events (event_name, event_date, event_type, venue_id, organizer_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            form["event_name"],
            form["event_date"],
            form["event_type"],
            form["venue_id"],
            form["organizer_id"],
        ),
    )
    flash("Event added successfully.", "success")
    return redirect(url_for("events"))


@app.route("/edit_event/<int:event_id>", methods=["GET", "POST"])
@login_required
def edit_event(event_id):
    if request.method == "POST":
        form = request.form
        if duplicate_exists(
            """
            SELECT event_id FROM events
            WHERE event_name = %s AND event_date = %s AND event_id != %s
            LIMIT 1
            """,
            (form["event_name"], form["event_date"], event_id),
        ):
            flash("Duplicate record: event name with this date already exists.", "error")
            return redirect(url_for("events", edit_id=event_id))

        execute_query(
            """
            UPDATE events
            SET event_name = %s, event_date = %s, event_type = %s, venue_id = %s, organizer_id = %s
            WHERE event_id = %s
            """,
            (
                form["event_name"],
                form["event_date"],
                form["event_type"],
                form["venue_id"],
                form["organizer_id"],
                event_id,
            ),
        )
        flash("Event updated successfully.", "success")
        return redirect(url_for("events"))

    return redirect(url_for("events", edit_id=event_id))


@app.route("/delete_event/<int:event_id>", methods=["POST"])
@login_required
def delete_event(event_id):
    try:
        execute_query("DELETE FROM events WHERE event_id = %s", (event_id,))
        flash("Event deleted successfully.", "success")
    except Error:
        flash(
            "Cannot delete event because it is linked with participants or registrations.",
            "error",
        )
    return redirect(url_for("events"))


@app.route("/organizers", methods=["GET", "POST"])
@login_required
def organizers():
    if request.method == "POST":
        organizer_id = request.form.get("organizer_id")
        duplicate_query = "SELECT organizer_id FROM organizers WHERE phone = %s"
        duplicate_params = (request.form["phone"],)
        if organizer_id:
            duplicate_query += " AND organizer_id != %s"
            duplicate_params = (request.form["phone"], organizer_id)
        duplicate_query += " LIMIT 1"

        if duplicate_exists(duplicate_query, duplicate_params):
            flash("Duplicate record: organizer phone must be unique.", "error")
            return redirect(
                url_for("organizers", edit_id=organizer_id) if organizer_id else url_for("organizers")
            )

        if organizer_id:
            execute_query(
                "UPDATE organizers SET organizer_name = %s, phone = %s WHERE organizer_id = %s",
                (request.form["organizer_name"], request.form["phone"], organizer_id),
            )
            flash("Organizer updated successfully.", "success")
        else:
            execute_query(
                "INSERT INTO organizers (organizer_name, phone) VALUES (%s, %s)",
                (request.form["organizer_name"], request.form["phone"]),
            )
            flash("Organizer added successfully.", "success")
        return redirect(url_for("organizers"))

    organizer_to_edit = None
    edit_id = request.args.get("edit_id")
    if edit_id:
        organizer_to_edit = fetch_one(
            "SELECT * FROM organizers WHERE organizer_id = %s", (edit_id,)
        )

    organizers_data = fetch_all("SELECT * FROM organizers ORDER BY organizer_name")
    return render_template(
        "organizers.html", organizers=organizers_data, organizer_to_edit=organizer_to_edit
    )


@app.route("/delete_organizer/<int:organizer_id>", methods=["POST"])
@login_required
def delete_organizer(organizer_id):
    try:
        execute_query("DELETE FROM organizers WHERE organizer_id = %s", (organizer_id,))
        flash("Organizer deleted successfully.", "success")
    except Error:
        flash(
            "Cannot delete organizer because it is linked with existing events.",
            "error",
        )
    return redirect(url_for("organizers"))


@app.route("/venues", methods=["GET", "POST"])
@login_required
def venues():
    if request.method == "POST":
        venue_id = request.form.get("venue_id")
        duplicate_query = "SELECT venue_id FROM venues WHERE venue_name = %s AND location = %s"
        duplicate_params = (request.form["venue_name"], request.form["location"])
        if venue_id:
            duplicate_query += " AND venue_id != %s"
            duplicate_params = (
                request.form["venue_name"],
                request.form["location"],
                venue_id,
            )
        duplicate_query += " LIMIT 1"

        if duplicate_exists(duplicate_query, duplicate_params):
            flash("Duplicate record: venue name with this location already exists.", "error")
            return redirect(url_for("venues", edit_id=venue_id) if venue_id else url_for("venues"))

        if venue_id:
            execute_query(
                """
                UPDATE venues
                SET venue_name = %s, location = %s, capacity = %s
                WHERE venue_id = %s
                """,
                (
                    request.form["venue_name"],
                    request.form["location"],
                    request.form["capacity"],
                    venue_id,
                ),
            )
            flash("Venue updated successfully.", "success")
        else:
            execute_query(
                "INSERT INTO venues (venue_name, location, capacity) VALUES (%s, %s, %s)",
                (
                    request.form["venue_name"],
                    request.form["location"],
                    request.form["capacity"],
                ),
            )
            flash("Venue added successfully.", "success")
        return redirect(url_for("venues"))

    venue_to_edit = None
    edit_id = request.args.get("edit_id")
    if edit_id:
        venue_to_edit = fetch_one("SELECT * FROM venues WHERE venue_id = %s", (edit_id,))

    venues_data = fetch_all("SELECT * FROM venues ORDER BY venue_name")
    return render_template("venues.html", venues=venues_data, venue_to_edit=venue_to_edit)


@app.route("/delete_venue/<int:venue_id>", methods=["POST"])
@login_required
def delete_venue(venue_id):
    try:
        execute_query("DELETE FROM venues WHERE venue_id = %s", (venue_id,))
        flash("Venue deleted successfully.", "success")
    except Error:
        flash(
            "Cannot delete venue because it is linked with existing events.",
            "error",
        )
    return redirect(url_for("venues"))


@app.route("/participants", methods=["GET", "POST"])
@login_required
def participants():
    if request.method == "POST":
        participant_id = request.form.get("participant_id")
        duplicate_query = "SELECT participant_id FROM participants WHERE email = %s"
        duplicate_params = (request.form["email"],)
        if participant_id:
            duplicate_query += " AND participant_id != %s"
            duplicate_params = (request.form["email"], participant_id)
        duplicate_query += " LIMIT 1"

        if duplicate_exists(duplicate_query, duplicate_params):
            flash("Duplicate record: participant email must be unique.", "error")
            return redirect(
                url_for("participants", edit_id=participant_id)
                if participant_id
                else url_for("participants")
            )

        if participant_id:
            execute_query(
                """
                UPDATE participants
                SET name = %s, email = %s, department = %s, phone = %s, event_id = %s
                WHERE participant_id = %s
                """,
                (
                    request.form["name"],
                    request.form["email"],
                    request.form["department"],
                    request.form["phone"],
                    request.form["event_id"],
                    participant_id,
                ),
            )
            flash("Participant updated successfully.", "success")
        else:
            execute_query(
                """
                INSERT INTO participants (name, email, department, phone, event_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    request.form["name"],
                    request.form["email"],
                    request.form["department"],
                    request.form["phone"],
                    request.form["event_id"],
                ),
            )
            flash("Participant added successfully.", "success")
        return redirect(url_for("participants"))

    participant_to_edit = None
    edit_id = request.args.get("edit_id")
    if edit_id:
        participant_to_edit = fetch_one(
            "SELECT * FROM participants WHERE participant_id = %s", (edit_id,)
        )

    participants_data = fetch_all(
        """
        SELECT p.participant_id, p.name, p.email, p.department, p.phone, e.event_id, e.event_name,
               CASE
                   WHEN EXISTS (
                       SELECT 1 FROM payments pay
                       WHERE pay.participant_id = p.participant_id
                         AND pay.payment_status IN ('Paid', 'Completed')
                   ) THEN 'Paid'
                   ELSE 'Pending'
               END AS access_status
        FROM participants p
        JOIN events e ON p.event_id = e.event_id
        ORDER BY p.name
        """
    )
    events_data = fetch_all("SELECT event_id, event_name FROM events ORDER BY event_name")

    return render_template(
        "participants.html",
        participants=participants_data,
        events=events_data,
        participant_to_edit=participant_to_edit,
    )


@app.route("/delete_participant/<int:participant_id>", methods=["POST"])
@login_required
def delete_participant(participant_id):
    execute_query("DELETE FROM participants WHERE participant_id = %s", (participant_id,))
    flash("Participant deleted successfully.", "success")
    return redirect(url_for("participants"))


@app.route("/registrations", methods=["GET", "POST"])
@login_required
def registrations():
    is_user_view = session.get("role") == "user"
    participant_id = request.args.get("participant_id")

    if is_user_view and (not participant_id or not has_paid_access(participant_id)):
        flash("Please complete payment to access participation", "error")
        return redirect(url_for("participants"))

    if request.method == "POST":
        registration_id = request.form.get("registration_id")
        if registration_id:
            execute_query(
                """
                UPDATE registrations
                SET participant_id = %s, event_id = %s, registration_date = %s,
                    registration_fee = %s, payment_status = %s
                WHERE registration_id = %s
                """,
                (
                    request.form["participant_id"],
                    request.form["event_id"],
                    request.form["registration_date"],
                    request.form["registration_fee"],
                    request.form["payment_status"],
                    registration_id,
                ),
            )
            flash("Registration updated successfully.", "success")
        else:
            execute_query(
                """
                INSERT INTO registrations (participant_id, event_id, registration_date, registration_fee, payment_status)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    request.form["participant_id"],
                    request.form["event_id"],
                    request.form["registration_date"],
                    request.form["registration_fee"],
                    request.form["payment_status"],
                ),
            )
            flash("Registration added successfully.", "success")
        return redirect(url_for("registrations"))

    registration_to_edit = None
    edit_id = request.args.get("edit_id")
    if edit_id:
        registration_to_edit = fetch_one(
            "SELECT * FROM registrations WHERE registration_id = %s", (edit_id,)
        )

    registrations_data = fetch_all(
        """
        SELECT r.registration_id, r.registration_date, r.registration_fee, r.payment_status,
               p.participant_id, p.name AS participant_name, e.event_id, e.event_name
        FROM registrations r
        JOIN participants p ON r.participant_id = p.participant_id
        JOIN events e ON r.event_id = e.event_id
        ORDER BY r.registration_date DESC
        """
    )
    participants_data = fetch_all(
        "SELECT participant_id, name FROM participants ORDER BY name"
    )
    events_data = fetch_all("SELECT event_id, event_name FROM events ORDER BY event_name")

    return render_template(
        "registrations.html",
        registrations=registrations_data,
        participants=participants_data,
        events=events_data,
        registration_to_edit=registration_to_edit,
        is_user_view=is_user_view,
    )


@app.route("/delete_registration/<int:registration_id>", methods=["POST"])
@login_required
def delete_registration(registration_id):
    execute_query("DELETE FROM registrations WHERE registration_id = %s", (registration_id,))
    flash("Registration deleted successfully.", "success")
    return redirect(url_for("registrations"))


@app.route("/payments", methods=["GET", "POST"])
@login_required
def payments():
    if request.method == "POST":
        payment_id = request.form.get("payment_id")
        if payment_id:
            execute_query(
                """
                UPDATE payments
                SET participant_id = %s, amount = %s, payment_date = %s, payment_status = %s
                WHERE payment_id = %s
                """,
                (
                    request.form["participant_id"],
                    request.form["amount"],
                    request.form["payment_date"],
                    request.form["payment_status"],
                    payment_id,
                ),
            )
            flash("Payment updated successfully.", "success")
        else:
            execute_query(
                """
                INSERT INTO payments (participant_id, amount, payment_date, payment_status)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    request.form["participant_id"],
                    request.form["amount"],
                    request.form["payment_date"],
                    request.form["payment_status"],
                ),
            )
            flash("Payment added successfully.", "success")
        return redirect(url_for("payments"))

    payment_to_edit = None
    edit_id = request.args.get("edit_id")
    if edit_id:
        payment_to_edit = fetch_one("SELECT * FROM payments WHERE payment_id = %s", (edit_id,))

    payments_data = fetch_all(
        """
        SELECT pay.payment_id, pay.amount, pay.payment_date, pay.payment_status,
               p.participant_id, p.name AS participant_name, e.event_name
        FROM payments pay
        JOIN participants p ON pay.participant_id = p.participant_id
        JOIN events e ON p.event_id = e.event_id
        ORDER BY pay.payment_date DESC
        """
    )
    participants_data = fetch_all(
        "SELECT participant_id, name FROM participants ORDER BY name"
    )

    return render_template(
        "payments.html",
        payments=payments_data,
        participants=participants_data,
        payment_to_edit=payment_to_edit,
    )


@app.route("/delete_payment/<int:payment_id>", methods=["POST"])
@login_required
def delete_payment(payment_id):
    execute_query("DELETE FROM payments WHERE payment_id = %s", (payment_id,))
    flash("Payment deleted successfully.", "success")
    return redirect(url_for("payments"))


@app.route("/download_event_registrations_pdf/<int:event_id>")
@login_required
def download_event_registrations_pdf(event_id):
    event_data = fetch_one(
        "SELECT event_id, event_name, event_date FROM events WHERE event_id = %s",
        (event_id,),
    )
    if not event_data:
        flash("Event not found.", "error")
        return redirect(url_for("events"))

    registered_users = fetch_all(
        """
        SELECT p.participant_id, p.name, p.email, p.department, p.phone, r.registration_date
        FROM registrations r
        JOIN participants p ON r.participant_id = p.participant_id
        WHERE r.event_id = %s
        ORDER BY p.name
        """,
        (event_id,),
    )

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "Registered Users Report")
    y -= 22
    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, y, f"Event: {event_data['event_name']} ({event_data['event_date']})")
    y -= 20
    pdf.drawString(40, y, f"Total Registrations: {len(registered_users)}")
    y -= 24

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "ID")
    pdf.drawString(80, y, "Name")
    pdf.drawString(210, y, "Email")
    pdf.drawString(360, y, "Department")
    pdf.drawString(470, y, "Phone")
    y -= 14
    pdf.line(40, y, 560, y)
    y -= 12

    pdf.setFont("Helvetica", 9)
    for user in registered_users:
        if y < 50:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 9)
        pdf.drawString(40, y, str(user["participant_id"]))
        pdf.drawString(80, y, str(user["name"])[:22])
        pdf.drawString(210, y, str(user["email"])[:25])
        pdf.drawString(360, y, str(user["department"])[:16])
        pdf.drawString(470, y, str(user["phone"])[:12])
        y -= 14

    pdf.save()
    buffer.seek(0)

    filename = f"event_{event_id}_registered_users.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


if __name__ == "__main__":
    app.run(debug=True)
