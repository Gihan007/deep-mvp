import csv
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
#from langchain.text_splitter import RecursiveCharacterTextSplitter
#from langchain.text_splitter.recursive import RecursiveCharacterTextSplitter

import time
from openai import OpenAI
from datetime import datetime
import logging
import traceback
import PyPDF2
import chromadb
from chromadb.config import Settings
import base64
from app.utills.inteligent_pdf_data_extractor import pdf_data_extract
import json
import uuid

from config import get_config
config = get_config()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHROMA_DB_PATH = config.CHROMA_DB_PATH
CHROMA_COLLECTION_NAME = config.CHROMA_COLLECTION_NAME

CHROMA_IMAGE_DB_PATH = config.CHROMA_DB_PATH
# CHROMA_IMAGE_COLLECTION_NAME = config.CHROMA_IMAGE_COLLECTION_NAME

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
chroma_image_client = chromadb.PersistentClient(path=CHROMA_IMAGE_DB_PATH)


def generate_embeddings(texts, embeddings):
    """Generate embeddings for a list of texts using provided embedding model."""
    try:
        return embeddings.embed_documents(texts)
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        return None


def store_data(chunks, embeddings, type=None):
    """Store JSON chunks with embeddings in ChromaDB"""
    try:
        collection = chroma_client.get_or_create_collection(name=CHROMA_COLLECTION_NAME)
        texts = [str(chunk.get("text", "")) for chunk in chunks]
        #logger.info(f"Generating embeddings for {len(texts)} {type} chunks...")
        #vectors = generate_embeddings(texts, embeddings)
        #if vectors is None:
        #    raise Exception("Failed to generate embeddings")

        ids = [chunk["id"] for chunk in chunks]
        documents = texts
        metadatas = [chunk.get("metadata", {}) for chunk in chunks] 

        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        logger.info(f"Successfully stored {len(chunks)} {type} chunks with embeddings in local ChromaDB at {CHROMA_DB_PATH}")
    except Exception as e:
        logger.error(f"Error storing {type} chunks: {str(e)}")
        raise


def user_data_store(path_images, path_files, path_audios, session_id, question, embeddings, llm):
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    file_exts = {".pdf", ".docx", ".txt", ".xlsx", ".csv", ".json"}
    audio_exts = {".mp3", ".wav", ".m4a", ".ogg"}

    # Images: store the question as text (for now) and image as metadata (base64)
    for image_path in path_images:
        ext = os.path.splitext(image_path)[1].lower()
        if ext in image_exts:
            image_base64 = base64.b64encode(open(image_path, "rb").read()).decode("utf-8")
            image_data = {
                "id": f"{session_id}_image_{uuid.uuid4().hex}",
                "text": question,
                "metadata": {
                    "file_type": "IMAGE",
                    "created_at": datetime.now().isoformat(),
                    "image_data_base64": image_base64,
                    "source_path": image_path,
                },
            }
            store_data(chunks=[image_data], embeddings=embeddings, type="IMAGE")

    # Files: extract text appropriately and store
    for file_path in path_files:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in file_exts:
            file_base64 = base64.b64encode(open(file_path, "rb").read()).decode("utf-8")

            if ext == ".pdf":
                text = pdf_data_extract(file_path, file_base64, llm)
                pdf_chunk = {
                    "id": f"{session_id}_pdf_{uuid.uuid4().hex}",
                    "text": text,
                    "metadata": {
                        "file_type": "PDF",
                        "created_at": datetime.now().isoformat(),
                        "data_base64": file_base64,
                        "question": question,
                        "source_path": file_path,
                    },
                }
                store_data(chunks=[pdf_chunk], embeddings=embeddings, type="PDF")

            if ext == ".json":
                json_text = open(file_path, "r", encoding="utf-8").read()
                json_chunk = {
                    "id": f"{session_id}_json_{uuid.uuid4().hex}",
                    "text": json_text,
                    "metadata": {
                        "file_type": "JSON",
                        "created_at": datetime.now().isoformat(),
                        "question": question,
                        "source_path": file_path,
                    },
                }
                store_data(chunks=[json_chunk], embeddings=embeddings, type="JSON")

            if ext == ".txt":
                txt_text = open(file_path, "r", encoding="utf-8").read()
                txt_chunk = {
                    "id": f"{session_id}_txt_{uuid.uuid4().hex}",
                    "text": txt_text,
                    "metadata": {
                        "file_type": "TXT",
                        "created_at": datetime.now().isoformat(),
                        "question": question,
                        "source_path": file_path,
                    },
                }
                store_data(chunks=[txt_chunk], embeddings=embeddings, type="TXT")

            if ext == ".csv":
                csv_text = open(file_path, "r", encoding="utf-8").read()
                csv_chunk = {
                    "id": f"{session_id}_csv_{uuid.uuid4().hex}",
                    "text": csv_text,
                    "metadata": {
                        "file_type": "CSV",
                        "created_at": datetime.now().isoformat(),
                        "question": question,
                        "source_path": file_path,
                    },
                }
                store_data(chunks=[csv_chunk], embeddings=embeddings, type="CSV")
