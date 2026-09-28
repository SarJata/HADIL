# Models

Git does not store MiniLM weights.

For a production EXE, put Hugging Face `sentence-transformers/all-MiniLM-L6-v2` files in:

`models/all-MiniLM-L6-v2/`

`packaging/build.py` checks for `model.safetensors` in that directory before PyInstaller runs.
