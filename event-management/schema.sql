-- =====================================================
-- Event Planning and Management System Database Schema
-- =====================================================

CREATE DATABASE IF NOT EXISTS event_management;
USE event_management;

-- ------------------------
-- 1. Organizer Management
-- ------------------------
CREATE TABLE IF NOT EXISTS organizers (
    organizer_id INT AUTO_INCREMENT PRIMARY KEY,
    organizer_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE
);

-- -------------------
-- 2. Venue Management
-- -------------------
CREATE TABLE IF NOT EXISTS venues (
    venue_id INT AUTO_INCREMENT PRIMARY KEY,
    venue_name VARCHAR(120) NOT NULL,
    location VARCHAR(150) NOT NULL,
    capacity INT NOT NULL,
    UNIQUE KEY uq_venue_location (venue_name, location)
);

-- -------------------
-- 3. Event Management
-- -------------------
CREATE TABLE IF NOT EXISTS events (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    event_name VARCHAR(150) NOT NULL,
    event_date DATE NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    venue_id INT NOT NULL,
    organizer_id INT NOT NULL,
    UNIQUE KEY uq_event_name_date (event_name, event_date),
    CONSTRAINT fk_events_venue
        FOREIGN KEY (venue_id) REFERENCES venues(venue_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_events_organizer
        FOREIGN KEY (organizer_id) REFERENCES organizers(organizer_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- --------------------------
-- 4. Participant Management
-- --------------------------
CREATE TABLE IF NOT EXISTS participants (
    participant_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    department VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    event_id INT NOT NULL,
    CONSTRAINT fk_participants_event
        FOREIGN KEY (event_id) REFERENCES events(event_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- -----------------------
-- 5. Registration Module
-- -----------------------
CREATE TABLE IF NOT EXISTS registrations (
    registration_id INT AUTO_INCREMENT PRIMARY KEY,
    participant_id INT NOT NULL,
    event_id INT NOT NULL,
    registration_date DATE NOT NULL,
    registration_fee DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    payment_status ENUM('Pending', 'Paid', 'Failed') NOT NULL DEFAULT 'Pending',
    CONSTRAINT fk_registrations_participant
        FOREIGN KEY (participant_id) REFERENCES participants(participant_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_registrations_event
        FOREIGN KEY (event_id) REFERENCES events(event_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

-- -------------------------
-- 6. Budget/Payment Module
-- -------------------------
CREATE TABLE IF NOT EXISTS payments (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    participant_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_date DATE NOT NULL,
    payment_status ENUM('Pending', 'Paid', 'Failed') NOT NULL DEFAULT 'Pending',
    CONSTRAINT fk_payments_participant
        FOREIGN KEY (participant_id) REFERENCES participants(participant_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);

-- ============================
-- Sample Dummy Data for Demo
-- ============================

INSERT INTO organizers (organizer_name, phone) VALUES
('Technical Club', '9876543210'),
('Cultural Committee', '9123456780'),
('Sports Department', '9988776655');

INSERT INTO venues (venue_name, location, capacity) VALUES
('Main Auditorium', 'Block A', 500),
('Seminar Hall', 'Block C', 150),
('Open Ground', 'North Campus', 1000);

INSERT INTO events (event_name, event_date, event_type, venue_id, organizer_id) VALUES
('Tech Symposium 2026', '2026-05-15', 'Technical', 1, 1),
('Cultural Fest', '2026-06-10', 'Cultural', 3, 2),
('Inter-College Sports Meet', '2026-07-05', 'Sports', 3, 3);

INSERT INTO participants (name, email, department, phone, event_id) VALUES
('Aarav Sharma', 'aarav.sharma@example.com', 'Computer Science', '9000011111', 1),
('Nisha Reddy', 'nisha.reddy@example.com', 'Electronics', '9000022222', 1),
('Rahul Verma', 'rahul.verma@example.com', 'Mechanical', '9000033333', 2),
('Sneha Iyer', 'sneha.iyer@example.com', 'Civil', '9000044444', 3);

INSERT INTO registrations (participant_id, event_id, registration_date, registration_fee, payment_status) VALUES
(1, 1, '2026-04-01', 500.00, 'Paid'),
(2, 1, '2026-04-02', 500.00, 'Pending'),
(3, 2, '2026-04-04', 300.00, 'Paid'),
(4, 3, '2026-04-06', 400.00, 'Paid');

INSERT INTO payments (participant_id, amount, payment_date, payment_status) VALUES
(1, 500.00, '2026-04-03', 'Paid'),
(2, 500.00, '2026-04-04', 'Pending'),
(3, 300.00, '2026-04-05', 'Paid'),
(4, 400.00, '2026-04-07', 'Paid');
