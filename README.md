# Projet OpenAIP - Pipeline de Données Aéronautiques

## 📋 Description

Pipeline Big Data pour le traitement et la visualisation de données aéronautiques (aéroports, espaces aériens, obstacles) provenant d'OpenAIP. Le projet utilise une architecture medallion (RAW → PROCESSED → GOLD) avec Apache Spark pour le traitement et Grafana pour la visualisation.

## Architecture

```
NiFi → Kafka → Spark Processing → MongoDB → API REST → Grafana
```

**Technologies utilisées :**
- **Apache NiFi** : Ingestion de données
- **Apache Kafka** : Streaming de messages
- **Apache Spark** : Traitement distribué
- **MongoDB** : Stockage des données
- **Node.js API** : Exposition REST des données
- **Grafana** : Visualisation

## Collections MongoDB

### RAW Layer (Données brutes)
- `airports_raw` : Aéroports bruts de Kafka
- `airspaces_raw` : Espaces aériens bruts
- `obstacles_raw` : Obstacles bruts

### PROCESSED Layer (Données nettoyées)
- `airports_processed` : Aéroports avec coordonnées parsées
- `airspaces_processed` : Espaces aériens structurés
- `obstacles_processed` : Obstacles structurés

### GOLD Layer (Analytics)
- `airport_airspaces` : Aéroports à proximité (<30km) d'espaces aériens
- `airport_obstacles` : Aéroports à proximité (<5km) d'obstacles

## 🚀 Installation et Lancement

### Prérequis

- Docker & Docker Compose
- 8 GB RAM minimum
- Ports disponibles : 3100, 5000, 7177, 8180, 9092, 27017

### Étape 1 : Démarrer l'infrastructure

```powershell
# Démarrer tous les services Docker
docker-compose up -d

# Vérifier que tous les conteneurs sont démarrés
docker-compose ps
```

**Services lancés :**
- Zookeeper (port 2181)
- Kafka (port 9092)
- MongoDB (port 27017)
- Spark Master (port 8180)
- Spark Workers
- NiFi (port 8443)
- Grafana (port 3100)
- API REST (port 5000)

### Étape 2 : Vérifier MongoDB

```powershell
# Vérifier la connexion MongoDB
docker-compose exec mongodb mongosh -u admin -p admin --authenticationDatabase admin
```

Dans le shell MongoDB :
```javascript
show dbs
use openaip_data
show collections
exit
```

### Étape 3 : Exécuter le traitement Spark

```powershell
# Copier le script de traitement dans le conteneur docker (si pas encore fait)
docker cp spark_scripts/openaip_processing.py projet_m2_data-spark-master-1:/tmp/openaip_processing.py

# Entrer dans le conteneur Spark Master
docker-compose exec spark-master bash

# Lancer le script de traitement (dans le conteneur)
/opt/spark/bin/spark-submit --packages org.mongodb.spark:mongo-spark-connector_2.12:3.0.2,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 /opt/spark/work-dir/openaip_processing.py 

# Sortir du conteneur
exit
```

**Résultat attendu :**
```
📡 Ingestion Kafka → RAW: airports_raw
📡 Ingestion Kafka → RAW: airspaces_raw
📡 Ingestion Kafka → RAW: obstacles_raw
🟨 Building GOLD datasets...
✅ GOLD done
✅ Pipeline COMPLETED — RAW + PROCESSED + GOLD written to MongoDB
```

### Étape 4 : Vérifier l'API REST

```powershell
# Tester l'API
curl http://localhost:5000/

# Vérifier les données des aéroports
curl http://localhost:5000/api/airports_processed
```

**Endpoints disponibles :**
- `GET /api/airports_processed`
- `GET /api/airspaces_processed`
- `GET /api/obstacles_processed`
- `GET /api/airport_airspaces`
- `GET /api/airport_obstacles`

### Étape 5 : Visualisation sur Grafana
Méthode 1:utilisation de JsonApi

Methode 2:Installer le plugin Grafana

```powershell
# Installer le plugin Infinity
docker-compose exec grafana grafana-cli plugins install yesoreyeram-infinity-datasource

# Redémarrer Grafana
docker-compose restart grafana
```

Attendre 15 secondes pour que Grafana redémarre.

### Étape 6 : Configurer Grafana

#### A. Accéder à Grafana
- URL : `http://localhost:3100`
- Username : `admin`
- Password : `admin`

#### B. Ajouter la Data Source

1. **Menu** → **⚙️ Configuration** → **Data Sources**
2. **Add data source** → Chercher **"Infinity"** (si plugging installé) sinon → Chercher **JsonAPI**

3. Configuration (pour Infinity) :
   ```
   Name: OpenAIP API
   ```
4. **Save & Test**

#### C. Créer un Dashboard avec Geomap

1. **+ Create** → **Dashboard** → **Add visualization**
2. Sélectionner **"OpenAIP API"**
3. Sélectionner **"Geomap"**

#### D. Configuration de la requête

Dans le panneau de requête :

```
Query Type:     JSON
Parser:         Backend
Source:         URL
Format:         Table
URL:            http://api-mongo:3001/api/airports_processed
Method:         GET
```

**Colonnes** (Parsing options & Result fields) :

| Selector | Alias | Type |
|----------|-------|------|
| `latitude` | `latitude` | `Number` |
| `longitude` | `longitude` | `Number` |
| `name` | `name` | `String` |
| `country` | `country` | `String` |

#### E. Configuration du Geomap

Dans le panneau de droite :

**Panel options :**
```
Title: Carte des Aéroports OpenAIP
```

**Map view :**
```
View: Fit data
```

**Data layer → Location :**
```
Location mode: Coords
Latitude field: latitude
Longitude field: longitude
```

**Marker :**
```
Size: 5
Color: Bleu
```

**Tooltip :**
```
Tooltip mode: Details
```

5. **Apply** → **Save dashboard**
   - Dashboard name : `OpenAIP - Visualisation Aéronautique`

## 🎯 Résultat

Vous devriez voir :
- 🗺️ Une carte interactive du monde
- ✈️ Des marqueurs pour chaque aéroport
- 📍 Détails au survol (nom, pays, coordonnées)
- 🔍 Zoom et navigation possibles

## 📁 Structure du Projet

```
projet_M2_Data/
├── docker-compose.yml              # Orchestration des services
├── spark_scripts/
│   └── openaip_processing.py       # Script Spark de traitement
├── api_mongo/
│   ├── server.js                   # API REST Node.js
│   ├── Dockerfile
│   └── requirements.txt
├── infrastructure/
│   └── spark/
│       ├── Dockerfile
│       └── requirements.txt
└── nifi_templates/
    └── nifi_version_finale.xml
```

## 🔧 Script Spark - Détails

Le script `openaip_processing.py` effectue :

### 1. RAW Layer
- Lit les topics Kafka : `openAIP_airports`, `openAIP_airspaces`, `openAIP_obstacles`
- Stocke les JSON bruts dans MongoDB
- Déduplique par contenu

### 2. PROCESSED Layer
- Parse le JSON en colonnes structurées
- Convertit les coordonnées en `DoubleType`
- Parse les champs imbriqués (`elevation`, `height`)
- Déduplique par `name`

### 3. GOLD Layer
- **airport_airspaces** : Calcule les aéroports à <30km d'espaces aériens (formule Haversine)
- **airport_obstacles** : Calcule les aéroports à <5km d'obstacles

## 🛠️ Commandes Utiles

### Gestion des conteneurs

```powershell
# Voir les logs
docker-compose logs -f api-mongo
docker-compose logs -f spark-master

# Redémarrer un service
docker-compose restart grafana
docker-compose restart api-mongo

# Arrêter tout
docker-compose down

# Tout supprimer (y compris les volumes)
docker-compose down -v
```

### MongoDB

```powershell
# Se connecter à MongoDB
docker-compose exec mongodb mongosh -u admin -p admin --authenticationDatabase admin

# Voir les collections
use openaip_data
show collections

# Compter les documents
db.airports_processed.countDocuments()
db.airport_airspaces.countDocuments()
```

### Vérifier les données

```powershell
# Via l'API
curl http://localhost:5000/api/airports_processed | ConvertFrom-Json | Select-Object -First 5

# Nombre d'aéroports
(curl http://localhost:5000/api/airports_processed | ConvertFrom-Json).Count
```

## 🐛 Dépannage

### L'API ne démarre pas
```powershell
# Reconstruire l'image
docker-compose build api-mongo
docker-compose up -d api-mongo
```

### Spark ne trouve pas spark-submit
```powershell
# Utiliser le chemin complet
/opt/spark/bin/spark-submit ...
```

### Grafana ne montre pas les données
1. Vérifier que l'API fonctionne : `curl http://localhost:5000/api/airports_processed`
2. Vérifier que le plugin Infinity est installé
3. Utiliser `http://api-mongo:3001` (pas `localhost:5000`) dans Grafana
4. Vérifier que les champs sont bien de type `Number`

### MongoDB est vide
```powershell
# Relancer le script Spark
docker-compose exec spark-master /opt/spark/bin/spark-submit --packages org.mongodb.spark:mongo-spark-connector_2.12:3.0.2,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 /opt/spark/work-dir/openaip_processing.py
```

## 📝 Notes Importantes

1. **Réseau Docker** : L'API est accessible via `api-mongo:3001` depuis Grafana (réseau interne) et `localhost:5000` depuis Windows
2. **Données** : Le script Spark écrase les collections à chaque exécution (mode `overwrite`)
3. **Performance** : Le traitement Spark peut prendre 1-2 minutes selon la quantité de données
4. **Plugins Grafana** : Le plugin Infinity est essentiel pour la visualisation

## 🎓 Auteur

Projet M2 Data - Données Distribuées
Léo Charles
Audrey Magne

## 📅 Date

Octobre 2025
