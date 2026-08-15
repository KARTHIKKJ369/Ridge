from dotenv import load_dotenv

from rag_ingest import split_article


load_dotenv()


def main():
    print("Loading and splitting document by real headers...")
    splits = split_article()

    print(f"Total final chunks created: {len(splits)}\n")

    start_index = min(10, max(0, len(splits) - 3))
    for i in range(start_index, min(start_index + 3, len(splits))):
        print(f"--- Chunk {i} ({len(splits[i].page_content)} chars) ---")
        print(f"Metadata: {splits[i].metadata}")
        print(splits[i].page_content)
        print("-" * 50 + "\n")


if __name__ == "__main__":
    main()
