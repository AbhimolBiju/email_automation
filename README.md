**Project Setup Plan**

**Goal Description**
Complete the base Django backend setup by initializing the git repository, creating a standard README and .gitignore, setting up a virtual environment, installing dependencies, applying migrations, and verifying that the project runs successfully.


**Proposed Changes**
Project Root
README.md
Add project documentation and setup instructions for other developers.



# Promise CRM Backend

This is the backend component for the "Promise Insurance Services" portal, built with Django and Django REST Framework.

## Features
- Django 6.0 Backend
- Django REST Framework (DRF)
- CORS headers configured for React frontend integration
- SQLite Database

## Requirements
- Python 3.10+

## Local Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd promise_crm_backend-main/promise_crm_backend-main
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run database migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Start the development server:**
   ```bash
   python manage.py runserver
   ```
   The API will be available at `http://localhost:8000/`.

## Endpoints
- The main API endpoints will be served from the `api` app.

## Contributing
- Ensure that you activate your virtual environment before adding new dependencies.
- Update `requirements.txt` using `pip freeze > requirements.txt` when installing new packages.
