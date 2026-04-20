"""
build_index.py
Run this script after updating dataset.csv or prospectus PDF to rebuild the combined index.
"""

from src.data_loader import FAQDataPreparator
from src.prospectus_loader import ProspectusLoader
from src.vector_store import VectorStore
import pandas as pd

# 1. Load FAQ dataset
print("Loading FAQ dataset...")
preparator = FAQDataPreparator()
faq_df = preparator.load_and_prepare("dataset/dataset.csv")   # adjust path if needed
print(f"FAQ rows: {len(faq_df)}")

# 2. Load prospectus (if you have multiple PDFs, load them and concatenate)
# Option A – single PDF (e.g., merged file)
prospectus_loader = ProspectusLoader(chunk_size=1500, chunk_overlap=50)
pros_df = prospectus_loader.load_and_chunk("dataset/prospectus.pdf")   # or "prospectus.pdf"
print(f"Prospectus chunks: {len(pros_df)}")

# Option B – if you have two separate PDFs and want to keep both (uncomment below)
# pros_df1 = prospectus_loader.load_and_chunk("dataset/prospectus.pdf")
# pros_df2 = prospectus_loader.load_and_chunk("dataset/prospectusnew.pdf")
# pros_df = pd.concat([pros_df1, pros_df2], ignore_index=True)
# print(f"Prospectus chunks (combined): {len(pros_df)}")

# 3. Combine DataFrames
combined_df = pd.concat([faq_df, pros_df], ignore_index=True)
print(f"Total documents: {len(combined_df)}")

# 4. Build FAISS index
store = VectorStore()
store.build_index(combined_df)

# 5. Save the combined index and documents (these are the files the API loads)
store.save("faiss_index_combined.bin", "documents_combined.pkl")

print("✅ Index rebuilt successfully. You can now restart the backend (python server.py).")