# Amazon Audit SaaS

Machine à Audit automatisée pour les vendeurs Amazon FBA.

## 🎯 Description

Ce SaaS analyse automatiquement 18 mois d'historique de données Amazon pour identifier l'argent perdu (stocks perdus, endommagés, non remboursés) et génère des dossiers de preuves prêts à l'emploi.

## 📋 Fonctionnalités

- ✅ **Audit gratuit** : L'analyse complète est 100% gratuite
- ✅ **Connexion sécurisée** : OAuth Amazon en lecture seule
- ✅ **Respect des règles** : Règle des 45 jours d'Amazon respectée
- ✅ **Idempotence** : Pas de doublons de réclamations
- ✅ **Dossiers complets** : Texte prêt à copier-coller

## 🛠️ Stack Technique

- **Backend**: Django 4.2, Django REST Framework
- **Base de données**: PostgreSQL
- **Tâches async**: Celery + Redis
- **Data Processing**: Pandas (opérations vectorisées)
- **API Amazon**: python-amazon-sp-api
- **Paiements**: Stripe
- **Authentification**: django-allauth

## 🚀 Installation

### Prérequis

- Python 3.10+
- PostgreSQL 15+
- Redis 7+

### Installation locale

```bash
# Cloner le repo
git clone <repo-url>
cd saas-remboursement-amazon

# Créer environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Installer dépendances
pip install -r requirements.txt

# Copier et configurer .env
cp .env.example .env
# Éditer .env avec vos clés

# Migrations
python manage.py migrate

# Créer superuser
python manage.py createsuperuser

# Lancer le serveur
python manage.py runserver
```

### Avec Docker

```bash
# Lancer tous les services
docker-compose up -d

# Migrations
docker-compose exec web python manage.py migrate

# Créer superuser
docker-compose exec web python manage.py createsuperuser
```

## ⚙️ Configuration

### Variables d'environnement requises

```
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://user:pass@localhost:5432/dbname
REDIS_URL=redis://localhost:6379/0

# Amazon SP-API
AMAZON_SP_API_LWA_APP_ID=amzn1.application-oa2-client.xxx
AMAZON_SP_API_LWA_CLIENT_SECRET=xxx

# Stripe
STRIPE_PUBLIC_KEY=pk_xxx
STRIPE_SECRET_KEY=sk_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

### Configuration Amazon Developer

1. Créer une application sur Amazon Seller Central > Developer
2. Configurer OAuth avec les scopes de lecture
3. Récupérer les credentials et les mettre dans .env

## 📁 Structure du projet

```
├── config/              # Configuration Django
│   ├── settings/        # Settings dev/prod
│   ├── celery.py        # Configuration Celery
│   └── urls.py          # URLs racine
├── apps/
│   ├── accounts/        # Gestion utilisateurs
│   ├── amazon_integration/  # API Amazon SP-API
│   ├── audit_engine/    # Moteur d'analyse
│   ├── payments/        # Stripe
│   └── dashboard/       # Interface utilisateur
├── templates/           # Templates HTML
├── static/              # CSS, JS
└── utils/               # Utilitaires
```

## 🔐 Règles Métier Importantes

1. **Règle des 45 jours**: On ignore les pertes de moins de 45 jours
2. **Idempotence**: Hash unique par perte pour éviter les doublons
3. **Lecture seule**: Aucune modification sur le compte Amazon
4. **Pas d'automatisation des tickets**: L'utilisateur soumet manuellement

## 📝 License

Propriétaire - Tous droits réservés
