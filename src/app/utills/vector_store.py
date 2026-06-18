#from langchain.vectorstores import Chroma
from langchain_community.vectorstores import Chroma

#from langchain.embeddings import OpenAIEmbeddings
from langchain_openai import OpenAIEmbeddings

from langchain_community.vectorstores import Neo4jVector
#from flask import current_app



class VectorStoreBuilder:
    def __init__(self, embeddings, config):

        self.embeddings = embeddings
        self.config = config

    def create_chroma_vector_store(self):
        vector_store = Chroma(
            persist_directory=self.config.CHROMA_DB_PATH,
            embedding_function=self.embeddings,
            collection_name=self.config.CHROMA_COLLECTION_NAME
        )
        return vector_store
    
    
    def create_graphDB_vector_store(self):
        # Create empty vector store first
        vector_store = Neo4jVector(
            embedding=self.embeddings,
            url=self.config.NEO4J_URI,
            username=self.config.NEO4J_USERNAME,
            password=self.config.NEO4J_PASSWORD,
            index_name=self.config.NEO4J_INDEX_NAME,
            node_label=self.config.NEO4J_NODE_LABEL,
            text_node_property=self.config.NEO4J_TEXT_NODE_PROPERTY,
            embedding_node_property=self.config.NEO4J_EMBEDDING_NODE_PROPERTY
        )
        return vector_store

    def create_grapgDB_vector_store(self):
        # Deprecated alias for backward compatibility
        return self.create_graphDB_vector_store()
