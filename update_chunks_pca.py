from pymongo import MongoClient, UpdateOne
from sklearn.decomposition import PCA
import numpy as np
import os
from dotenv import load_dotenv

# -----------------------------
# 1. MongoDB Configuration
# -----------------------------

load_dotenv()
MONGO_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DATABASE")
CHUNKS_COLLECTION = os.getenv("MONGODB_COLLECTION")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
chunks_col = db[CHUNKS_COLLECTION]

# -----------------------------
# 2. Load all chunks with embeddings
# -----------------------------
chunks = list(chunks_col.find({}, {"id": 1, "embeddings": 1}))

ids = []
embeddings = []

for chunk in chunks:
    if "embeddings" in chunk and chunk["embeddings"]:
        ids.append(chunk["id"])
        embeddings.append(chunk["embeddings"])

embeddings = np.array(embeddings, dtype=np.float32)

print(f"Loaded {len(embeddings)} embeddings")

# -----------------------------
# 3. Run PCA
# -----------------------------
pca = PCA(n_components=2, random_state=42)
coords = pca.fit_transform(embeddings)

Xpca = coords[:, 0]
Ypca = coords[:, 1]

# -----------------------------
# 4. Update MongoDB
# -----------------------------
bulk_ops = []

for i, chunk_id in enumerate(ids):
    bulk_ops.append(
        UpdateOne(
            {"id": chunk_id},
            {"$set": {"Xpca": float(Xpca[i]), "Ypca": float(Ypca[i])}}
        )
    )

if bulk_ops:
    result = chunks_col.bulk_write(bulk_ops)
    print(f"Updated {result.modified_count} chunks with Xpca/Ypca")

print("Done!")