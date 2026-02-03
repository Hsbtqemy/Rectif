"""Modèles de données pour la queue et les statuts."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class QueueStatus(str, Enum):
    """Statut d'un élément dans la queue."""

    PENDING = "pending"
    DONE = "done"
    ERROR = "error"


@dataclass
class QueueItem:
    """Élément de la file d'attente des images."""

    path: Path
    status: QueueStatus = QueueStatus.PENDING
    error_message: Optional[str] = None

    @property
    def filename(self) -> str:
        """Nom du fichier sans chemin."""
        return self.path.name

    @property
    def stem(self) -> str:
        """Nom sans extension."""
        return self.path.stem

    @property
    def extension(self) -> str:
        """Extension du fichier."""
        return self.path.suffix.lower()

    def __str__(self) -> str:
        status_str = self.status.value
        if self.error_message:
            return f"{self.filename} [{status_str}: {self.error_message}]"
        return f"{self.filename} [{status_str}]"
