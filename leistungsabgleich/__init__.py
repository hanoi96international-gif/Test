"""Leistungsabgleich: Datenaustausch zwischen Jobcenter (SGB II) und Wohngeldstelle (WoGG).

Beide Behörden melden ihre Fälle (Antrag gestellt, bewilligt, abgelehnt, eingestellt) an ein
gemeinsames Register. Personen werden dort nur als Pseudonym gespeichert. Jede Behörde kann
für eine eigene Person sehen, ob bei der anderen Stelle ein Antrag läuft oder Leistungen
bewilligt sind, und Erstattungsansprüche (§§ 102 ff. SGB X) digital anmelden.
"""

from .register import Register, pseudonym

__all__ = ["Register", "pseudonym"]
