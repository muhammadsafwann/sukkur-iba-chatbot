"""
vector_store.py

A complete class to generate embeddings via Hugging Face Inference API and manage a FAISS vector index.
Usage:
    from src.vector_store import VectorStore
    store = VectorStore()
    store.build_index(df)          # df has 'text' and 'metadata' columns
    store.save("faiss_index.bin", "documents.pkl")
    store.load("faiss_index.bin", "documents.pkl")
    results = store.search("What is the fee for BBA?", k=3)
"""

import os
import numpy as np
import pandas as pd
import pickle
import faiss
from typing import List, Dict, Optional, Union
from tqdm import tqdm
from huggingface_hub import InferenceClient

class VectorStore:
    """
    Handles embedding generation via Hugging Face API, FAISS index creation, saving/loading,
    and similarity search.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize the embedding client and FAISS index.
        model_name: any embedding model available on Hugging Face Inference API.
        Requires HF_TOKEN environment variable.
        """
        self.model_name = model_name
        self.token = os.environ.get("HF_TOKEN")
        if not self.token:
            raise ValueError("HF_TOKEN environment variable not set. Get a free token at huggingface.co/settings/tokens")
        # Use the official client with the correct, up-to-date endpoint.
        self.client = InferenceClient(model=model_name, token=self.token)
        self.index = None
        self.documents = None  # DataFrame with original texts + metadata
        print(f"OK: Using Hugging Face embedding model: {model_name}")

    def _embed_batch(self, texts: List[str], batch_size: int = 32) -> List[np.ndarray]:
        """
        Send a batch of texts to the Hugging Face API.
        Uses the official client which handles the correct API endpoint format.
        Returns a list of numpy arrays (each of dimension 384 for all-MiniLM-L6-v2).
        """
        all_embeddings = []
        # Process in smaller batches to avoid timeouts
        for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches", unit="batch"):
            batch = texts[i:i+batch_size]
            # Retry logic for transient errors
            retries = 3
            for attempt in range(retries):
                try:
                    # The official client method returns the embedding vector(s).
                    # It can handle both a single string and a list of strings.
                    embeddings = self.client.feature_extraction(batch)
                    break
                except Exception as e:
                    if attempt == retries - 1:
                        raise
                    time.sleep(2)
            # The API returns a list of lists; convert to numpy.
            # It may return a single list for a single text.
            if isinstance(embeddings, list) and len(embeddings) > 0 and isinstance(embeddings[0], list):
                all_embeddings.extend([np.array(emb) for emb in embeddings])
            else:
                # Handle single text response case
                all_embeddings.append(np.array(embeddings))
        return all_embeddings

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Convert a list of strings into a numpy array of embeddings (normalized).
        """
        print(f"Generating embeddings for {len(texts)} documents via Hugging Face API...")
        embeddings_list = self._embed_batch(texts, batch_size=32)
        # Stack into numpy array of shape (n_docs, dim)
        embeddings = np.vstack(embeddings_list).astype(np.float32)
        # Normalize for cosine similarity (FAISS inner product works as cosine after normalization)
        faiss.normalize_L2(embeddings)
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

        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner product = cosine after normalization
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

        # Use the official client for the query embedding.
        # The client expects a string, not a list, for a single input.
        query_embedding = self.client.feature_extraction(query)
        query_vec = np.array(query_embedding).astype(np.float32).reshape(1, -1)
        # Normalize query vector
        faiss.normalize_L2(query_vec)

        # Search
        scores, indices = self.index.search(query_vec, k)

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

# Example usage (run only if this file is executed directly)
if __name__ == "__main__":
    from data_loader import FAQDataPreparator

    preparator = FAQDataPreparator()
    df = preparator.load_and_prepare("dataset.csv")
    store = VectorStore()
    store.build_index(df)
    store.save("faiss_index.bin", "documents.pkl")
    print("\n>> Searching for 'BBA fee':")
    results = store.search("BBA fee", k=3)
    for r in results:
        print(f"Score: {r['score']:.4f} - Q: {r['question'][:60]}...")