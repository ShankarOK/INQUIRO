# Chatbot Project

Welcome to the Chatbot Project! This project implements a chatbot using Python and MySQL. Follow the instructions below to set up and run the project on your local machine.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Database Setup](#database-setup)
- [Running the Project](#running-the-project)
- [Usage](#usage)
- [License](#license)

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.x
- MySQL Server
- pip (Python package installer)

## Installation

1. **Download and open project in VS code, go to project directory**

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
     `if that didn't work ⬇️`
     ```bash
     .\venv\Scripts\activate
     ```

   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Download the spaCy language model**:
   ```bash
   python -m spacy download en_core_web_md
   ```

6. **Install PyMySQL**:
   ```bash
   pip install pymysql
   ```

## Database Setup

To set up the database, run the following command in your terminal:

```bash
mysql -u your_username -p your_database < path/to/chatbot_db.sql
```

Replace `your_username`, `your_database`, and `path/to/chatbot_db.sql` with your actual MySQL username, database name, and the path to your SQL file.

## Running the Project

After completing the setup, you can run the chatbot application with:

```bash
python inquiro.py
```

The application will start running on:

```
http://127.0.0.1:5000
```

To stop the server, press `CTRL+C` in your terminal.

## Usage

Once the server is running, open your web browser and navigate to `http://127.0.0.1:5000` to interact with the chatbot.