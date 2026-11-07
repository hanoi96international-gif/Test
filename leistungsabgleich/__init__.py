"""Leistungsabgleich: Datenaustausch zwischen Jobcenter (SGB II) und Wohngeldstelle (WoGG).

Beide Behörden melden ihre Fälle an ein gemeinsames Register. Personen stehen dort nur als
Pseudonym. Überschneiden sich Leistungen, werden Erstattungsansprüche (§§ 102 ff. SGB X)
automatisch angemeldet und beziffert; die Sachbearbeitung bekommt nur noch die nötigen Aufgaben.
"""

__version__ = "0.9.0b1"

from .register import Register, pseudonym  # noqa: E402

__all__ = ["Register", "pseudonym", "__version__"]
