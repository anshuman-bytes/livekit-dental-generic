def format_prompt(prompt_template: str, variables: dict) -> str:

import requests
import os
import yaml
from jinja2 import Template

BACKEND_API = os.getenv("BACKEND_API", "http://localhost:8000")
BACKEND_API_TOKEN = os.getenv("BACKEND_API_TOKEN", "")

def format_prompt(prompt_template: str, variables: dict) -> str:
    jinja_template = Template(prompt_template)
    prompt_to_render = jinja_template.render(**variables)
    final_prompt = prompt_to_render
    return final_prompt



class PromptManager:
    def __init__(self, prompt_file_path: str = None, customer_id: str = None):
        self.prompt_file = None
        if customer_id:
            self.prompt_file = self.load_prompts_from_api(customer_id)
        elif prompt_file_path:
            try:
                with open(prompt_file_path, "r") as f:
                    self.prompt_file = yaml.safe_load(f)
            except FileNotFoundError:
                print(f"Prompt file not found: {prompt_file_path}")
                raise FileNotFoundError(f"Prompt file not found: {prompt_file_path}")

    @staticmethod
    def load_prompts_from_api(customer_id: str):
        headers = {}
        if BACKEND_API_TOKEN:
            headers["Authorization"] = f"Bearer {BACKEND_API_TOKEN}"
        url = f"{BACKEND_API}/customer/{customer_id}/prompts"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return {}
        except Exception:
            return {}

    def get_prompt_with_variables(self, prompt_key: str, variables: dict) -> str:
        if not self.prompt_file:
            raise ValueError("Prompt file not loaded.")
        prompt_data = self.prompt_file.get(prompt_key, {})
        template = prompt_data.get("template", "")
        required_variables = prompt_data.get("variables", [])

        missing_variables = [var for var in required_variables if var not in variables]
        if missing_variables:
            raise ValueError(
                f"Missing variables for prompt '{prompt_key}': {missing_variables}"
            )

        return format_prompt(template, variables)
