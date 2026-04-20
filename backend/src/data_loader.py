"""
data_loader.py

A complete class to load and prepare the university FAQ dataset.
Usage:
    from data_loader import FAQDataPreparator
    preparator = FAQDataPreparator()
    df = preparator.load_and_prepare("data/data.csv")
"""

import pandas as pd
import re
from typing import Dict, List, Union


class FAQDataPreparator:
    """
    Prepares FAQ CSV data for embedding and retrieval.
    Each row becomes a document with:
        - 'text': concatenated Question + Answer (cleaned)
        - 'metadata': dict with id, question, department, tags
    """

    def __init__(self):
        """Initialize the preparator (no state needed)."""
        pass

    def load_csv(self, file_path: str) -> pd.DataFrame:
        """
        Load a CSV file into a pandas DataFrame.
        Expects columns: ID, Question, Answer, Tags, Department.
        """
        df = pd.read_csv(file_path)
        print(f"OK: Loaded {len(df)} rows from {file_path}")
        return df

    @staticmethod
    def _clean_text(text: Union[str, float]) -> str:
        """
        Internal method: remove extra whitespace, newlines, and trim.
        Handles NaN values by converting to empty string.
        """
        if pd.isna(text):
            return ""
        # Convert to string (in case of numbers)
        text = str(text)
        # Collapse multiple whitespace characters into a single space
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def clean_text_series(self, series: pd.Series) -> pd.Series:
        """Apply text cleaning to an entire pandas Series."""
        return series.apply(self._clean_text)

    def prepare_documents(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add 'text' and 'metadata' columns to the DataFrame.
        Returns a new DataFrame (original columns are kept).
        """
        # Work on a copy to avoid modifying the original
        df = df.copy()

        # 1. Clean the Question and Answer columns
        df['Question'] = self.clean_text_series(df['Question'])
        df['Answer'] = self.clean_text_series(df['Answer'])

        # 2. Create unified text field (Question + Answer)
        df['text'] = df['Question'] + " " + df['Answer']

        # 3. Add metadata dictionary for filtering / display
        df['metadata'] = df.apply(self._create_metadata, axis=1)

        return df

    @staticmethod
    def _create_metadata(row: pd.Series) -> Dict:
        """Create a metadata dictionary from a DataFrame row."""
        tags = []
        if pd.notna(row['Tags']):
            tags = [tag.strip() for tag in str(row['Tags']).split(',')]
        return {
            'id': row['ID'],
            'question': row['Question'],
            'department': row['Department'],
            'tags': tags
        }

    def load_and_prepare(self, file_path: str) -> pd.DataFrame:
        """
        Convenience method: load CSV and prepare documents in one call.
        """
        df = self.load_csv(file_path)
        df = self.prepare_documents(df)
        return df


# ----------------------------------------------------------------------
# Example usage (run only if this file is executed directly)
if __name__ == "__main__":
    # Quick test - assumes there is a 'data.csv' file in the same folder
    preparator = FAQDataPreparator()
    try:
        df = preparator.load_and_prepare("data.csv")
        print("\nOK: First row preview:")
        print(df[['ID', 'text', 'metadata']].head(1))
    except FileNotFoundError:
        print("WARNING:  Place your 'data.csv' file in the same directory as this script to run the test.")