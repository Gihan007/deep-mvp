import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

class GroqInitializer:
    def __init__(self):
        load_dotenv()
        self.api_key = os.environ.get('GROQ_API')
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        os.environ["GROQ_API_KEY"] = self.api_key
        print("Initializing the model")

    def run_groq_model(
        self,
        prompt: str,
        model_name: str = "mixtral-8x7b-32768",
        temperature: float = 0.2
    ):
        llm = ChatGroq(model_name=model_name, temperature=temperature)
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content

