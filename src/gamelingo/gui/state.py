import hashlib
import re
from pathlib import Path
from typing import Optional

from gamelingo.storage.database import Database


class AppState:
    def __init__(self):
        self.workspace_path: Optional[Path] = None
        self.db: Optional[Database] = None
        self.game_path: Optional[Path] = None
        self.active_project_id: Optional[str] = None

    def open_workspace(self, path: Path):
        self.workspace_path = path
        if not path.exists():
            path.mkdir(parents=True)

        db_path = path / "gamelingo.db"
        self.db = Database(db_path)
        self.db.migrate()
        self._load_project_config()

    def set_game_path(self, path: Optional[Path], project_id: Optional[str] = None):
        self.game_path = path
        self.active_project_id = project_id
        if path and not project_id and self.db:
            self.active_project_id = self.get_project_id()

    def get_project_id(self) -> Optional[str]:
        if self.active_project_id:
            return self.active_project_id
        if not self.db:
            return None
        if not self.game_path:
            conn = self.db.connect()
            cur = conn.execute("SELECT id FROM projects WHERE id = 'default'")
            if cur.fetchone():
                return "default"
            return None

        conn = self.db.connect()
        resolved_str = str(self.game_path.resolve())

        # 1. Match install_path in projects table
        cur = conn.execute(
            "SELECT id FROM projects WHERE install_path = ?", (resolved_str,)
        )
        row = cur.fetchone()
        if row and row["id"]:
            return row["id"]

        cur = conn.execute(
            "SELECT id FROM projects WHERE install_path = ?", (str(self.game_path),)
        )
        row = cur.fetchone()
        if row and row["id"]:
            return row["id"]

        # 2. Check 'default' project
        cur = conn.execute("SELECT id, install_path FROM projects WHERE id = 'default'")
        row = cur.fetchone()
        if row:
            p_inst = row["install_path"]
            if not p_inst or p_inst in (resolved_str, str(self.game_path)):
                return "default"
            # Game path differs from default's install_path -> compute deterministic isolated project ID
            slug = re.sub(r"[^a-zA-Z0-9_]", "_", self.game_path.name).lower() or "proj"
            path_hash = hashlib.sha256(resolved_str.encode("utf-8")).hexdigest()[:8]
            return f"proj_{slug}_{path_hash}"

        return "default"

    def _load_project_config(self):
        if not self.db:
            return

        conn = self.db.connect()
        cur = conn.execute("SELECT install_path FROM projects WHERE id = 'default'")
        row = cur.fetchone()
        if row and row["install_path"]:
            p = Path(row["install_path"])
            if p.exists():
                self.game_path = p
                self.active_project_id = "default"
