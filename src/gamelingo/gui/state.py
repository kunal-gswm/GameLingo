from pathlib import Path
from typing import Optional

from gamelingo.storage.database import Database

class AppState:
    def __init__(self):
        self.workspace_path: Optional[Path] = None
        self.db: Optional[Database] = None
        self.game_path: Optional[Path] = None

    def open_workspace(self, path: Path):
        self.workspace_path = path
        if not path.exists():
            path.mkdir(parents=True)
            
        db_path = path / "gamelingo.db"
        self.db = Database(db_path)
        self.db.migrate()
        self._load_project_config()

    def _load_project_config(self):
        if not self.db:
            return
            
        conn = self.db.connect()
        cur = conn.execute("SELECT install_path FROM projects WHERE id = 'default'")
        row = cur.fetchone()
        if row and row['install_path']:
            p = Path(row['install_path'])
            if p.exists():
                self.game_path = p
