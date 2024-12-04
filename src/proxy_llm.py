import os
import json
from datetime import datetime
from json import JSONDecodeError

import requests
from requests.adapters import HTTPAdapter
import urllib3
from openai import OpenAI  # 导入OpenAI库用于访问GPT模型
from logger import LOG

# 常量定义
API_URL = 'https://api.yesapikey.com/v1/chat/completions'
OLLAMA_API_URL = "http://localhost:11434/api/chat"
DEFAULT_MAX_RETRIES = 5
DEFAULT_TIMEOUT = 2000


class CustomHTTPClient:
    def __init__(self, api_key: str = None, proxy_url: str = None, max_retries: int = DEFAULT_MAX_RETRIES, timeout: int = DEFAULT_TIMEOUT):
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            })
        if proxy_url:
            self.session.proxies = {
                "http": proxy_url,
                "https": proxy_url
            }

        # 设置重试策略
        retry_strategy = urllib3.Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.timeout = timeout

    def request(self, method: str, url: str, json_data: dict = None) -> dict:
        try:
            response = self.session.request(method, url, json=json_data, timeout=self.timeout)
            response.raise_for_status()  # 检查请求是否成功
            return response.json()
        except requests.exceptions.RequestException as e:
            LOG.error(f"Request failed: {e}")
            return {}


def _get_response(client, model_type: str = "openai", model_name: str = "gpt-4o-mini", messages: list = None) -> str:
    request_api_url = API_URL
    if model_type == "ollama":
        data = {
            "model": model_name,
            "messages": messages,
            "max_tokens": 10000,
            "context_length": 10000,
            "top_p": 1,
            "temperature": 1,
            "stream": False
        }
        request_api_url = OLLAMA_API_URL
    else:
        data = {
            "model": model_name,
            "messages": messages,
            "temperature": 1,
            "max_tokens": 100,
            "top_p": 1
        }

    try:
        if model_type == "openai":
            response = client.chat.completions.create(**data)
            LOG.debug("GPT response: %s", response)
            return response.choices[0].message.content
        else:
            response = client.request("POST", request_api_url, json_data=data)
            if model_type == "yesapi":
                choices = response.get('choices')
                if choices:
                    return choices[0]['message']['content']
                else:
                    LOG.error("No choices found in the response.")
                    return ""
            elif model_type == "ollama":
                message_content = response.get("message", {}).get("content")
                if message_content:
                    return message_content
                else:
                    LOG.error(f"无法从响应中提取报告内容。{response.text}")
                    raise ValueError("Ollama API 返回的响应结构无效")
    except Exception as e:
        LOG.error(f"An error occurred while getting the response: {e}")
    return ""


class LLM:
    def __init__(self, max_retries: int = DEFAULT_MAX_RETRIES, model_type: str = "openai", model_name: str = "gpt-4o-mini", prompt_file_path: str = "prompts/github_openai_report_prompt.txt", timeout: int = DEFAULT_TIMEOUT):
        self.max_retries = max_retries
        self.timeout = timeout
        self.prompt_file_path = prompt_file_path
        self.model_type = model_type
        self.model_name = model_name
        if model_type == "openai":
            self.client = OpenAI()
        elif model_type == "yesapi":
            self.proxy_url = API_URL
            self.api_key = os.getenv("OPENAI_API_KEY")
            self.client = CustomHTTPClient(self.api_key, self.proxy_url, max_retries, timeout)
        elif model_type == "ollama":
            self.proxy_url = OLLAMA_API_URL
            self.client = CustomHTTPClient(None, self.proxy_url, max_retries, timeout)

        with open(self.prompt_file_path, "r", encoding='utf-8') as file:
            self.default_prompt = file.read()

        LOG.add("logs/llm_logs.log", rotation="1 MB", level="DEBUG")

    def generate_github_daily_report(self, markdown_content: str, prompt: str = None, dry_run: bool = False) -> str:
        if not prompt:
            prompt = self.default_prompt

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": markdown_content},
        ]

        if dry_run:
            LOG.info("Dry run mode enabled. Saving prompt to file.")
            with open(self.prompt_file_path, "w+") as f:
                json.dump(messages, f, indent=4, ensure_ascii=False)
            LOG.debug(f"Prompt saved to {self.prompt_file_path}")
            return "DRY RUN"

        LOG.info(f"Starting report generation using {self.model_type}--{self.model_name} model.")
        response_content = _get_response(client=self.client, model_type=self.model_type, model_name=self.model_name, messages=messages)
        if response_content:
            LOG.debug(f"GPT response: {response_content}")
            return response_content
        else:
            LOG.error("Failed to get a valid response from the GPT model.")
            return ""

    def generate_hn_daily_report(self, markdown_content: str, prompt: str = None, dry_run: bool = False) -> str:
        if not prompt:
            prompt = self.default_prompt

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": markdown_content},
        ]

        if dry_run:
            LOG.info("Dry run mode enabled. Saving prompt to file.")
            with open(self.prompt_file_path, "w+") as f:
                json.dump(messages, f, indent=4, ensure_ascii=False)
            LOG.debug(f"Prompt saved to {self.prompt_file_path}")
            return "DRY RUN"

        LOG.info(f"Starting report generation using {self.model_type}--{self.model_name} model.")
        response_content = _get_response(client=self.client, model_type=self.model_type, model_name=self.model_name, messages=messages)
        if response_content:
            LOG.debug(f"GPT response: {response_content}")
            return response_content
        else:
            LOG.error("Failed to get a valid response from the GPT model.")
            return ""


if __name__ == '__main__':
    llm = LLM(model_type="ollama", model_name="llama3.2", prompt_file_path="./../prompts/hacker_news_daily_report_ollama_prompt.txt")
    markdown_content = """
# Progress for langchain-ai/langchain (2024-08-20 to 2024-08-21)

## Issues Closed in the Last 1 Days
- partners/chroma: release 0.1.3 #25599
- docs: few-shot conceptual guide #25596
- docs: update examples in api ref #25589
"""

    # 示例：生成 GitHub 报告
    system_prompt = "Your specific system prompt for GitHub report generation"
    github_report = llm.generate_hn_daily_report(system_prompt, markdown_content)
    LOG.debug(github_report)
    print(github_report)
