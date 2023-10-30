# pylint: disable=missing-module-docstring
# type: ignore
import struct

import icontract
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


def decode(blob):
    return struct.unpack("f" * (len(blob) // 4), blob)


def event_embedding_data_to_df(parsed_events):
    # pylint disable=invalid-name
    df = pd.DataFrame(
        parsed_events,
        columns=["id", "embedding", "description", "name", "event_json"],
    )

    # Decode the embedding column
    df["embedding"] = df["embedding"].apply(lambda x: np.array(decode(x)))

    return df


def perform_kmeans_clustering(df, n_clusters):
    # Assuming the embedding column is a list of lists
    embeddings = df["embedding"].tolist()
    scaler = StandardScaler()
    standardized_embeddings = scaler.fit_transform(embeddings)
    ids = df["id"].tolist()
    kmeans = KMeans(
        n_clusters=n_clusters, init="k-means++", random_state=42
    ).fit(standardized_embeddings)
    id_labels = pd.DataFrame(dict(labels=kmeans.labels_, id=ids))
    return id_labels, kmeans


@icontract.require(
    lambda embeddings, cluster_labels: len(embeddings) == len(cluster_labels)
)
def evaluate_clustering(embeddings: np.ndarray, cluster_labels: np.ndarray):
    scaler = StandardScaler()
    standardized_embeddings = scaler.fit_transform(embeddings)
    score = silhouette_score(standardized_embeddings, cluster_labels)
    return score


@icontract.require(
    lambda embeddings, cluster_labels: len(embeddings) == len(cluster_labels)
)
def visualize_tsne(
    embeddings: np.ndarray, cluster_labels: np.ndarray, n_clusters: int
):
    scaler = StandardScaler()
    standardized_embeddings = scaler.fit_transform(embeddings)
    tsne = TSNE(
        n_components=2,
        perplexity=30,
        init="random",
        learning_rate="auto",
    ).fit_transform(standardized_embeddings)
    plot_clusters(tsne, cluster_labels, n_clusters)


colors_4 = [
    "#1f77b4",  # Blue
    "#ff7f0e",  # Orange
    "#2ca02c",  # Green
    "#d62728",  # Red
]
# Colors for 6 clusters
colors_5 = [
    "#1f77b4",  # Blue
    "#ff7f0e",  # Orange
    "#2ca02c",  # Green
    "#d62728",  # Red
    "#9467bd",  # Purple
]
# Colors for 6 clusters
colors_6 = [
    "#1f77b4",  # Blue
    "#ff7f0e",  # Orange
    "#2ca02c",  # Green
    "#d62728",  # Red
    "#9467bd",  # Purple
    "#8c564b",  # Brown
]

colors_7 = [
    "#1f77b4",  # Blue
    "#ff7f0e",  # Orange
    "#2ca02c",  # Green
    "#d62728",  # Red
    "#9467bd",  # Purple
    "#8c564b",  # Brown
    "#e377c2",  # Pink
]
# Colors for 8 clusters
colors_8 = [
    "#1f77b4",  # Blue
    "#ff7f0e",  # Orange
    "#2ca02c",  # Green
    "#d62728",  # Red
    "#9467bd",  # Purple
    "#8c564b",  # Brown
    "#e377c2",  # Pink
    "#7f7f7f",  # Gray
]


def plot_clusters(tsne, labels, n_clusters):
    if n_clusters == 4:
        colors = colors_4
    elif n_clusters == 5:
        colors = colors_5
    elif n_clusters == 6:
        colors = colors_6
    elif n_clusters == 7:
        colors = colors_7
    elif n_clusters == 8:
        colors = colors_8
    else:
        raise ValueError("Invalid number of clusters")

    for i in range(n_clusters):
        plt.scatter(
            tsne[labels == i, 0],
            tsne[labels == i, 1],
            color=colors[i],
            label=f"Cluster {i}",
        )

    plt.legend()
    plt.show()


def evaluate_query(embedding, kmeans):
    distances = np.linalg.norm(kmeans.cluster_centers_ - embedding, axis=1)
    closest_cluster = np.argmin(distances)
    score = -distances[closest_cluster]
    return closest_cluster, score
