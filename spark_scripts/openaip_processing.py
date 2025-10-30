from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, expr
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType
from pyspark.sql.functions import regexp_extract

# ========================================================
# CONFIGURATION
# ========================================================
KAFKA_SERVERS = "kafka:9093"
MONGO_ROOT_USER = "admin"
MONGO_ROOT_PASSWORD = "admin"
MONGO_HOST = "mongodb"
MONGO_PORT = 27017
MONGO_DB = "openaip_data"

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
    .appName("OpenAIP-Processing") \
    .config("spark.mongodb.write.connection.uri", MONGO_URI) \
    .config("spark.mongodb.read.connection.uri", MONGO_URI) \
    .config("spark.jars.packages",
            "org.mongodb.spark:mongo-spark-connector_2.12:3.0.2,"
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# ========================================================
#  SCHEMA JSON IMBRIQUÉ
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
# FUNCTION — KAFKA → RAW COLLECTION
# ========================================================
def ingest_raw(topic, collection):
    print(f"📡 Ingestion Kafka → RAW: {collection}_raw")

    df = spark.read \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_SERVERS) \
        .option("subscribe", topic) \
        .option("startingOffsets", "earliest") \
        .load() \
        .selectExpr("CAST(value AS STRING) as json")

    # Remove duplicates by `name`
    df = df.dropDuplicates(["json"])

    df.write \
        .format("mongo") \
        .mode("overwrite") \
        .option("uri", MONGO_URI) \
        .option("database", MONGO_DB) \
        .option("collection", f"{collection}_raw") \
        .save()

    return df

# ========================================================
# INGEST RAW
# ========================================================
df_airports_raw = ingest_raw(TOPICS["airports"], "airports")
df_airspaces_raw = ingest_raw(TOPICS["airspaces"], "airspaces")
df_obstacles_raw = ingest_raw(TOPICS["obstacles"], "obstacles")

# ========================================================
# PARSE JSON → PROCESSED COLLECTIONS
# ========================================================
def parse_dataset(df_raw):
    return spark.read.json(df_raw.rdd.map(lambda r: r.json))

df_airports = parse_dataset(df_airports_raw) \
    .withColumn("latitude", col("lat").cast(DoubleType())) \
    .withColumn("longitude", col("lon").cast(DoubleType())) \
    .withColumn("elevation_parsed", from_json(col("elevation"), schema_elevation)) \
    .drop("lat", "lon") \
    .dropDuplicates(["name"])

df_airspaces = parse_dataset(df_airspaces_raw) \
    .withColumn("lowerLimit_value", col("lowerLimit_value").cast(DoubleType())) \
    .withColumn("upperLimit_value", col("upperLimit_value").cast(DoubleType())) \
    .dropDuplicates(["name"])

df_obstacles = parse_dataset(df_obstacles_raw) \
    .withColumn("latitude", col("latitude").cast(DoubleType())) \
    .withColumn("longitude", col("longitude").cast(DoubleType())) \
    .withColumn("elevation_parsed", from_json(col("elevation"), schema_elevation)) \
    .withColumn("height_parsed", from_json(col("height"), schema_height)) \
    .dropDuplicates(["name"])

# Write processed
df_airports.write.format("mongo").mode("overwrite").option("uri", MONGO_URI).option("database", MONGO_DB).option("collection", "airports_processed").save()
df_airspaces.write.format("mongo").mode("overwrite").option("uri", MONGO_URI).option("database", MONGO_DB).option("collection", "airspaces_processed").save()
df_obstacles.write.format("mongo").mode("overwrite").option("uri", MONGO_URI).option("database", MONGO_DB).option("collection", "obstacles_processed").save()


# ========================================================
# GOLD
# ========================================================
print("🟨 Building GOLD datasets...")

# Parse geometry JSON
df_airspaces_geo = df_airspaces.withColumn(
    "geometry_json",
    from_json(col("geometry"), StructType([
        StructField("type", StringType()),
        StructField("coordinates", StringType())
    ]))
)

# Extract coordinates string
df_airspaces_geo = df_airspaces_geo.withColumn(
    "coords", col("geometry_json.coordinates")
)

# Regex to get first lon,lat from coordinates
df_airspaces_centroid = df_airspaces_geo \
    .withColumn("lon_c", regexp_extract(col("coords"), r'\[\s*([\-0-9\.]+)', 1).cast(DoubleType())) \
    .withColumn("lat_c", regexp_extract(col("coords"), r'\[\s*[^\[]+,\s*([\-0-9\.]+)', 1).cast(DoubleType()))

# Haversine
def haversine(lat1, lon1, lat2, lon2):
    return f"""
    6371 * 2 * asin(
        sqrt(
            sin(radians(({lat2} - {lat1})/2)) * sin(radians(({lat2} - {lat1})/2)) +
            cos(radians({lat1})) * cos(radians({lat2})) *
            sin(radians(({lon2} - {lon1})/2)) * sin(radians(({lon2} - {lon1})/2))
        )
    )
    """

# Airports ↔ Airspaces (30 km)
gold_airport_airspaces = df_airports.alias("a") \
    .crossJoin(df_airspaces_centroid.alias("b")) \
    .withColumn("distance_km", expr(haversine("a.latitude","a.longitude","b.lat_c","b.lon_c"))) \
    .filter(col("distance_km") < 30) \
    .select("a.name","a.country","b.name","b.type","distance_km")

gold_airport_airspaces.write.format("mongo").mode("overwrite") \
    .option("uri", MONGO_URI).option("database", MONGO_DB) \
    .option("collection", "airport_airspaces").save()

# Airports ↔ Obstacles (5 km)
gold_airport_obstacles = df_airports.alias("a") \
    .crossJoin(df_obstacles.alias("b")) \
    .withColumn("distance_km", expr(haversine("a.latitude","a.longitude","b.latitude","b.longitude"))) \
    .filter(col("distance_km") < 5) \
    .select("a.name","a.country","b.name","b.type","distance_km")

gold_airport_obstacles.write.format("mongo").mode("overwrite") \
    .option("uri", MONGO_URI).option("database", MONGO_DB) \
    .option("collection", "airport_obstacles").save()

print("✅ GOLD done")

print("✅ Pipeline COMPLETED — RAW + PROCESSED + GOLD written to MongoDB")
spark.stop()