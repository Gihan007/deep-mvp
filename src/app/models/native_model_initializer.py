import os
from dotenv import load_dotenv
import openai
import anthropic
#from google import genai as google_genai
import google.generativeai as google_genai
from openai import AzureOpenAI

class NativeChatModelInitializer:

    def __init__(self, config):
        
        self.chat_model_type = config.get('CHAT_MODEL_TYPE')
        print(f"Initializing the model {self.chat_model_type}")

        if self.chat_model_type == "OPENAI":
            openai.api_key = config.get("OPENAI_API_KEY")
            self.model_name = config.get("CHAT_MODEL_NAME", "gpt-4o")
            self.client = openai.OpenAI()

        elif self.chat_model_type == "ANTHROPIC":
            self.model_name = config.get("CHAT_MODEL_NAME", "claude-3-5-sonnet-20240620")
            self.client = anthropic.Anthropic(api_key=config.get("ANTHROPIC_API_KEY"))

        elif self.chat_model_type == "AZURE":
            self.model_name = config.get("CHAT_MODEL_NAME", "gpt-4o")
            self.azure_endpoint = config.get("AZURE_OPENAI_ENDPOINT")
            self.azure_api_key = config.get("AZURE_OPENAI_API_KEY")
            self.azure_deployment = config.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
            self.client = AzureOpenAI(
                api_key=self.azure_api_key,
                api_version="2024-02-01",
                azure_endpoint=self.azure_endpoint
            )

        elif self.chat_model_type == "GOOGLE":
            self.model_name = config.get("CHAT_MODEL_NAME", "gemini-1.5-pro")
            self.client = google_genai.Client(api_key=config.get("GOOGLE_API_KEY"))

    def get_LLM(self):
        """Return the initialized LLM client instance."""
        return self.client

    def run_text_model(self, prompt: str, temperature: float = 0):
        if self.chat_model_type == "OPENAI":
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message["content"]

        elif self.chat_model_type == "ANTHROPIC":
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=1024,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text

        elif self.chat_model_type == "AZURE":
            response = self.client.chat.completions.create(
                model=self.azure_deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message["content"]

        elif self.chat_model_type == "GOOGLE":
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.candidates[0].content.parts[0].text