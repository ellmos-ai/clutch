"""Kupplung -- Provider-neutrale LLM Orchestration Engine.

Auto-Metapher:
  Fahrer   = Orchestrator (beliebiges LLM)
  Strecke  = Task/Aufgabe
  Getriebe = Modelle aller Provider (Claude, Gemini, Ollama...)
  Gang     = Ein konkretes Modell
  Gas      = Reasoning-Level hoch (mehr Tokens, gruendlicher)
  Bremse   = Reasoning-Level runter (weniger Tokens, direkter)
  Kupplung = Modellwechsel (Gang einlegen)
  Tacho    = Metriken
  Tankuhr  = Budget-Tracking
"""

__version__ = "0.3.0"

from clutch.fahrer import Fahrer
from clutch.strecke import StreckenAnalyse, StreckenTyp
from clutch.getriebe import Getriebe, Gang
from clutch.kupplung import Kupplung
from clutch.motorblock import MotorBlock, MotorErgebnis

__all__ = [
    "Fahrer", "StreckenAnalyse", "StreckenTyp",
    "Getriebe", "Gang", "Kupplung",
    "MotorBlock", "MotorErgebnis",
]
