import sys
import numpy as np
from embedding_manager import list_embeddings, delete_embedding, delete_empty_shape_embeddings

def print_usage():
    print("Usage:")
    print("  python gui_agents/s2/utils/embedding_cli.py list <embeddings_path>")
    print("  python gui_agents/s2/utils/embedding_cli.py delete <embeddings_path> <key>")
    print("  python gui_agents/s2/utils/embedding_cli.py clean_empty <embeddings_path>")
    print("Example:")

    """
    kb_s2/darwin/embeddings.pkl
    """

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    cmd = sys.argv[1]
    embeddings_path = sys.argv[2]

    if cmd == "list":
        info = list_embeddings(embeddings_path)
        for k, v in info.items():
            print(f"Key: {k}, Shape: {v['shape']}, Preview: {v['preview']}")
    elif cmd == "delete":
        if len(sys.argv) != 4:
            print_usage()
            sys.exit(1)
        key = sys.argv[3]
        delete_embedding(embeddings_path, key)
    elif cmd == "clean_empty":
        deleted = delete_empty_shape_embeddings(embeddings_path)
        print(f"Deleted {deleted} empty embeddings.")
    else:
        print_usage()