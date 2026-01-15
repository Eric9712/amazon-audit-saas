@echo off
echo ============================================
echo   Amazon Audit SaaS - Setup Script
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python n'est pas installe ou n'est pas dans le PATH
    exit /b 1
)

REM Create virtual environment
if not exist "venv" (
    echo [1/6] Creation de l'environnement virtuel...
    python -m venv venv
)

REM Activate virtual environment
echo [2/6] Activation de l'environnement virtuel...
call venv\Scripts\activate.bat

REM Install dependencies
echo [3/6] Installation des dependances...
pip install -r requirements.txt -q

REM Copy .env if not exists
if not exist ".env" (
    echo [4/6] Copie du fichier .env.example vers .env...
    copy .env.example .env
    echo [WARNING] N'oubliez pas de configurer le fichier .env avec vos cles API!
) else (
    echo [4/6] Fichier .env deja present
)

REM Run migrations
echo [5/6] Execution des migrations...
python manage.py migrate

REM Collect static
echo [6/6] Collection des fichiers statiques...
python manage.py collectstatic --noinput

echo.
echo ============================================
echo   Installation terminee!
echo ============================================
echo.
echo Pour lancer le serveur de developpement:
echo   python manage.py runserver
echo.
echo Pour creer un superuser:
echo   python manage.py createsuperuser
echo.
echo Pour lancer Celery (dans un autre terminal):
echo   celery -A config.celery worker -l INFO
echo.
