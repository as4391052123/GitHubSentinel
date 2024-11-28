
# src/llm.py

import os
import json
import requests
from requests.adapters import HTTPAdapter
import urllib3
from openai import OpenAI  # 导入OpenAI库用于访问GPT模型
from logger import LOG

# 常量定义
API_URL = 'https://api.yesapikey.com/v1/chat/completions'
MODEL_NAME = 'gpt-4o-mini'
DEFAULT_MAX_RETRIES = 5
DEFAULT_TIMEOUT = 30

class CustomHTTPClient:
    def __init__(self, api_key: str, proxy_url: str = None, max_retries: int = DEFAULT_MAX_RETRIES, timeout: int = DEFAULT_TIMEOUT):
        self.session = requests.Session()
        self.api_key = api_key
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
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


def _get_response(client, messages: list) -> str:
    data = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 1,
        "max_tokens": 1000,
        "top_p": 1
    }
    try:
        if isinstance(client, CustomHTTPClient):
            # 通过代理调用OpenAI GPT模型生成报告
            response = client.request("POST", API_URL, json_data=data)
        else:
            # 调用OpenAI GPT模型生成报告
            response = client.chat.completions.create(**data)
            LOG.debug("GPT response: {}", response)
            # 返回模型生成的内容
            return response.choices[0].message.content
        if response and response.get('choices'):
            content = response['choices'][0]['message']['content']
            return content
        else:
            LOG.error("No choices found in the response.")
    except Exception as e:
        LOG.error(f"An error occurred while getting the response: {e}")
    return ""


class LLM:
    def __init__(self, max_retries: int = DEFAULT_MAX_RETRIES, timeout: int = DEFAULT_TIMEOUT):
        self.proxy_url = os.getenv("OPENAI_PROXY_URL")
        self.max_retries = max_retries
        self.timeout = timeout
        self.api_key = os.getenv("OPENAI_API_KEY")
        # 根据proxy_url是否为None选择不同的客户端
        if self.proxy_url:
            self.client = CustomHTTPClient(self.api_key, self.proxy_url, max_retries, timeout)
        else:
            self.client = OpenAI()

        # 从TXT文件加载提示信息
        with open("./../prompts/report_prompt.txt", "r", encoding='utf-8') as file:
            self.default_prompt = file.read()

        # 配置日志文件，当文件大小达到1MB时自动轮转，日志级别为DEBUG
        LOG.add("logs/llm_logs.log", rotation="1 MB", level="DEBUG")

    def generate_daily_report(self, markdown_content: str, prompt: str = None, dry_run: bool = False) -> str:
        # 如果传入的prompt为空，则使用默认提示词
        if not prompt:
            prompt = self.default_prompt

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": markdown_content},
        ]

        if dry_run:
            LOG.info("Dry run mode enabled. Saving prompt to file.")
            with open("daily_progress/prompt.txt", "w+") as f:
                json.dump(messages, f, indent=4, ensure_ascii=False)
            LOG.debug("Prompt saved to daily_progress/prompt.txt")
            return "DRY RUN"

        LOG.info("Starting report generation using GPT model.")
        response_content = _get_response(self.client, messages)
        if response_content:
            LOG.debug(f"GPT response: {response_content}")
            return response_content
        else:
            LOG.error("Failed to get a valid response from the GPT model.")
            return ""