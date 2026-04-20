import os
from groq import Groq

class AnswerGenerator:
    def __init__(self, model_name="llama-3.3-70b-versatile"):
        self.model_name = model_name
        
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key or api_key == "YOUR_GROQ_API_KEY":
            raise ValueError("GROQ_API_KEY environment variable is not set. Please add it to your .env file.")
            
        self.client = Groq(api_key=api_key)
        print(f"OK: Loaded generator with Groq model: {model_name}")

    def generate(self, query: str, retrieved_docs: list) -> str:
        # 1. Build context string from top documents (your existing code)
        context_parts = []
        for i, doc in enumerate(retrieved_docs, 1):
            source = doc.get('metadata', {}).get('source', 'FAQ')
            if source == 'prospectus':
                context_parts.append(f"[Document {i}] (Prospectus): {doc['text']}")
            else:
                context_parts.append(
                    f"[Document {i}] (FAQ)\nQ: {doc['question']}\nA: {doc['answer']}"
                )
        context = "\n\n".join(context_parts)

        # 2. Create the advanced prompt
        prompt = f"""You are a helpful, factual assistant for Sukkur IBA University. You are given several documents ranked by relevance (Document 1 is the most relevant). Follow these rules strictly:

1. Base your answer **primarily on Document 1** (the first document).
2. Only look at Documents 2, 3, etc. if Document 1 does NOT contain the answer.
3. Give a **direct, complete answer** in 1-2 sentences. Do not add phrases like "Based on the provided context" or "According to the documents".
4. If the answer is a number (e.g., CGPA, percentage), include a brief explanation (e.g., "You need a minimum CGPA of 2.2. Falling below may lead to probation.").
5. If none of the documents contain the answer, say exactly: "I don't have that information in my knowledge base."

Now, here are the documents:

{context}

User Question: {query}

Answer:"""

        # 3. Call the Groq API
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model_name,
                temperature=0.2,  # Lower temperature for more factual answers
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            print(f"Error calling Groq API: {e}")
            return "Sorry, I encountered an error while generating an answer."