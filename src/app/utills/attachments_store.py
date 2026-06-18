from datetime import datetime
import logging
import pandas as pd
import PyPDF2
import requests
from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter
import chromadb
from chromadb.config import Settings
import uuid
import os
import traceback

from app.utills.data_inject_graph_db import store_pdf, store_txt, store_webpages

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def attachments_store_for_chroma(session_id=None,path_files=None):
    if path_files and session_id: 
        for file_path in path_files:
            if file_path.lower().endswith(".pdf"):
                try:
                    date_time = datetime.now().strftime("%Y%m%d%H%M%S%f")
                    file_name = os.path.basename(file_path)
                    file_id = f'{file_name}_{date_time}'
                    reader = PyPDF2.PdfReader(file_path)
                    num_pages = len(reader.pages)
                    for i in range(num_pages):
                        page = reader.pages[i]
                        page_content = page.extract_text()
                        page_number = i + 1
                        #split_texts = text_splitter.split_text(page_content)
            
                        chunk_id = f"{file_id}_page{page_number}"
                        chunk_data = {'id': chunk_id,'text': page_content,
                            'metadata': {
                                'file_id': file_id,
                                'file_name': file_name,
                                'file_type': 'PDF',
                                'page_number': page_number,
                                'created_at': datetime.now().isoformat()
                            }
                        }


                except Exception as e:
                    error_traceback = traceback.format_exc()
                    logger.error(f"Traceback:\n{error_traceback}")
