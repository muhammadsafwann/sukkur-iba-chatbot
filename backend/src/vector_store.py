"""
vector_store.py

A complete class to generate embeddings and manage a FAISS vector index.
Usage:
    from src.vector_store import VectorStore
    store = VectorStore()
    store.build_index(df)          # df has 'text' and 'metadata' columns
    store.save("faiss_index.bin", "documents.pkl")
    store.load("faiss_index.bin", "documents.pkl")
    results = store.search("What is the fee for BBA?", k=3)
"""

import faiss
import numpy as np
import pandas as pd
import pickle
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional, Union


class VectorStore:
    """
    Handles embedding generation, FAISS index creation, saving/loading,
    and similarity search.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedding model and FAISS index.
        model_name: any sentence-transformers model (384-dim recommended).
        """
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.documents = None  # DataFrame with original texts + metadata
        print(f"OK: Loaded embedding model: {model_name}")

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Convert a list of strings into a numpy array of embeddings.
        """
        print(f"Generating embeddings for {len(texts)} documents...")
        embeddings = self.model.encode(
            texts,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True  # Important for cosine similarity with FAISS
        )
        print(f"OK: Generated embeddings with shape {embeddings.shape}")
        return embeddings

    def build_index(self, df: pd.DataFrame, text_column: str = "text"):
        """
        Create a FAISS index from the 'text' column of the DataFrame.
        Also stores the full DataFrame (with metadata) for retrieval.
        """
        self.documents = df.copy()
        texts = df[text_column].tolist()
        embeddings = self.generate_embeddings(texts)

        # Create FAISS index (Inner Product = Cosine similarity after normalization)
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings)
        print(f"OK: FAISS index built with {self.index.ntotal} vectors.")
        return self.index

    def save(self, index_path: str, documents_path: str):
        """
        Save the FAISS index and the documents DataFrame to disk.
        """
        if self.index is None:
            raise ValueError("No index to save. Call build_index() first.")
        faiss.write_index(self.index, index_path)
        with open(documents_path, "wb") as f:
            pickle.dump(self.documents, f)
        print(f"OK: Index saved to {index_path}")
        print(f"OK: Documents saved to {documents_path}")

    def load(self, index_path: str, documents_path: str):
        """
        Load a previously saved FAISS index and documents DataFrame.
        """
        self.index = faiss.read_index(index_path)
        with open(documents_path, "rb") as f:
            self.documents = pickle.load(f)
        print(f"OK: Loaded index with {self.index.ntotal} vectors.")
        print(f"OK: Loaded {len(self.documents)} documents.")
        return self.index, self.documents

    def search(
        self,
        query: str,
        k: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Dict]:
        """
        Search for the top-k most similar documents to the query.
        Returns a list of dicts with 'id', 'question', 'answer', 'department',
        'tags', 'text', 'score'.
        """
        if self.index is None:
            raise ValueError("No index loaded. Call build_index() or load() first.")

        # Embed and normalize the query
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True
        )

        # Search
        scores, indices = self.index.search(query_embedding, k)

        results = []
        for i, idx in enumerate(indices[0]):
            score = float(scores[0][i])
            if score_threshold is not None and score < score_threshold:
                continue

            doc = self.documents.iloc[idx]
            results.append({
                'id': doc['ID'],
                'question': doc['Question'],
                'answer': doc['Answer'],
                'department': doc['Department'],
                'tags': doc['Tags'],
                'text': doc['text'],
                'score': score,
                'metadata': doc['metadata']  # already a dict
            })
        return results


# ----------------------------------------------------------------------
# Example usage (run only if this file is executed directly)
if __name__ == "__main__":
    # This test assumes you have a prepared DataFrame from data_loader.py
    from data_loader import FAQDataPreparator

    # Load and prepare data
    preparator = FAQDataPreparator()
    df = preparator.load_and_prepare("dataset.csv")  # adjust path if needed

    # Build vector store
    store = VectorStore()
    store.build_index(df)

    # Save to disk
    store.save("faiss_index.bin", "documents.pkl")

    # Test a search
    print("\n>> Searching for 'BBA fee':")
    results = store.search("BBA fee", k=3)
    for r in results:
        print(f"Score: {r['score']:.4f} - Q: {r['question'][:60]}...")