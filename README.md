# 🏠 ImmoTunisia — Django + React

Plateforme d'annonces immobilières basée sur les données **Mubawab** et **Tayara**.

---

## 📁 Structure du projet

```
immo_project/
├── backend/                   ← Django API
│   ├── manage.py
│   ├── requirements.txt
│   ├── immo_project/
│   │   ├── settings.py
│   │   └── urls.py
│   └── listings/
│       ├── models.py          ← Modèle Listing
│       ├── serializers.py     ← DRF Serializer
│       ├── views.py           ← API Views + filtres
│       ├── urls.py            ← Routes API
│       ├── admin.py
│       └── management/
│           └── commands/
│               └── seed_data.py   ← Import CSV
├── frontend/                  ← React App
│   ├── package.json
│   ├── public/index.html
│   └── src/
│       ├── App.jsx            ← Composant principal
│       ├── index.js
│       ├── index.css
│       ├── services/api.js    ← Appels API
│       └── components/
│           ├── Navbar.jsx
│           ├── Filters.jsx
│           ├── ListingCard.jsx
│           ├── ListingModal.jsx
│           ├── Pagination.jsx
│           └── StatsBar.jsx
└── data/
    ├── mubawab_data.csv       ← ⬅ METS TES CSV ICI
    └── tayara_data.csv        ← ⬅ METS TES CSV ICI
```

---

## ⚙️ Installation — Backend (Django)

### 1. Prérequis
- Python 3.10+
- pip

### 2. Créer et activer l'environnement virtuel

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Créer la base de données

```bash
python manage.py migrate
```

### 5. Placer tes fichiers CSV

Copie tes fichiers dans le dossier `data/` (à la racine du projet) :
```
immo_project/data/mubawab_data.csv
immo_project/data/tayara_data.csv
```

### 6. Importer les données CSV

```bash
python manage.py seed_data
```

Résultat attendu :
```
[mubawab] Imported 500 listings
[tayara]  Imported 300 listings
✓ Total: 800 listings loaded into DB
```

### 7. Créer un superuser (optionnel, pour l'admin)

```bash
python manage.py createsuperuser
```

### 8. Lancer le serveur Django

```bash
python manage.py runserver
```

API disponible sur → http://localhost:8000/api/

---

## ⚙️ Installation — Frontend (React)

### 1. Prérequis
- Node.js 18+
- npm ou yarn

### 2. Installer les dépendances

```bash
cd frontend
npm install
```

### 3. Lancer React

```bash
npm start
```

Frontend disponible sur → http://localhost:3000

---

## 🔗 Endpoints API

| Méthode | URL | Description |
|---------|-----|-------------|
| GET | `/api/listings/` | Liste paginée (12/page) |
| GET | `/api/listings/{id}/` | Détail d'une annonce |
| GET | `/api/stats/` | Statistiques globales |
| GET | `/api/filter-options/` | Types & villes disponibles |

### Paramètres de filtrage

```
GET /api/listings/?source=mubawab
GET /api/listings/?type_bien=Appartement
GET /api/listings/?localisation=Tunis
GET /api/listings/?min_prix=100000&max_prix=500000
GET /api/listings/?min_surface=50&max_surface=200
GET /api/listings/?chambres=2
GET /api/listings/?search=studio
GET /api/listings/?ordering=-prix
GET /api/listings/?page=2
```

---

## 📊 Format CSV attendu

Les deux fichiers CSV doivent avoir ces colonnes :

```
Titre, Lien, Prix, Localisation, Description, Pieces, Chambres, SallesDeBain, Surface, Type, DatePost
```

- `Prix` : ex. `195 000 TND` ou `1900DT` ou `Prix à consulter`
- `DatePost` : format `DD/MM/YYYY` ou `YYYY-MM-DD`
- Valeurs manquantes : `N/A` ou vide

---

## 🎨 Fonctionnalités

- ✅ Liste paginée des annonces (Mubawab + Tayara)
- ✅ Filtres : source, type, ville, prix, surface, chambres
- ✅ Recherche plein texte
- ✅ Tri par prix, surface, date
- ✅ Vue grille / liste
- ✅ Modal détail d'annonce
- ✅ Barre de statistiques
- ✅ Skeleton loading
- ✅ Interface Django Admin (`/admin/`)

---

## 🚀 Prochaines étapes

- [ ] Authentification utilisateur
- [ ] Annonces favorites
- [ ] Graphiques d'analyse de prix
- [ ] Export PDF des annonces
- [ ] Comparaison Mubawab vs Tayara

---

*Projet Django 4.2 + React 18 + Django REST Framework*

