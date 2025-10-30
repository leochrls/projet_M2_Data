# infrastructure/spark/Dockerfile

FROM apache/spark:3.5.1
USER 0
RUN apt-get update && apt-get install -y python3-pip && rm -rf /var/lib/apt/lists/*

# Copier et installer depuis le fichier de dépendances
COPY requirements.txt /tmp/
RUN pip3 install -r /tmp/requirements.txt

USER 185