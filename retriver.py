from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

print("1. Downloading a free Embedding Model (this takes a few seconds the first time)...")
# This runs locally on your machine, so it's 100% free.
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

print("2. Scraping a web article...")
# We are grabbing a random article about Agentic AI
url = "https://lilianweng.github.io/posts/2023-06-23-agent/"
loader = WebBaseLoader(url)
docs = loader.load()

print("3. Chopping the article into chunks...")
# LLMs can't read whole books at once. We split the text into 500-character chunks.
# Update these lines in your retriever.py file
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=100,
    separators=["\n\n", "\n", ".", " ", ""] 
)
splits = text_splitter.split_documents(docs)

print(f"   Created {len(splits)} chunks.")

print("4. Saving chunks to the Chroma Vector Database...")
# This converts the text chunks into math (vectors) and saves them in a folder called 'chroma_db'
vectorstore = Chroma.from_documents(
    documents=splits,
    embedding=embeddings,
    persist_directory="./chroma_db" # Saves to your hard drive so you don't have to rebuild it
)

print("\n=== LET'S TEST THE RETRIEVER ===")
# Now we ask our database to find the top 2 most relevant chunks to a specific question
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

question = "What is the role of memory in AI agents?"
print(f"Question: '{question}'")

retrieved_docs = retriever.invoke(question)

for i, doc in enumerate(retrieved_docs):
    print(f"\n--- Result {i+1} ---")
    print(doc.page_content)