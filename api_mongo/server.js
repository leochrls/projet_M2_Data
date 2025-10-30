const express = require('express');
const { MongoClient } = require('mongodb');

// ===================================================================
// CONFIGURATION
const port = 3001;
const dbHost = process.env.MONGO_HOST || 'mongo'; 
const dbPort = process.env.MONGO_PORT || '27017';
const dbUser = process.env.MONGO_USER;
const dbPassword = process.env.MONGO_PASS;
const dbName = process.env.MONGO_DBNAME; // Le nom de la base de données cible

// Vérification que les variables d'environnement critiques sont bien définies
if (!dbUser || !dbPassword || !dbName) {
    console.error("Erreur: Les variables d'environnement MONGO_USER, MONGO_PASS, et MONGO_DBNAME doivent être définies.");
    process.exit(1); // Arrête< l'application si les identifiants sont manquants>
}

// Construction de la chaîne de connexion avec encodage des identifiants
// pour gérer les caractères spéciaux dans le mot de passe
const mongoUrl = `mongodb://${encodeURIComponent(dbUser)}:${encodeURIComponent(dbPassword)}@${dbHost}:${dbPort}`;
const client = new MongoClient(mongoUrl);

// Initialisation de l'application Express
const app = express();

// ===================================================================
// FONCTION PRINCIPALE POUR DÉMARRER LE SERVEUR
async function run() {
    try {
        // 1. Connexion à la base de données
        await client.connect();
        const db = client.db(dbName);
        console.log(`Connecté avec succès à la base de données MongoDB: "${dbName}"`);

        // 2. Définition des routes de l'API (une par collection)
        
        // Route de test pour vérifier que l'API fonctionne
        app.get('/', (req, res) => {
            res.send('API pour Grafana est en marche ! Les routes sont sur /api/<nom_collection>');
        });

        // Liste des collections à exposer
        const collections = [
            'airport_airspaces',
            'airport_obstacles',
            'airports_processed',
            'airspaces_processed',
            'obstacles_processed'
        ];

        // Boucle pour créer une route pour chaque collection
        collections.forEach(collectionName => {
            app.get(`/api/${collectionName}`, async (req, res) => {
                try {
                    console.log(`Requête reçue pour la collection: ${collectionName}`);
                    const collection = db.collection(collectionName);
                    // Récupère tous les documents de la collection.
                    // Pour de très grosses collections, il faudrait ajouter de la pagination.
                    const data = await collection.find({}).toArray();
                    res.json(data);
                } catch (err) {
                    console.error(`Erreur lors de la récupération des données de ${collectionName}:`, err);
                    res.status(500).send(`Erreur serveur pour la collection ${collectionName}: ${err.message}`);
                }
            });
            console.log(`Route /api/${collectionName} créée.`);
        });

        // 3. Démarrage du serveur web
        app.listen(port, () => {
            console.log(`API démarrée et écoutant sur le port ${port}`);
        });

    } catch (err) {
        console.error("Impossible de se connecter à MongoDB ou de démarrer le serveur API:", err);
        process.exit(1);
    }
}

// Lancement de l'application
run();