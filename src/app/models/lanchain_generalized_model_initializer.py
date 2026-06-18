import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, AzureChatOpenAI, OpenAIEmbeddings, AzureOpenAIEmbeddings
#from langchain_anthropic import ChatAnthropic
#from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
#from langchain_ollama import ChatOllama
#from flask import current_app


class LangChainGeneralizedChatModelInitializer:
    def __init__(self, config):
        self.chat_model_type = config.CHAT_MODEL_TYPE
        print(f"Initializing the model {self.chat_model_type}")

        if self.chat_model_type == "OPENAI":
            self.model_name = config.CHAT_MODEL_NAME
            self.llm = ChatOpenAI(model=self.model_name)

        # elif self.chat_model_type == "ANTHROPIC":
        #     self.model_name = config.CHAT_MODEL_NAME
        #     self.llm = ChatAnthropic(model=self.model_name)

        # elif self.chat_model_type == "AZURE":
        #     self.model_name = config.CHAT_MODEL_NAME
        #     self.azure_openai_deployment_name = config.AZURE_OPENAI_DEPLOYMENT_NAME
        #     self.llm = AzureChatOpenAI(azure_deployment=self.azure_openai_deployment_name)

        # elif self.chat_model_type == "GOOGLE":
        #     self.model_name = config.CHAT_MODEL_NAME
        #     self.llm = ChatGoogleGenerativeAI(model=self.model_name)
        
        # elif self.chat_model_type == "OLLAMA":
        #     self.model_name = config.CHAT_MODEL_NAME
        #     self.llm = ChatOllama(model=self.model_name)
        #     #self.llm = init_chat_model(f"ollama:{self.model_name}")
    


    def get_LLM(self):
        return self.llm
    
    def run_text_model(self,prompt: str,temperature: float = 0):
        return self.llm.invoke(prompt=prompt, temperature=temperature)
       



class LangChainGeneralizedEmbeddingModelInitializer:
    def __init__(self, config):
        # FIXED: Use config.get() instead of os.environ.get()
        self.embedding_model_type = config.EMBEDDINGS_MODEL_TYPE
        print(f"Initializing the embeddings model {self.embedding_model_type}")

        if self.embedding_model_type == "OPENAI":
            self.model_name = config.EMBEDDINGS_MODEL_NAME
            self.embeddings = OpenAIEmbeddings(model=self.model_name)

        # elif self.embedding_model_type == "ANTHROPIC":
        #     self.model_name = config.EMBEDDINGS_MODEL_NAME
        #     print("Warning: Anthropic does not provide embeddings. Falling back to OpenAI embeddings.")
        #     self.embeddings = OpenAIEmbeddings(model=self.model_name)

        # elif self.embedding_model_type == "AZURE":
        #     self.model_name = config.EMBEDDINGS_MODEL_NAME
        #     # FIXED: Use config.get() instead of os.environ.get()
        #     self.azure_openai_deployment_name = config.AZURE_OPENAI_DEPLOYMENT_NAME
        #     self.embeddings = AzureOpenAIEmbeddings(azure_deployment=self.azure_openai_deployment_name)

        # elif self.embedding_model_type == "GOOGLE":
        #     self.model_name = config.EMBEDDINGS_MODEL_NAME
        #     self.embeddings = GoogleGenerativeAIEmbeddings(model=self.model_name)
        
        else:
            # ADDED: Default case to ensure self.embeddings is always initialized
            print(f"Warning: Unknown embedding model type '{self.embedding_model_type}'. Using default OPENAI.")
            self.model_name = config.EMBEDDINGS_MODEL_NAME
            self.embeddings = OpenAIEmbeddings(model=self.model_name)

    def get_EMBEDDINGS(self):
        return self.embeddings
    
    def run_text_model(self,prompt: str,temperature: float = 0):
        return self.embeddings.invoke(prompt=prompt, temperature=temperature)
