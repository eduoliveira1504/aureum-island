"""Páginas do notch aberto."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageInfo:
    id: str  # mesmo id salvo em settings.json (last_page)
    label: str  # nome acessível e tooltip, pt-BR
    icon: str  # arquivo em assets/icons


PAGES: tuple[PageInfo, ...] = (
    PageInfo("music", "Música", "music"),
    PageInfo("focus", "Foco", "focus"),
    PageInfo("water", "Água", "water"),
    PageInfo("tasks", "Tarefas", "tasks"),
    PageInfo("calendar", "Calendário", "calendar"),
)
