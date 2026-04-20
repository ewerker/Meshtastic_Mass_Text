# Meshtastic_Mass_Text

Kleines Python-Skript fuer Meshtastic, das Direktnachrichten an bekannte Nodes sendet.

## Funktionen

- fragt den Nachrichtentext interaktiv ab oder nutzt eine gespeicherte Standardnachricht
- findet serielle Ports automatisch oder laesst dich einen Port auswaehlen
- verbindet sich mit einem Meshtastic-Geraet ueber USB/COM
- liest bekannte Nodes aus
- kann an alle bekannten Nodes oder nur an gefilterte Ziele senden
- unterstuetzt Filter ueber Node-ID, Kurzname und Langname, z. B. `!55d8c9dc`, `Rico` oder `FR*`
- ueberspringt standardmaessig den eigenen Node
- ueberspringt standardmaessig Nodes, die als `unmessageable` markiert sind
- zeigt die Empfaengerliste vor dem Versand zur Bestaetigung an
- kann auf ACK, implizites ACK oder NAK warten
- speichert Laufzeitparameter in einer CFG-Datei im selben Ordner
- kann unbeaufsichtigt ohne Rueckfragen laufen

## Voraussetzungen

- Windows mit Python 3.14+
- installierte Python-Pakete:
  - `meshtastic`
  - `pyserial`

## Installation

```powershell
python -m pip install meshtastic pyserial
```

## Dateien

- Skript: [send_to_all_nodes.py](C:\Users\richt\Documents\Codex\2026-04-19-installiere-mir-phyton\send_to_all_nodes.py)
- Konfiguration: [send_to_all_nodes.cfg](C:\Users\richt\Documents\Codex\2026-04-19-installiere-mir-phyton\send_to_all_nodes.cfg)

## Erster Start

Wenn noch keine CFG existiert, sollte das Skript beim ersten Mal mit Parametern gestartet werden. Dabei wird die CFG automatisch erzeugt.

Beispiel:

```powershell
python .\send_to_all_nodes.py --port COM7 --channel-index 1 --ack --delay 1.5 --timeout 60 --target-mode filter --filter "FR*" --message "Testnachricht" --unattended
```

Danach reicht fuer spaetere Starts oft einfach:

```powershell
python .\send_to_all_nodes.py
```

Dann werden die Werte aus der CFG verwendet.

## CFG-Verhalten

- Existiert keine CFG und das Skript wird mit Parametern gestartet, wird die CFG erzeugt.
- Existiert die CFG bereits und das Skript wird mit Parametern gestartet, werden diese Werte in die CFG uebernommen.
- Wird das Skript ohne Parameter gestartet, gelten die Werte aus der CFG.
- Gibt es weder CFG noch Parameter, zeigt das Skript ein Beispiel fuer einen gueltigen Erstaufruf.
- Mit `--clear` wird die CFG geloescht.

CFG loeschen:

```powershell
python .\send_to_all_nodes.py --clear
```

## Zielauswahl

Das Skript kann an alle bekannten Nodes oder nur an gefilterte Ziele senden.

Interaktiv:

```powershell
python .\send_to_all_nodes.py
```

Dann fragt das Skript:

- `1` fuer alle bekannten Nodes
- `2` fuer gefilterte Ziele

Direkt per Parameter:

```powershell
python .\send_to_all_nodes.py --help
python .\send_to_all_nodes.py --list-ports
python .\send_to_all_nodes.py --port COM7
python .\send_to_all_nodes.py --channel-index 1
python .\send_to_all_nodes.py --target-mode all
python .\send_to_all_nodes.py --target-mode filter --filter "FR*"
python .\send_to_all_nodes.py --target-mode filter --filter "!55d8c9dc"
python .\send_to_all_nodes.py --target-mode filter --filter "Rico"
```

Filterregeln:

- Mit Wildcards wie `FR*` oder `*mobil*` wird ueber Muster gesucht.
- Ohne Wildcards reicht auch ein Teilstring, z. B. `Rico`.
- Geprueft werden Node-ID, Kurzname und Langname.

## Nachricht und unattended-Modus

Eine Standardnachricht kann per Parameter gesetzt und in die CFG geschrieben werden:

```powershell
python .\send_to_all_nodes.py --message "Hallo zusammen"
```

Unbeaufsichtigter Start ohne Rueckfragen:

```powershell
python .\send_to_all_nodes.py --unattended
```

Typischer unattended-Aufruf:

```powershell
python .\send_to_all_nodes.py --port COM7 --channel-index 1 --ack --target-mode filter --filter "FR*" --message "Hallo zusammen" --unattended
```

Im unattended-Modus gilt:

- keine Rueckfrage zur Nachricht
- keine Rueckfrage zur Zielauswahl
- keine Rueckfrage vor dem Versand
- fehlende Pflichtwerte muessen aus Parametern oder der CFG kommen

## ACK-Auswertung

Mit `--ack` wartet das Skript pro Nachricht auf eine Rueckmeldung.

Moegliche Ausgaben:

- `Received an ACK.`: Nachricht wurde bestaetigt.
- `Versendet, aber nicht bestaetigt (nur implizites ACK).`: Nachricht wurde angestossen, aber nicht eindeutig bestaetigt.
- `Received a NAK, error reason: ...`: Nachricht wurde negativ beantwortet.
- `Fehler bei ... Kein ACK/NAK ...`: Timeout ohne Rueckmeldung.

Beispiel:

```powershell
python .\send_to_all_nodes.py --port COM7 --channel-index 1 --ack --delay 1.5 --timeout 60
```

## Wichtige Optionen

```powershell
python .\send_to_all_nodes.py --ack
python .\send_to_all_nodes.py --no-ack
python .\send_to_all_nodes.py --include-unmessageable
python .\send_to_all_nodes.py --no-include-unmessageable
python .\send_to_all_nodes.py --message "Hallo"
python .\send_to_all_nodes.py --unattended
python .\send_to_all_nodes.py --no-unattended
python .\send_to_all_nodes.py --clear
```

## Hinweis

Das Skript ist fuer kontrollierte Direktnachrichten gedacht. Bitte beachte lokale Funkregeln, Duty-Cycle-Grenzen und den respektvollen Umgang mit anderen Nodes im Mesh.
