"""Búsqueda web real (Fase I, rama Research — ver plan de expansión
"Inteligencia Ejecutiva"). Vendor decidido: Tavily — API construida
específicamente para agentes/LLM, REST simple, pricing por request. Mismo
criterio lazy-client-desde-env-var que el resto de las Capacidades de este
repo (ver Notion): sin `TAVILY_API_KEY` real, `available` es `False` y
`search()` nunca se llama — nunca se inventa un resultado."""

import os

import requests

from snarf.capabilities.base import Capability

API_URL = "https://api.tavily.com/search"
DEFAULT_MAX_RESULTS = 5
REQUEST_TIMEOUT_SECONDS = 20


class TavilySearch(Capability):
    name = "tavily_search"

    def __init__(self):
        self._api_key = os.environ.get("TAVILY_API_KEY")

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def search(self, query: str, max_results: int = DEFAULT_MAX_RESULTS, include_answer: bool = True) -> dict:
        if not self.available:
            raise RuntimeError("TAVILY_API_KEY no configurada. Definila en .env (ver .env.example).")
        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": include_answer,
        }
        response = requests.post(API_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        return {
            "answer": data.get("answer"),
            "results": [
                {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
                for r in data.get("results", [])
            ],
        }
