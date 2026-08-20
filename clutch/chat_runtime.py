"""ChatRuntime -- Konversationsschicht ueber dem clutch-Router.

Sitzt zwischen Interfaces (CLI-REPL, Web, API) und der Engine. Pro Nachricht:
  1. Session laden (Profil, system_prompt_on, model_override).
  2. Vollprompt bauen: optional CLUTCH.md-Systemprompt + mitgesendete Prompts
     (aus dem toolset-Profil via Prompt-Bibliothek) voranstellen.
  3. Routen + ausfuehren via Fahrer (Routing + Motorblock).
  4. User- und Assistant-Nachricht im SessionStore persistieren.

Recycling-Vorbild: BACH hub/_services/chat/chat_runtime.py (Tool-Loop/Backends),
hier auf clutch-Routing reduziert und ohne BACH-spezifische Tools.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from clutch.fahrer import Fahrer
from clutch.motorblock import MotorBlock
from clutch.session_store import SessionStore, ChatSession
from clutch.prompt_library import PromptLibrary
from clutch.profile_manager import ProfileManager


class ChatRuntime:
    """Konversations-Runtime: Multi-Turn-Chat ueber den clutch-Router."""

    def __init__(
        self,
        fahrer: Optional[Fahrer] = None,
        session_store: Optional[SessionStore] = None,
        prompt_library: Optional[PromptLibrary] = None,
        profile_manager: Optional[ProfileManager] = None,
        handler: Optional[Callable] = None,
        db_path: Optional[Path] = None,
        system_prompt_path: Optional[Path] = None,
    ):
        self.fahrer = fahrer or Fahrer(db_path=db_path)
        self.sessions = session_store or SessionStore(db_path=db_path)
        self.prompts = prompt_library or PromptLibrary(db_path=db_path)
        self.profile = profile_manager or ProfileManager(db_path=db_path)
        # Handler injizierbar (Tests koennen ein Fake-MotorErgebnis liefern).
        self.handler = handler or MotorBlock().handler()

        if system_prompt_path is None:
            system_prompt_path = Path(__file__).parent.parent / "CLUTCH.md"
        self._system_prompt_path = Path(system_prompt_path)

    # -- Systemprompt ------------------------------------------------------

    def system_prompt(self) -> str:
        try:
            return self._system_prompt_path.read_text(encoding="utf-8")
        except OSError:
            return ""

    # -- Sessions ----------------------------------------------------------

    def neue_session(self, titel: str = "", profil: Optional[str] = None,
                     model_override: Optional[str] = None,
                     system_prompt_on: bool = True) -> ChatSession:
        return self.sessions.neue_session(
            titel=titel, profil=profil, model_override=model_override,
            system_prompt_on=system_prompt_on,
        )

    # -- Prompt-Aufbau -----------------------------------------------------

    def _baue_vollprompt(self, session: ChatSession, user_text: str) -> str:
        teile: list[str] = []

        if session.system_prompt_on:
            sp = self.system_prompt().strip()
            if sp:
                teile.append(sp)

        # Mitgesendete Prompts aus dem toolset-Profil der Session
        if session.profil:
            tp = self.profile.lade(session.profil, "toolset")
            if tp:
                for pid in tp.payload.get("mitgesendete_prompts", []):
                    txt = self.prompts.copy_text(pid)
                    if txt:
                        teile.append(txt)

        teile.append(user_text)
        return "\n\n---\n\n".join(teile)

    # -- Chat --------------------------------------------------------------

    def chat(self, session_id: str, user_text: str, hat_bild: bool = False,
             vertrauenswuerdig: bool = True) -> dict:
        session = self.sessions.session(session_id)
        if session is None:
            session = self.neue_session()
            session_id = session.id

        vollprompt = self._baue_vollprompt(session, user_text)

        # User-Nachricht persistieren
        self.sessions.add_message(session_id, "user", user_text,
                                  attachments=["<bild>"] if hat_bild else None)

        kontext = {"hat_bild": hat_bild, "vertrauenswuerdig": vertrauenswuerdig}
        if session.model_override:
            kontext["model_override"] = session.model_override

        erg = self.fahrer.fahren(vollprompt, handler=self.handler, kontext=kontext)

        out = erg.output
        text = getattr(out, "text", "") if out is not None else ""
        model = getattr(out, "model_id", "") if out is not None else ""
        in_tok = getattr(out, "input_tokens", 0) if out is not None else 0
        out_tok = getattr(out, "output_tokens", 0) if out is not None else 0
        gang = erg.config.gang.name if erg.config else ""

        # Assistant-Nachricht persistieren
        self.sessions.add_message(
            session_id, "assistant", text,
            tokens=in_tok + out_tok, model=model, latenz=erg.latenz_sekunden,
        )

        return {
            "session_id": session_id,
            "text": text,
            "erfolg": erg.erfolg,
            "gang": gang,
            "model": model,
            "tokens": in_tok + out_tok,
            "usage_status": getattr(out, "usage_status", "unknown") if out is not None else "unknown",
            "cost_usd": getattr(out, "cost_usd", None) if out is not None else None,
            "cost_breakdown": getattr(out, "cost_breakdown", None) if out is not None else None,
            "requested_effort": erg.requested_effort,
            "effective_effort": erg.effective_effort,
            "latenz": erg.latenz_sekunden,
            "warnungen": erg.warnungen,
        }

    def verlauf(self, session_id: str) -> list:
        return self.sessions.verlauf(session_id)

    # -- Statistik ---------------------------------------------------------

    def nutzungsstatistik(self) -> dict:
        status = self.fahrer.status()
        return {
            "tankuhr": status.get("tankuhr", {}),
            "tacho": status.get("tacho", {}),
            "bordcomputer": status.get("bordcomputer", {}),
            "sessions": len(self.sessions.sessions(limit=1000)),
        }
