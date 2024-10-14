CREATE DATABASE employee_task_db;

USE employee_task_db;

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('Manager', 'Employee') NOT NULL
);



CREATE TABLE tasks (
    task_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    assigned_to VARCHAR(255) NOT NULL,
    status ENUM('Pending', 'Completed') DEFAULT 'Pending'
);


ALTER TABLE tasks
ADD COLUMN deadline DATE;

ALTER TABLE tasks ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;


ALTER TABLE users
ADD COLUMN email VARCHAR(255) NOT NULL;
