from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType

# ========================================================
# CONFIGURATION
# ========================================================
KAFKA_SERVERS = "kafka:9093"
MONGO_ROOT_USER = "admin"
MONGO_ROOT_PASSWORD = "admin"
MONGO_HOST = "mongodb"
MONGO_PORT = 27017
MONGO_DB = "openaip_data"

# URI SANS collection (on la donne via .option("collection", ...))
MONGO_URI = f"mongodb://{MONGO_ROOT_USER}:{MONGO_ROOT_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/?authSource=admin"

TOPICS = {
    "airports": "openAIP_airports",
    "airspaces": "openAIP_airspaces",
    "obstacles": "openAIP_obstacles"
}

# ========================================================
# SESSION SPARK
# ========================================================
spark = SparkSession.builder \
    .appName("OpenAIP-Processing (dedup by name)") \
    .config("spark.mongodb.write.connection.uri", MONGO_URI) \
    .config("spark.mongodb.read.connection.uri", MONGO_URI) \
    .config("spark.jars.packages",
            "org.mongodb.spark:mongo-spark-connector_2.12:3.0.2,"
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# ========================================================
#  SCHÉMAS JSON IMBRIQUÉS
# ========================================================
schema_elevation = StructType([
    StructField("value", DoubleType()),
    StructField("unit", IntegerType()),
    StructField("referenceDatum", IntegerType())
])

schema_height = StructType([
    StructField("value", DoubleType()),
    StructField("unit", IntegerType()),
    StructField("referenceDatum", IntegerType())
])

# ========================================================
# FONCTION GÉNÉRIQUE : KAFKA → DF JSON → DEDUP(name) → MONGO RAW
# ========================================================
def read_kafka_parse_dedup_write_raw(topic_name: str, collection_name: str):
    """
    Lit Kafka (topic_name), parse le JSON, déduplique sur 'name',
    écrit le RAW dédupliqué dans Mongo (collection '<name>_raw'),
    et retourne le DataFrame dédupliqué pour la suite (processed).
    """
    print(f"📡 Lecture Kafka topic: {topic_name} → Mongo collection: {collection_name}_raw (dedup by 'name')")

    # 1) Lecture Kafka (value en STRING)
    df_json_string = spark.read \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_SERVERS) \
        .option("subscribe", topic_name) \
        .option("startingOffsets", "earliest") \
        .load() \
        .selectExpr("CAST(value AS STRING) AS json")

    # 2) Parsing JSON → colonnes
    df_parsed = spark.read.json(df_json_string.rdd.map(lambda r: r.json))

    # 3) Déduplication sur 'name'
    # (si 'name' peut être null, on peut ajouter .na.drop(['name']) avant)
    df_dedup = df_parsed.dropDuplicates(["name"])

    # 4) Écriture RAW (documents plats, pas la colonne 'json')
    df_dedup.write \
        .format("mongo") \
        .mode("overwrite") \
        .option("uri", MONGO_URI) \
        .option("database", MONGO_DB) \
        .option("collection", f"{collection_name}_raw") \
        .save()

    return df_dedup

# ========================================================
#  AIRPORTS (dedup)
# ========================================================
df_airports_base = read_kafka_parse_dedup_write_raw(TOPICS["airports"], "airports")

df_airports_proc = df_airports_base \
    .withColumn("latitude",  col("lat").cast(DoubleType())) \
    .withColumn("longitude", col("lon").cast(DoubleType())) \
    .withColumn("elevation_parsed", from_json(col("elevation"), schema_elevation)) \
    .drop("lat", "lon") \
    .dropDuplicates(["name"])  # ceinture et bretelles

df_airports_proc.write \
    .format("mongo") \
    .mode("overwrite") \
    .option("uri", MONGO_URI) \
    .option("database", MONGO_DB) \
    .option("collection", "airports_processed") \
    .save()

# ========================================================
#  AIRSPACES (dedup)
# ========================================================
df_airspaces_base = read_kafka_parse_dedup_write_raw(TOPICS["airspaces"], "airspaces")

df_airspaces_proc = df_airspaces_base \
    .withColumn("lowerLimit_value", col("lowerLimit_value").cast(DoubleType())) \
    .withColumn("upperLimit_value", col("upperLimit_value").cast(DoubleType())) \
    .dropDuplicates(["name"])

df_airspaces_proc.write \
    .format("mongo") \
    .mode("overwrite") \
    .option("uri", MONGO_URI) \
    .option("database", MONGO_DB) \
    .option("collection", "airspaces_processed") \
    .save()

# ========================================================
# OBSTACLES (dedup)
# ========================================================
df_obstacles_base = read_kafka_parse_dedup_write_raw(TOPICS["obstacles"], "obstacles")

df_obstacles_proc = df_obstacles_base \
    .withColumn("latitude",  col("latitude").cast(DoubleType())) \
    .withColumn("longitude", col("longitude").cast(DoubleType())) \
    .withColumn("elevation_parsed", from_json(col("elevation"), schema_elevation)) \
    .withColumn("height_parsed",    from_json(col("height"),    schema_height)) \
    .dropDuplicates(["name"])

df_obstacles_proc.write \
    .format("mongo") \
    .mode("overwrite") \
    .option("uri", MONGO_URI) \
    .option("database", MONGO_DB) \
    .option("collection", "obstacles_processed") \
    .save()

# ========================================================
# FIN DE TRAITEMENT
# ========================================================
print(" Ingestion dédupliquée (clé 'name') + parsing/typage écrits dans Mongo.")
spark.stop()
