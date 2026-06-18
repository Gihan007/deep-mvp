import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_openai import AzureChatOpenAI

from langchain_openai import OpenAIEmbeddings
# Anthropic currently doesn't provide embeddings API — placeholder
from langchain_openai import AzureOpenAIEmbeddings

# Optional dependency: keep import-time safe when Google GenAI isn't installed.
try:
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
except Exception:  # ImportError (or any packaging-related issue)
    ChatGoogleGenerativeAI = None  # type: ignore
    GoogleGenerativeAIEmbeddings = None  # type: ignore


class LangChainChatModelInitializer:
    def __init__(self, config):
        self.chat_model_type = config.get('CHAT_MODEL_TYPE')
        print(f"Initializing the model {self.chat_model_type}")

        if self.chat_model_type == "OPENAI":
            self.model_name = config.get("CHAT_MODEL_NAME", "gpt-4.1")
            self.llm = ChatOpenAI(
                model=self.model_name,
                temperature=0,
                api_key=os.getenv("OPENAI_API_KEY")
            )

        elif self.chat_model_type == "ANTHROPIC":
            self.model_name = config.get("CHAT_MODEL_NAME", "claude-3-5-sonnet-latest")
            self.llm = ChatAnthropic(
                model=self.model_name,
                temperature=0,
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )

        elif self.chat_model_type == "AZURE":
            self.model_name = config.get("CHAT_MODEL_NAME", "gpt-4o")
            self.azure_openai_deployment_name = config.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
            self.llm = AzureChatOpenAI(
                model=self.model_name,
                azure_deployment=self.azure_openai_deployment_name,
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                temperature=0
            )

        elif self.chat_model_type == "GOOGLE":
            self.model_name = config.get("CHAT_MODEL_NAME", "gemini-1.5-flash")
            if ChatGoogleGenerativeAI is None:
                raise ModuleNotFoundError(
                    "langchain_google_genai is not installed. Install 'langchain-google-genai' to use GOOGLE chat models."
                )
            self.llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=0,
                google_api_key=os.getenv("GOOGLE_API_KEY")
            )

    def get_LLM(self):
        return self.llm
    
    def run_text_model(self, prompt: str, temperature: float = 0):
        return self.llm.invoke(prompt)
    



class LangChainEmbeddingModelInitializer:
    def __init__(self, config):
        self.embedding_model_type = os.environ.get('EMBEDDINGS_MODEL_TYPE')
        print(f"Initializing the embeddings model {self.embedding_model_type}")

        if self.embedding_model_type == "OPENAI":
            self.model_name = config.get("EMBEDDINGS_MODEL_NAME", "text-embedding-3-small")
            self.embeddings = OpenAIEmbeddings(
                model=self.model_name,
                api_key=os.getenv("OPENAI_API_KEY")
            )

        elif self.embedding_model_type == "AZURE":
            self.model_name = config.get("EMBEDDINGS_MODEL_NAME", "text-embedding-3-small")
            self.azure_openai_deployment_name = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME', "")
            self.embeddings = AzureOpenAIEmbeddings(
                model=self.model_name,
                azure_deployment=self.azure_openai_deployment_name,
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )

        elif self.embedding_model_type == "GOOGLE":
            self.model_name = config.get("EMBEDDINGS_MODEL_NAME", "embedding-001")
            if GoogleGenerativeAIEmbeddings is None:
                raise ModuleNotFoundError(
                    "langchain_google_genai is not installed. Install 'langchain-google-genai' to use GOOGLE embeddings."
                )
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model=self.model_name,
                google_api_key=os.getenv("GOOGLE_API_KEY")
            )

        elif self.embedding_model_type == "ANTHROPIC":
            raise NotImplementedError("Anthropic does not provide an embeddings API.")

        else:
            raise ValueError(f"Unsupported embeddings model type: {self.embedding_model_type}")

    def get_EMBEDDINGS(self):
        return self.embeddings

    def embed_text(self, text: str):
        """Return vector representation of the given text"""
        return self.embeddings.embed_query(text)
