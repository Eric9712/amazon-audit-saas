#!/bin/bash

echo "============================================"
echo "  Amazon Audit SaaS - Setup Script"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 n'est pas installé"
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "[1/6] Création de l'environnement virtuel..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "[2/6] Activation de l'environnement virtuel..."
source venv/bin/activate

# Install dependencies
echo "[3/6] Installation des dépendances..."
pip install -r requirements.txt -q

# Copy .env if not exists
if [ ! -f ".env" ]; then
    echo "[4/6] Copie du fichier .env.example vers .env..."
    cp .env.example .env
    echo "[WARNING] N'oubliez pas de configurer le fichier .env avec vos clés API!"
else
    echo "[4/6] Fichier .env déjà présent"
fi

# Run migrations
echo "[5/6] Exécution des migrations..."
python manage.py migrate

# Collect static
echo "[6/6] Collection des fichiers statiques..."
python manage.py collectstatic --noinput

echo ""
echo "============================================"
echo "  Installation terminée!"
echo "============================================"
echo ""
echo "Pour lancer le serveur de développement:"
echo "  python manage.py runserver"
echo ""
echo "Pour créer un superuser:"
echo "  python manage.py createsuperuser"
echo ""
echo "Pour lancer Celery (dans un autre terminal):"
echo "  celery -A config.celery worker -l INFO"
echo ""
