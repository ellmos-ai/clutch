"""Web-App für clutch — M6 Web-Oberfläche (FastAPI, optionale Dependency).

Startet einen FastAPI-Server, der die ChatRuntime über HTTP zugänglich macht.

WICHTIG: FastAPI ist eine optionale Dependency (`pip install clutch[web]`).
Der Import erfolgt lazy in create_app() / serve(), damit das Modul importierbar
bleibt, auch wenn FastAPI nicht installiert ist.

Endpunkte:
    GET  /                          index.html ausliefern
    POST /api/chat                  Chat (neue Session oder bestehende)
    POST /api/upload                Datei-Upload (setzt hat_bild-Flag)
    GET  /api/sessions              Sessions auflisten
    GET  /api/sessions/{id}         Session-Verlauf
    GET  /api/models                Gänge aus dem Getriebe
    GET  /api/profiles              Profile auflisten (optional: ?scope=)
    POST /api/profiles              Profil speichern
    GET  /api/prompts               Prompt-Bibliothek (optional: ?suche=)
    GET  /api/stats                 Nutzungsstatistik
"""

from pathlib import Path
import json
import os
from typing import Any, List, Optional


# ---------------------------------------------------------------------------
# Lazy-Import-Hilfsfunktion
# ---------------------------------------------------------------------------

def _require_fastapi() -> None:
    """Prüft ob FastAPI verfügbar ist — wirft ImportError mit Hinweis falls nicht."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "Die Web-Oberfläche benötigt zusätzliche Pakete.\n"
            "Bitte installieren mit:\n\n"
            "    pip install clutch[web]\n\n"
            f"Fehlendes Paket: {e.name}"
        ) from e


# ---------------------------------------------------------------------------
# App-Fabrik
# ---------------------------------------------------------------------------

def create_app(
    db_path: Optional[Path] = None,
    runtime: Optional[Any] = None,
    allowed_hosts: Optional[List[str]] = None,
    auth_token: Optional[str] = None,
    lang: Optional[str] = None,
) -> Any:
    """Erstellt und gibt die FastAPI-App zurück.

    Parameter
    ---------
    db_path:
        Pfad zur clutch.db. Standard: ~/.clutch/clutch.db.
    runtime:
        Optionale ChatRuntime-Instanz (wird für Tests injiziert).
        Wenn None, wird eine neue Instanz erzeugt.
    allowed_hosts:
        Erlaubte Werte des HTTP-Host-Headers (Schutz gegen DNS-Rebinding).
        Standard: nur Loopback (localhost/127.0.0.1/::1).
    auth_token:
        Wenn gesetzt, erfordert jeder /api/*-Zugriff den Header
        ``Authorization: Bearer <token>`` (oder ``X-Clutch-Token``). Ohne Token
        (Standard) ist die API ungeschützt — nur für reinen Loopback-Betrieb
        gedacht, wo `serve()` das erzwingt.
    """
    _require_fastapi()

    import secrets as _secrets

    from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    from clutch.chat_runtime import ChatRuntime
    from clutch.profile_manager import Profil
    from clutch.getriebe import Getriebe
    from clutch.discovery import ModellDiscovery, konfigurierte_ollama_hosts
    from clutch.i18n import DEFAULT_LANG, LANGS, get_locale, normalisiere_sprache

    # --- Laufzeit-Objekte -------------------------------------------------

    if runtime is None:
        rt = ChatRuntime(db_path=db_path)
    else:
        rt = runtime

    profile_mgr = rt.profile
    prompt_lib = rt.prompts

    import clutch as _clutch_pkg
    _config_dir = Path(_clutch_pkg.__file__).parent / "config"
    getriebe = Getriebe(config_dir=_config_dir)
    modell_discovery = ModellDiscovery()

    # --- FastAPI-App ------------------------------------------------------

    app = FastAPI(
        title="clutch Web-API",
        description="Provider-neutraler LLM-Router — Web-Oberfläche (M6)",
        version="0.5.0",
    )
    env_lang = os.environ.get("CLUTCH_LANG")
    app.state.lang = normalisiere_sprache(lang or env_lang) if (lang or env_lang) else None

    def _sprachcode(request: Request, requested: Optional[str] = None) -> str:
        """Ermittelt die UI-Sprache aus Query, App-Default oder Browser-Header."""
        kandidat = requested or request.query_params.get("lang")
        if not kandidat:
            kandidat = getattr(request.app.state, "lang", None)
        if not kandidat:
            kandidat = request.headers.get("accept-language", "").split(",", 1)[0]
        return normalisiere_sprache(kandidat or DEFAULT_LANG)

    # DNS-Rebinding-Schutz: nur erlaubte Host-Header akzeptieren. Eine boesartige
    # Webseite kann ihren eigenen Hostnamen per DNS-Rebinding auf 127.0.0.1
    # zeigen lassen; der Host-Header traegt dann aber die Angreifer-Domain.
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=allowed_hosts or ["localhost", "127.0.0.1", "::1"],
    )

    # CORS: keine Cookie-Auth -> allow_credentials=False; nur die eigene UI-Origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8760", "http://127.0.0.1:8760"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Token-Gate fuer /api/* (nur aktiv, wenn ein Token gesetzt ist).
    if auth_token:
        @app.middleware("http")
        async def _token_gate(request: Request, call_next):  # noqa: ANN001
            if request.url.path.startswith("/api/"):
                header = request.headers.get("authorization", "")
                vorgelegt = header[7:] if header.startswith("Bearer ") else ""
                vorgelegt = vorgelegt or request.headers.get("x-clutch-token", "")
                if not vorgelegt or not _secrets.compare_digest(vorgelegt, auth_token):
                    return JSONResponse({"detail": "Unauthorized"}, status_code=401)
            return await call_next(request)

    # --- Endpunkte --------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Liefert die Single-Page-Chat-UI."""
        html_pfad = Path(__file__).parent / "web" / "index.html"
        try:
            inhalt = html_pfad.read_text(encoding="utf-8")
        except OSError:
            inhalt = "<html><body><h1>index.html nicht gefunden</h1></body></html>"
        sprachcode = _sprachcode(request)
        # Die Übersetzungen werden zusammen mit der HTML-Seite ausgeliefert;
        # so rendert die UI ohne zusätzlichen Roundtrip bereits korrekt.
        bootstrap = (
            f"<script>window.CLUTCH_LANG = {json.dumps(sprachcode, ensure_ascii=False)};"
            f"window.CLUTCH_I18N = {json.dumps(get_locale(sprachcode), ensure_ascii=False)};"
        )
        if auth_token:
            bootstrap += f"window.CLUTCH_TOKEN = {json.dumps(auth_token)};"
        bootstrap += "</script>\n"
        # Kompatibilitäts-Snippet für bestehende Integratoren, die den
        # ursprünglichen Token-Bootstrap direkt suchen.
        if auth_token:
            bootstrap += f"<script>window.CLUTCH_TOKEN = {auth_token!r};</script>\n"
        if "</head>" in inhalt:
            inhalt = inhalt.replace("</head>", f"{bootstrap}</head>", 1)
        else:
            inhalt = bootstrap + inhalt
        # Die ausgelieferte Locale-Datei ist die Quelle für <html lang>; der
        # statische Fallback im Paket bleibt für direktes Öffnen erhalten.
        inhalt = inhalt.replace('<html lang="de">', f'<html lang="{sprachcode}">', 1)
        return HTMLResponse(content=inhalt)

    @app.get("/api/i18n")
    async def i18n(request: Request, requested_lang: Optional[str] = Query(default=None, alias="lang")) -> dict:
        """Liefert die vollständigen UI-Strings für eine Locale als JSON."""
        sprachcode = _sprachcode(request, requested_lang)
        return {"lang": sprachcode, "strings": get_locale(sprachcode), "supported": list(LANGS)}

    @app.post("/api/chat")
    async def chat(request: Request) -> dict:
        """Führt einen Chat-Schritt aus.

        Nimmt JSON entgegen: {session_id?: str, text: str, hat_bild?: bool,
        system_prompt_on?: bool}.
        Wenn keine session_id übergeben wird, wird automatisch eine neue
        Session angelegt.
        """
        try:
            daten = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Ungültiges JSON")

        text = daten.get("text", "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="'text' darf nicht leer sein")

        try:
            session_id = daten.get("session_id") or None
            hat_bild = bool(daten.get("hat_bild", False))

            # Neue Session anlegen, wenn keine angegeben
            if not session_id:
                sp_an = daten.get("system_prompt_on", True)
                session = rt.neue_session(system_prompt_on=bool(sp_an))
                session_id = session.id

            # Web/API gilt als untrusted: keine agentischen CLI-Motoren mit Auto-Approve.
            ergebnis = rt.chat(
                session_id=session_id,
                user_text=text,
                hat_bild=hat_bild,
                vertrauenswuerdig=False,
            )
            return ergebnis

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    @app.post("/api/upload")
    async def upload(datei: UploadFile = File(...)) -> dict:
        """Nimmt eine hochgeladene Datei entgegen.

        Minimal-Implementierung: speichert nichts dauerhaft, gibt nur das
        hat_bild-Flag und den Dateinamen zurück. Das hat_bild-Flag soll beim
        nächsten /api/chat-Aufruf mitgeschickt werden.
        """
        MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
        try:
            name = datei.filename or "unbekannt"
            # Inhalt lesen mit Groessenlimit (RAM-Schutz gegen riesige Uploads)
            inhalt = await datei.read(MAX_UPLOAD_BYTES + 1)
            if len(inhalt) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Datei zu groß (max 10 MB)")
            return {"hat_bild": True, "name": name}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail="Upload fehlgeschlagen") from e

    @app.get("/api/sessions")
    async def sessions_liste() -> list:
        """Gibt alle Sessions zurück (neueste zuerst)."""
        try:
            sitzungen = rt.sessions.sessions(limit=200)
            return [
                {
                    "id": s.id,
                    "titel": s.titel,
                    "profil": s.profil,
                    "model_override": s.model_override,
                    "system_prompt_on": s.system_prompt_on,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                }
                for s in sitzungen
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    @app.get("/api/sessions/{session_id}")
    async def session_verlauf(session_id: str) -> dict:
        """Gibt eine Session mit ihrem Verlauf zurück."""
        try:
            sitzung = rt.sessions.session(session_id)
            if sitzung is None:
                raise HTTPException(status_code=404, detail="Session nicht gefunden")

            nachrichten = rt.verlauf(session_id)
            return {
                "id": sitzung.id,
                "titel": sitzung.titel,
                "profil": sitzung.profil,
                "model_override": sitzung.model_override,
                "system_prompt_on": sitzung.system_prompt_on,
                "created_at": sitzung.created_at,
                "updated_at": sitzung.updated_at,
                "nachrichten": [
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content,
                        "attachments": m.attachments,
                        "tokens": m.tokens,
                        "model": m.model,
                        "latenz": m.latenz,
                        "created_at": m.created_at,
                    }
                    for m in nachrichten
                ],
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    @app.get("/api/models")
    async def models(discover: bool = Query(default=True)) -> list:
        """Gibt alle Gänge (Modelle) aus dem Getriebe zurück."""
        try:
            if discover:
                try:
                    modell_discovery.entdecke_und_registriere(
                        getriebe,
                        ollama_hosts=konfigurierte_ollama_hosts(),
                        ollama_timeout=1.0,
                    )
                except Exception:
                    # Ein nicht laufender lokaler/remote Ollama darf die
                    # statische Modellliste der Web-UI nicht unbrauchbar machen.
                    pass
            gaenge = getriebe.alle_gaenge()
            return [
                {
                    "name": g.name,
                    "provider": g.provider,
                    "gang": g.gang,
                    "leistung": g.leistung,
                    "kosten_input_1k": g.kosten_input_1k,
                    "kosten_output_1k": g.kosten_output_1k,
                    "staerken": g.staerken,
                    "schwaechen": g.schwaechen,
                    "ist_lokal": g.ist_lokal,
                    "model_id": g.model_id,
                    "endpoint": g.endpoint,
                    "catalog_source": g.catalog_source,
                    "quantization": g.quantization,
                    "efforts": g.efforts,
                    "reasoning_modes": g.reasoning_modes,
                    "pricing": g.pricing.to_dict() if g.pricing else None,
                    "pricing_stale": g.pricing.is_stale() if g.pricing else None,
                }
                for g in gaenge
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    @app.get("/api/profiles")
    async def profiles_liste(scope: Optional[str] = Query(default=None)) -> list:
        """Gibt alle Profile zurück, optional gefiltert nach Scope."""
        try:
            profile = profile_mgr.liste(scope=scope)
            return [
                {
                    "name": p.name,
                    "scope": p.scope,
                    "payload": p.payload,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                }
                for p in profile
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    @app.post("/api/profiles")
    async def profiles_speichern(request: Request) -> dict:
        """Speichert oder aktualisiert ein Profil.

        Nimmt JSON entgegen: {name: str, scope: str, payload?: dict}.
        """
        try:
            daten = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Ungültiges JSON")

        name = daten.get("name", "").strip()
        scope = daten.get("scope", "").strip()
        payload = daten.get("payload", {})

        if not name or not scope:
            raise HTTPException(status_code=422, detail="'name' und 'scope' sind Pflichtfelder")

        try:
            profil = Profil(name=name, scope=scope, payload=payload)
            gespeichert = profile_mgr.speichere(profil)
            return {
                "name": gespeichert.name,
                "scope": gespeichert.scope,
                "payload": gespeichert.payload,
                "updated_at": gespeichert.updated_at,
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    @app.get("/api/prompts")
    async def prompts_liste(suche: Optional[str] = Query(default=None)) -> list:
        """Gibt die Prompt-Bibliothek zurück, optional mit Suchfilter."""
        try:
            items = prompt_lib.liste(suche=suche)
            return [
                {
                    "id": item.id,
                    "typ": item.typ,
                    "name": item.name,
                    "content": item.content,
                    "category": item.category,
                    "tags": item.tags,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                }
                for item in items
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    @app.get("/api/stats")
    async def stats() -> dict:
        """Gibt die Nutzungsstatistik zurück."""
        try:
            return rt.nutzungsstatistik()
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    # --- M6+: Credential- und Config-Verwaltung (spiegelt die CLI) ---------
    # WICHTIG: Key-WERTE werden NIE zurückgegeben — nur Namen + Quelle.

    import os as _os
    from clutch.credentials import CredentialStore as _CredStore
    from clutch import cli as _cli

    @app.get("/api/credentials")
    async def credentials_liste() -> dict:
        """Listet Key-Namen + Quelle (env/store). Niemals Werte."""
        try:
            store = _CredStore()
            store_namen = store.namen()
            env_namen = sorted(k for k in _os.environ if k.endswith("_API_KEY"))
            namen = sorted(set(store_namen) | set(env_namen))
            return {
                "keys": [
                    {
                        "name": n,
                        "quelle": "env" if n in env_namen else "store",
                        "im_store": n in store_namen,
                    }
                    for n in namen
                ],
                "env_erkannt": env_namen,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    @app.post("/api/credentials")
    async def credentials_setzen(request: Request) -> dict:
        """Speichert einen API-Key im lokalen Store. Wert wird nicht zurückgegeben."""
        try:
            daten = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Ungültiges JSON")
        name = (daten.get("name") or "").strip()
        wert = daten.get("value") or ""
        if not name or not wert:
            raise HTTPException(status_code=422, detail="name und value erforderlich")
        try:
            _CredStore().set(name, wert)
            return {"ok": True, "name": name}
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    @app.delete("/api/credentials/{name}")
    async def credentials_entfernen(name: str) -> dict:
        """Entfernt einen Key aus dem lokalen Store."""
        try:
            entfernt = _CredStore().remove(name)
            return {"ok": True, "entfernt": entfernt}
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    @app.get("/api/config")
    async def config_lesen() -> dict:
        """Liest die CLI-Konfiguration (~/.clutch/cli_config.json)."""
        try:
            return _cli._lade_config()
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    @app.post("/api/config")
    async def config_setzen(request: Request) -> dict:
        """Setzt einen Konfigurationswert."""
        try:
            daten = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Ungültiges JSON")
        key = (daten.get("key") or "").strip()
        if not key:
            raise HTTPException(status_code=422, detail="key erforderlich")
        try:
            cfg = _cli._lade_config()
            cfg[key] = daten.get("value")
            _cli._speichere_config(cfg)
            return {"ok": True, "key": key}
        except Exception as e:
            raise HTTPException(status_code=500, detail="Interner Fehler") from e

    return app


# ---------------------------------------------------------------------------
# Server-Einstieg
# ---------------------------------------------------------------------------

def serve(
    host: str = "127.0.0.1",
    port: int = 8760,
    db_path: Optional[Path] = None,
) -> None:
    """Startet den uvicorn-Server mit der clutch-Web-App.

    Wirft ImportError (mit Hinweis auf pip install clutch[web]), wenn
    fastapi oder uvicorn fehlen.
    """
    _require_fastapi()

    import os

    import uvicorn

    import secrets

    loopback_hosts = {"127.0.0.1", "localhost", "::1"}
    ist_loopback = host in loopback_hosts
    token = os.environ.get("CLUTCH_WEB_TOKEN") or None

    # Bei Bind an ein nicht-loopback-Interface (z.B. 0.0.0.0) ist die API im
    # Netzwerk erreichbar. Ohne Token waere der Credential-/Config-CRUD dann
    # ungeschuetzt exponiert -> Token zur Pflicht machen.
    if not ist_loopback and not token:
        raise RuntimeError(
            f"Bind an nicht-loopback-Host '{host}' erfordert ein Auth-Token. "
            "Setze die Umgebungsvariable CLUTCH_WEB_TOKEN=<geheim>, sonst ist "
            "die Web-API (inkl. Credential-Verwaltung) offen im Netzwerk erreichbar."
        )

    # Bei Loopback-Start ohne explizites Env-Token: automatisch sicheres Token generieren.
    if ist_loopback and not token:
        token = secrets.token_urlsafe(32)

    allowed_hosts = ["localhost", "127.0.0.1", "::1"]
    if not ist_loopback:
        allowed_hosts.append(host)

    app = create_app(db_path=db_path, allowed_hosts=allowed_hosts, auth_token=token)
    print(f"clutch Web-Oberfläche startet auf http://{host}:{port}")
    if not ist_loopback:
        print(f"WARNUNG: gebunden an {host} — im Netzwerk erreichbar.")
    if token:
        print("Auth-Token aktiv: /api/* erfordert Token (in UI injiziert).")
    print("Zum Beenden: Ctrl+C")
    uvicorn.run(app, host=host, port=port)
