# Meshtastic_Mass_Text

Kleines Python-Skript fuer Meshtastic, das eine Direktnachricht an alle bekannten Nodes sendet.

## Funktionen

- fragt den Nachrichtentext interaktiv ab
- findet serielle Ports automatisch oder laesst dich einen Port auswaehlen
- verbindet sich mit einem Meshtastic-Geraet ueber USB/COM
- liest bekannte Nodes aus
- ueberspringt standardmaessig den eigenen Node
- ueberspringt standardmaessig Nodes, die als `unmessageable` markiert sind
- zeigt die Empfaengerliste vor dem Versand zur Bestaetigung an

## Voraussetzungen

- Windows mit Python 3.14+
- installierte Python-Pakete:
  - `meshtastic`
  - `pyserial`

## Installation

```powershell
python -m pip install meshtastic pyserial
```

## Start

```powershell
python .\send_to_all_nodes.py
```

## Optionen

```powershell
python .\send_to_all_nodes.py --help
python .\send_to_all_nodes.py --list-ports
python .\send_to_all_nodes.py --port COM7
python .\send_to_all_nodes.py --ack
python .\send_to_all_nodes.py --channel-index 1
python .\send_to_all_nodes.py --include-unmessageable
```

## Hinweis

Das Skript ist fuer kontrollierte Direktnachrichten gedacht. Bitte beachte lokale Funkregeln, Duty-Cycle-Grenzen und den respektvollen Umgang mit anderen Nodes im Mesh.
