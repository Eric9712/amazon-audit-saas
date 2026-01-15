# Guide de Déploiement sur Render.com (Gratuit)

Ce guide vous explique comment mettre votre application SaaS Amazon Audit en ligne gratuitement pour que des visiteurs puissent la voir.

## Prérequis

1.  Un compte **GitHub** (https://github.com)
2.  Un compte **Render** (https://render.com)
3.  Le code du projet prêt (ce qui est le cas maintenant)

---

## Étape 1 : Mettre le code sur GitHub

Si ce n'est pas déjà fait, vous devez versionner votre code et l'envoyer sur GitHub.

1.  **Initialiser Git** (si pas déjà fait) :
    Ouvrez un terminal dans le dossier du projet et lancez :

    ```bash
    git init
    git add .
    git commit -m "Prêt pour déploiement"
    ```

2.  **Créer un repository sur GitHub** :

    - Allez sur GitHub -> New Repository
    - Donnez-lui un nom (ex: `amazon-audit-saas`)
    - Ne cochez rien (pas de README, pas de license)
    - Cliquez sur **Create repository**

3.  **Lier et envoyer le code** :
    Copiez les commandes affichées par GitHub (section "...or push an existing repository from the command line") et lancez-les dans votre terminal. Cela ressemble à :
    ```bash
    git remote add origin https://github.com/VOTRE_NOM/amazon-audit-saas.git
    git branch -M main
    git push -u origin main
    ```

---

## Étape 2 : Créer la Base de Données sur Render

1.  Connectez-vous sur [Render Dashboard](https://dashboard.render.com).
2.  Cliquez sur **New +** -> **PostgreSQL**.
3.  **Name** : `amazon-saas-db` (ou ce que vous voulez).
4.  **Database** : Laissez le nom généré.
5.  **User** : Laissez le nom généré.
6.  **Region** : Choisissez `Frankfurt` (ou le plus proche de la France).
7.  **Instance Type** : Sélectionnez **Free**.
8.  Cliquez sur **Create Database**.
9.  **IMPORTANT** : Une fois créée, copiez l'URL appelée **"Internal Database URL"** (visible dans les détails de la BDD). Nous en aurons besoin.

---

## Étape 3 : Créer le Serveur Web sur Render

1.  Sur le Dashboard, cliquez sur **New +** -> **Web Service**.
2.  Sélectionnez **Build and deploy from a Git repository**.
3.  Connectez votre compte GitHub et choisissez le repo `amazon-audit-saas`.
4.  **Name** : `amazon-audit-demo` (ce sera l'adresse : `amazon-audit-demo.onrender.com`).
5.  **Region** : Choisissez la même que la BDD (ex: `Frankfurt`).
6.  **Branch** : `main`.
7.  **Runtime** : `Python 3`.
8.  **Build Command** : `./build.sh`
9.  **Start Command** : `gunicorn config.wsgi:application --log-file -`
10. **Instance Type** : Sélectionnez **Free**.

---

## Étape 4 : Configurer les Variables d'Environnement

Avant de lancer la création, descendez à la section **Environment Variables** et cliquez sur **Add Environment Variable**. Ajoutez les clés suivantes :

| Key                      | Value                                                         |
| ------------------------ | ------------------------------------------------------------- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.production`                                  |
| `SECRET_KEY`             | Générez une clé aléatoire longue (ex: `django-insecure-....`) |
| `DATABASE_URL`           | L'URL **Internal Database URL** copiée à l'étape 2            |
| `PYTHON_VERSION`         | `3.11.4`                                                      |
| `AMAZON_USE_SANDBOX`     | `True` (pour garder le mode test en ligne)                    |
| `STRIPE_SECRET_KEY`      | `sk_test_...` (votre clé Stripe de test)                      |
| `STRIPE_WEBHOOK_SECRET`  | `whsec_...` (votre secret webhook)                            |
| `STRIPE_PUBLIC_KEY`      | `pk_test_...`                                                 |

_Note : Pour lancer juste une démo visuelle, les clés Stripe sont optionnelles si vous n'allez pas sur la page de paiement, mais l'app plantera au démarrage si elles manquent dans la config. Mettez des valeurs bidons (ex: `sk_test_dummy`) si vous ne voulez pas tester les paiements._

---

## Étape 5 : Lancer le Déploiement

1.  Cliquez sur **Create Web Service**.
2.  Render va cloner votre code, installer les dépendances (pip install), et lancer les migrations BDD (grâce au script `build.sh`).
3.  Cela peut prendre 3-5 minutes la première fois.
4.  Une fois terminé, vous verrez un badge vert **Live**.

Votre site sera accessible à l'adresse : `https://VOTRE-NOM-SERVICE.onrender.com`

## Problèmes Courants

- **Page blanche / CSS manquant** : Vérifiez que `whitenoise` est bien activé (vérifier les logs de déploiement).
- **Erreur Serveur (500)** : Vérifiez les variables d'environnement (Secret Key, Database URL).
- **Erreur de Build** : Vérifiez que `requirements.txt` est bien à la racine.

---

**Besoin d'aide ?** Consultez les logs dans l'onglet "Logs" de votre service Render pour voir ce qui ne va pas.
