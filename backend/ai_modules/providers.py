import os
import json
import time
import re
import logging
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)

class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Sends system and user prompts to the LLM and returns parsed JSON dict.
        """
        pass

    @abstractmethod
    def health_check(self) -> dict:
        """
        Performs a harmless check to verify endpoint reachability and authentication.
        """
        pass

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = os.getenv("OPENAI_API_KEY")
        self._client = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self.api_key:
                raise ValueError("OpenAI API Key is missing. Please configure it in AI Settings.")
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def health_check(self) -> dict:
        if not self.api_key:
            return {"success": False, "provider": "openai", "model": self.model, "message": "OpenAI API Key is required."}
        try:
            self.client.models.retrieve(self.model)
            return {"success": True, "provider": "openai", "model": self.model, "message": "OpenAI API connection verified."}
        except Exception as e:
            return {"success": False, "provider": "openai", "model": self.model, "message": f"OpenAI verification failed: {e}"}

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        start_time = time.time()
        logger.info(f"[LLMProvider: OpenAI] Sending generation request to model '{self.model}'")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            latency = round(time.time() - start_time, 3)
            content = response.choices[0].message.content.strip()
            logger.info(f"[LLMProvider: OpenAI] Successfully generated response in {latency}s")
            return json.loads(content)
        except Exception as e:
            latency = round(time.time() - start_time, 3)
            logger.error(f"[LLMProvider: OpenAI] Generation failed after {latency}s: {e}")
            raise RuntimeError(f"OpenAI Generation Error: {e}")

class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini Provider using OpenAI-compatible REST API endpoint.
    Base Endpoint: https://generativelanguage.googleapis.com/v1beta/openai
    Default Model: gemini-2.5-flash
    """
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None, endpoint: Optional[str] = None):
        self.model = model or "gemini-2.5-flash"
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if endpoint and any(domain in endpoint.lower() for domain in ["sarvam.ai", "openai.com", "anthropic.com"]):
            endpoint = None
        base_ep = endpoint or "https://generativelanguage.googleapis.com/v1beta/openai"
        self.endpoint = base_ep.rstrip('/')

    def _resolve_url(self) -> str:
        if self.endpoint.endswith("/chat/completions"):
            return self.endpoint
        return f"{self.endpoint}/chat/completions"

    def health_check(self) -> dict:
        if not self.api_key:
            return {"success": False, "provider": "gemini", "model": self.model, "message": "Gemini API Key is required."}
        url = self._resolve_url()
        logger.info(f"[LLMProvider: Gemini] Testing connection to {url} (model '{self.model}')")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in [200, 201]:
                    return {"success": True, "provider": "gemini", "model": self.model, "message": "Google Gemini API connection verified."}
                return {"success": False, "provider": "gemini", "model": self.model, "message": f"Gemini API returned status {resp.status}"}
        except urllib.error.HTTPError as he:
            return {"success": False, "provider": "gemini", "model": self.model, "message": f"Gemini API returned HTTP {he.code}: {he.reason}"}
        except Exception as e:
            return {"success": False, "provider": "gemini", "model": self.model, "message": f"Gemini connection failed: {e}"}

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.api_key:
            raise ValueError("Gemini API Key is missing. Please configure it in AI Settings.")
        url = self._resolve_url()
        start_time = time.time()
        logger.info(f"[LLMProvider: Gemini] Sending generation request to model '{self.model}' at '{url}'")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"}
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw_data = resp.read().decode('utf-8')
                res = json.loads(raw_data)

            latency = round(time.time() - start_time, 3)
            choices = res.get("choices", [])
            if not choices:
                raise ValueError("Gemini API returned empty choices response.")

            content = choices[0].get("message", {}).get("content", "").strip()
            logger.info(f"[LLMProvider: Gemini] Successfully generated response in {latency}s")
            return self._parse_json(content)
        except Exception as e:
            latency = round(time.time() - start_time, 3)
            logger.error(f"[LLMProvider: Gemini] Generation failed after {latency}s: {e}")
            raise RuntimeError(f"Gemini LLM Error: {e}")

    def _parse_json(self, content: str) -> dict:
        clean = content.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Malformed JSON returned by Gemini: {content[:200]}")

class ClaudeProvider(BaseLLMProvider):
    """
    Anthropic Claude Provider using Anthropic v1 Messages API.
    Default Base Endpoint: https://api.anthropic.com/v1
    Default Model: claude-3-5-sonnet-20241022
    """
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or "claude-3-5-sonnet-20241022"
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        self.endpoint = "https://api.anthropic.com/v1/messages"

    def health_check(self) -> dict:
        if not self.api_key:
            return {"success": False, "provider": "claude", "model": self.model, "message": "Claude/Anthropic API Key is required."}
        payload = {
            "model": self.model,
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "ping"}]
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        try:
            req = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in [200, 201]:
                    return {"success": True, "provider": "claude", "model": self.model, "message": "Claude API connection verified."}
            return {"success": False, "provider": "claude", "model": self.model, "message": f"Claude API status {resp.status}"}
        except urllib.error.HTTPError as he:
            return {"success": False, "provider": "claude", "model": self.model, "message": f"Claude API returned HTTP {he.code}: {he.reason}"}
        except Exception as e:
            return {"success": False, "provider": "claude", "model": self.model, "message": f"Claude connection failed: {e}"}

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.api_key:
            raise ValueError("Claude API Key is missing. Please configure it in AI Settings.")
        start_time = time.time()
        logger.info(f"[LLMProvider: Claude] Sending generation request to model '{self.model}'")
        
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        try:
            req = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw_data = resp.read().decode('utf-8')
                res = json.loads(raw_data)

            latency = round(time.time() - start_time, 3)
            content_blocks = res.get("content", [])
            if not content_blocks:
                raise ValueError("Claude returned empty content response.")

            content = content_blocks[0].get("text", "").strip()
            logger.info(f"[LLMProvider: Claude] Successfully generated response in {latency}s")
            return self._parse_json(content)
        except Exception as e:
            latency = round(time.time() - start_time, 3)
            logger.error(f"[LLMProvider: Claude] Generation failed after {latency}s: {e}")
            raise RuntimeError(f"Claude LLM Error: {e}")

    def _parse_json(self, content: str) -> dict:
        clean = content.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Malformed JSON returned by Claude: {content[:200]}")

class SarvamProvider(BaseLLMProvider):
    """
    Sarvam AI Provider (India LLM platform).
    Default Base Endpoint: https://api.sarvam.ai/v1
    Default Model: sarvam-2b
    """
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None, endpoint: Optional[str] = None):
        self.model = model or "sarvam-2b"
        self.api_key = api_key or os.getenv("SARVAM_API_KEY")
        if endpoint and any(domain in endpoint.lower() for domain in ["googleapis.com", "openai.com", "anthropic.com"]):
            endpoint = None
        base_ep = endpoint or "https://api.sarvam.ai/v1"
        self.endpoint = base_ep.rstrip('/')

    def _resolve_url(self) -> str:
        if self.endpoint.endswith("/chat/completions"):
            return self.endpoint
        return f"{self.endpoint}/chat/completions"

    def health_check(self) -> dict:
        if not self.api_key:
            return {"success": False, "provider": "sarvam", "model": self.model, "message": "Sarvam API Key is required."}
        url = self._resolve_url()
        logger.info(f"[LLMProvider: Sarvam] Testing connection to {url} (model '{self.model}')")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in [200, 201]:
                    return {"success": True, "provider": "sarvam", "model": self.model, "message": "Sarvam AI connection verified."}
                return {"success": False, "provider": "sarvam", "model": self.model, "message": f"Sarvam API returned status {resp.status}"}
        except urllib.error.HTTPError as he:
            return {"success": False, "provider": "sarvam", "model": self.model, "message": f"Sarvam API returned HTTP {he.code}: {he.reason}"}
        except Exception as e:
            return {"success": False, "provider": "sarvam", "model": self.model, "message": f"Sarvam connection failed: {e}"}

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.api_key:
            raise ValueError("Sarvam API Key is missing. Please configure it in AI Settings.")
        url = self._resolve_url()
        start_time = time.time()
        logger.info(f"[LLMProvider: Sarvam] Sending generation request to model '{self.model}' at '{url}'")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"}
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw_data = resp.read().decode('utf-8')
                res = json.loads(raw_data)

            latency = round(time.time() - start_time, 3)
            choices = res.get("choices", [])
            if not choices:
                raise ValueError("Sarvam API returned empty choices response.")

            content = choices[0].get("message", {}).get("content", "").strip()
            logger.info(f"[LLMProvider: Sarvam] Successfully generated response in {latency}s")
            return self._parse_json(content)
        except Exception as e:
            latency = round(time.time() - start_time, 3)
            logger.error(f"[LLMProvider: Sarvam] Generation failed after {latency}s: {e}")
            raise RuntimeError(f"Sarvam LLM Error: {e}")

    def _parse_json(self, content: str) -> dict:
        clean = content.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Malformed JSON returned by Sarvam: {content[:200]}")

class QwenProvider(BaseLLMProvider):
    def __init__(self, model: Optional[str] = None, endpoint: Optional[str] = None):
        self.model = model or os.getenv("QWEN_MODEL", "qwen2.5-coder:3b")
        self.ollama_url = endpoint or os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

    def health_check(self) -> dict:
        try:
            tags_url = self.ollama_url.replace("/api/chat", "/api/tags")
            req = urllib.request.Request(tags_url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return {"success": True, "provider": "ollama", "model": self.model, "message": "Ollama server connected."}
            return {"success": False, "provider": "ollama", "model": self.model, "message": "Ollama server connection error."}
        except Exception as e:
            return {"success": False, "provider": "ollama", "model": self.model, "message": f"Ollama connection failed: {e}"}

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        start_time = time.time()
        logger.info(f"[LLMProvider: Qwen/Ollama] Sending generation request to model '{self.model}' at '{self.ollama_url}'")
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0
            }
        }
        
        try:
            req = urllib.request.Request(
                self.ollama_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw_data = resp.read().decode('utf-8')
                res = json.loads(raw_data)
                
            latency = round(time.time() - start_time, 3)
            content = res.get("message", {}).get("content", "").strip()
            logger.info(f"[LLMProvider: Qwen/Ollama] Successfully generated response in {latency}s")
            
            if not content:
                raise ValueError("Qwen/Ollama returned empty message content.")
            
            parsed_json = self._parse_json(content)
            return parsed_json
        except Exception as e:
            latency = round(time.time() - start_time, 3)
            logger.error(f"[LLMProvider: Qwen/Ollama] Generation failed after {latency}s: {e}")
            raise RuntimeError(f"Qwen/Ollama Generation Error: {e}")

    def _parse_json(self, content: str) -> dict:
        clean = content.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Malformed JSON returned by Qwen: {content[:200]}")

class CustomProvider(BaseLLMProvider):
    def __init__(self, endpoint: str, model: str, api_key: Optional[str] = None):
        self.endpoint = (endpoint or "").rstrip('/')
        self.model = model or "custom-model"
        self.api_key = api_key

    def _resolve_url(self) -> str:
        if not self.endpoint:
            return "http://localhost:8000/v1/chat/completions"
        if self.endpoint.endswith("/chat/completions"):
            return self.endpoint
        if self.endpoint.endswith("/v1"):
            return f"{self.endpoint}/chat/completions"
        return f"{self.endpoint}/v1/chat/completions" if "/v1" not in self.endpoint else f"{self.endpoint}/chat/completions"

    def health_check(self) -> dict:
        url = self._resolve_url()
        logger.info(f"[LLMProvider: Custom] Testing connection to {url} (model '{self.model}')")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in [200, 201]:
                    return {
                        "success": True,
                        "provider": "custom",
                        "model": self.model,
                        "message": "AI provider endpoint connected successfully."
                    }
                return {
                    "success": False,
                    "provider": "custom",
                    "model": self.model,
                    "message": f"Endpoint responded with HTTP status {resp.status}"
                }
        except urllib.error.HTTPError as he:
            return {
                "success": False,
                "provider": "custom",
                "model": self.model,
                "message": f"Provider endpoint returned HTTP {he.code}: {he.reason}"
            }
        except Exception as e:
            return {
                "success": False,
                "provider": "custom",
                "model": self.model,
                "message": f"Connection failed: {str(e)}"
            }

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        url = self._resolve_url()
        start_time = time.time()
        logger.info(f"[LLMProvider: Custom] Sending generation request to model '{self.model}' at '{url}'")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"}
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw_data = resp.read().decode('utf-8')
                res = json.loads(raw_data)

            latency = round(time.time() - start_time, 3)
            choices = res.get("choices", [])
            if not choices:
                raise ValueError("Provider returned empty choices response.")

            content = choices[0].get("message", {}).get("content", "").strip()
            logger.info(f"[LLMProvider: Custom] Successfully generated response in {latency}s")
            return self._parse_json(content)
        except Exception as e:
            latency = round(time.time() - start_time, 3)
            logger.error(f"[LLMProvider: Custom] Generation failed after {latency}s: {e}")
            raise RuntimeError(f"LLM Provider Error: {e}")

    def _parse_json(self, content: str) -> dict:
        clean = content.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Malformed JSON returned by LLM: {content[:200]}")

# Alias for backward compatibility
OllamaProvider = QwenProvider

def get_llm_provider(target: str = "generator") -> BaseLLMProvider:
    """
    Returns configured BaseLLMProvider instance for target ('generator' or 'verifier').
    Checks HADIL Metadata DB first; falls back to environment variables.
    """
    try:
        from services.metadata_service import metadata_service
        config = metadata_service.get_llm_config_internal(target)
        p_type = (config.get("provider_type") or "").lower().strip()
        
        if p_type == "sarvam":
            return SarvamProvider(
                model=config.get("model"),
                api_key=config.get("api_key"),
                endpoint=config.get("endpoint")
            )
        elif p_type in ["gemini", "google"]:
            return GeminiProvider(
                model=config.get("model"),
                api_key=config.get("api_key"),
                endpoint=config.get("endpoint")
            )
        elif p_type in ["claude", "anthropic"]:
            return ClaudeProvider(
                model=config.get("model"),
                api_key=config.get("api_key")
            )
        elif p_type == "custom":
            return CustomProvider(
                endpoint=config.get("endpoint"),
                model=config.get("model"),
                api_key=config.get("api_key")
            )
        elif p_type in ["qwen", "ollama"]:
            return QwenProvider(
                model=config.get("model"),
                endpoint=config.get("endpoint")
            )
        elif p_type == "openai":
            return OpenAIProvider(
                model=config.get("model"),
                api_key=config.get("api_key")
            )
    except Exception as err:
        logger.warning(f"Could not load LLM config from metadata DB for target '{target}': {err}")

    # Fallback to environment variables
    provider_type = os.getenv("LLM_PROVIDER", "openai").lower().strip()
    if provider_type == "sarvam":
        return SarvamProvider()
    elif provider_type in ["gemini", "google"]:
        return GeminiProvider()
    elif provider_type in ["claude", "anthropic"]:
        return ClaudeProvider()
    elif provider_type in ["qwen", "ollama"]:
        return QwenProvider()
    return OpenAIProvider()
