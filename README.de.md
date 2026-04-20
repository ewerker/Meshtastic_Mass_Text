# Meshtastic_Mass_Com

Deutsche Dokumentation. English version: [README.md](C:\Users\richt\Documents\Codex\Meshtastic_tool\README.md)

Kleines Python-Werkzeug fuer umfassende Meshtastic-Kommunikation: Direktnachrichten, Gruppen-Broadcasts, Live-Mitschnitt, Logging, History und getrennte lokale Konfigurationsdateien fuer Senden und Lauschen.

## Funktionen

- Sendet an alle bekannten Nodes oder nur an gefilterte Ziele
- Kann eine vorgefilterte Liste anzeigen und daraus gezielt einzelne Nodes auswaehlen
- Filtert ueber Node-ID, Kurzname oder Langname
- Unterstuetzt Wildcards wie `FR*`
- Erkennt serielle Ports automatisch oder laesst dich interaktiv waehlen
- Wartet optional auf ACK, implizites ACK oder NAK
- Kann bei implizitem ACK oder NAK automatisch erneut senden
- Kann eingehende Pakete live mit Filtern anzeigen
- Kann Sende- und Empfangsdaten in eine lokale JSONL-Datei schreiben
- Kann echte Gruppen-/Broadcast-Nachrichten auf einem gewaehlten Kanal senden
- Kann einen Dry-Run ohne Aussendung ausfuehren
- Kann eine lokale History/Inbox pflegen und spaeter anzeigen
- Speichert Laufzeitwerte in getrennten `.cfg`-Dateien fuer Senden und Lauschen
- Unterstuetzt unbeaufsichtigte Laeufe ohne Rueckfragen
- Kann die Konfigurationsdatei gezielt schuetzen oder bewusst aktualisieren

## Voraussetzungen

- Python 3.14+
- Beliebiges Betriebssystem, auf dem Python und der Meshtastic-Stack verfuegbar sind
- Python-Pakete:
  - `meshtastic`
  - `pyserial`

## Installation

```bash
python -m pip install meshtastic pyserial
```

## Dateien

- Skript: [meshtastic_mass_com.py](C:\Users\richt\Documents\Codex\Meshtastic_tool\meshtastic_mass_com.py)
- Sende-Konfiguration: [meshtastic_mass_com.send.cfg](C:\Users\richt\Documents\Codex\Meshtastic_tool\meshtastic_mass_com.send.cfg)
- Listen-Konfiguration: [meshtastic_mass_com.listen.cfg](C:\Users\richt\Documents\Codex\Meshtastic_tool\meshtastic_mass_com.listen.cfg)
- Standard-History fuer Senden: [meshtastic_mass_com.send.history.jsonl](C:\Users\richt\Documents\Codex\Meshtastic_tool\meshtastic_mass_com.send.history.jsonl)
- Standard-History fuer Lauschen: [meshtastic_mass_com.listen.history.jsonl](C:\Users\richt\Documents\Codex\Meshtastic_tool\meshtastic_mass_com.listen.history.jsonl)
- Englische Dokumentation: [README.md](C:\Users\richt\Documents\Codex\Meshtastic_tool\README.md)

## Erster Start

Wenn noch keine passende Konfigurationsdatei existiert, sollte das Skript einmal mit Parametern gestartet werden, damit eine CFG erzeugt werden kann.

Regeln fuer die CFG-Auswahl:

- Ohne Parameter oder mit `--mode send`, `--mode broadcast`, `--mode history`
  - Es wird die Sende-CFG `meshtastic_mass_com.send.cfg` verwendet
- Mit `--listen` oder `--mode listen`
  - Es wird die Listen-CFG `meshtastic_mass_com.listen.cfg` verwendet

Beispiel:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --ack --delay 1.5 --timeout 60 --target-mode select --filter "FR*" --selection "1,3" --retry-implicit-ack 1 --retry-nak 1 --message "Testnachricht" --unattended --forcecfg
```

Danach reicht oft:

```bash
python ./meshtastic_mass_com.py
```

## Verhalten der Konfigurationsdatei

- Keine aktive CFG + Parameter uebergeben:
  - Aus den Parametern kann die aktive CFG erzeugt werden.
- Vorhandene aktive CFG + Parameter uebergeben:
  - Die Parameter gelten fuer diesen Lauf.
  - Ob die aktive CFG aktualisiert wird, haengt von `--forcecfg` / `--protectcfg` ab.
- Vorhandene aktive CFG + keine Parameter:
  - Das Skript verwendet die Werte aus der aktiven CFG.
- Keine aktive CFG + keine Parameter:
  - Das Skript zeigt ein Beispiel fuer einen gueltigen Erstaufruf.

## Steuerung der CFG

Diese Schalter machen das Verhalten eindeutig:

- `--forcecfg`
  - Erzeugt oder aktualisiert die aktive CFG immer, wenn Parameter uebergeben werden.
- `--protectcfg`
  - Veraendert die aktive CFG in diesem Lauf niemals, auch wenn Parameter uebergeben werden.
- `--clear`
  - Loescht die aktive CFG und beendet sich danach.

Beispiele:

- Sende-CFG loeschen:

```bash
python ./meshtastic_mass_com.py --clear
```

- Listen-CFG loeschen:

```bash
python ./meshtastic_mass_com.py --listen --clear
```

Sendeeinstellungen in der Sende-CFG speichern:

```bash
python ./meshtastic_mass_com.py --port <PORT> --channel-index 1 --message "Hallo" --forcecfg
```

Listen-Einstellungen in der Listen-CFG speichern:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --listen-filter "FR*" --text-only --forcecfg
```

## Kommandozeilen-Parameter

Die wichtigsten Parameter sind hier nach Zweck gruppiert.

### Workflow-Auswahl

- `--mode send`
  - Sendet Direktnachrichten an die ausgewaehlten Empfaenger.
- `--mode listen` oder `--listen`
  - Haelt die Verbindung offen und zeigt passende eingehende Pakete live an.
- `--mode broadcast` oder `--broadcast`
  - Sendet genau eine Nachricht in einen Kanalchat statt einer DM-Schleife.
- `--mode history` oder `--history`
  - Zeigt lokal gespeicherte History-Eintraege ohne Verbindung zum Geraet.

### Geraet und Kanal

- `--port <PORT>`
  - Waehlt den seriellen Port explizit. Ohne Angabe wird automatisch gesucht oder nachgefragt.
- `--channel-index 0`
  - Waehlt den Kanal fuer Direktnachrichten oder Broadcasts.
- `--list-ports`
  - Zeigt verfuegbare serielle Ports und beendet sich.

### Empfaengerauswahl fuer den Sendemodus

- `--target-mode all`
  - Sendet an alle bekannten Nodes.
- `--target-mode filter --filter "FR*"`
  - Sendet nur an Nodes, die auf den Filter passen.
- `--target-mode select --filter "FR*" --selection "1,3-5"`
  - Filtert eine Liste vor und sendet dann nur an die ausgewaehlten Eintraege.
- `--filter`
  - Vergleicht Node-ID, Kurzname und Langname. Wildcards wie `FR*` oder `*mobil*` werden unterstuetzt.
- `--selection`
  - Kommagetrennte Listenindizes oder Bereiche aus der angezeigten Kandidatenliste.

### Nachricht und Zustellverhalten

- `--message "Hallo"`
  - Setzt den Nachrichtentext fuer Sende- oder Broadcast-Modus.
- `--ack`
  - Wartet bei Direktnachrichten auf ACK, implizites ACK oder NAK.
- `--retry-implicit-ack 1`
  - Wiederholt bei "gesendet, aber nicht explizit bestaetigt".
- `--retry-nak 1`
  - Wiederholt nach einem NAK.
- `--delay 1.5`
  - Pause zwischen Empfaengern und Retries.
- `--timeout 60`
  - Timeout fuer Verbindung und ACK-Wartezeit.
- `--final-wait 5`
  - Haelt die Verbindung nach der letzten Uebertragung noch etwas offen, wenn `--ack` nicht genutzt wird.
- `--dry-run`
  - Zeigt Empfaenger, Nachricht und Kanal nur als Vorschau, ohne zu senden.

### Filter im Listen-Modus

- `--listen-filter "FR*"`
  - Zeigt nur Pakete von passenden Absendern.
- `--listen-channel-index 1`
  - Zeigt nur Pakete eines Kanals.
- `--dm-only`
  - Zeigt nur Direktnachrichten.
- `--group-only`
  - Zeigt nur Gruppen- oder Broadcast-Verkehr.
- `--text-only`
  - Zeigt nur Textpakete und blendet Telemetrie, Nodeinfo und andere Typen aus.

### Dateien und lokale History

- `--log-file ./meshtastic_log.jsonl`
  - Schreibt JSONL-Aktivitaetsdaten fuer Senden und Lauschen.
- `--history-file ./meshtastic_history.jsonl`
  - Ueberschreibt die Standarddatei fuer lokale Inbox/History.
  - Standard ohne Ueberschreibung:
    - Senden/Broadcast/History -> `meshtastic_mass_com.send.history.jsonl`
    - Lauschen -> `meshtastic_mass_com.listen.history.jsonl`
- `--history-filter "Naunhof"`
  - Filtert die Anzeige im History-Modus.
- `--history-limit 50`
  - Begrenzt die Anzahl angezeigter History-Eintraege.

### Umgang mit der CFG

- `--forcecfg`
  - Schreibt die aktuellen CLI-Werte immer in die aktive CFG.
- `--protectcfg`
  - Veraendert die aktive CFG in diesem Lauf niemals.
- `--clear`
  - Loescht die aktive CFG der gewaehlten CFG-Familie und beendet sich.
- `--unattended`
  - Ueberspringt Rueckfragen. Alle benoetigten Werte muessen dann aus CLI oder CFG kommen.

## Zielauswahl

Das Skript kann:

- an alle bekannten Nodes senden
- nur an gefilterte Nodes senden
- aus einer nummerierten Liste einzelne Nodes auswaehlen, auf Wunsch nach Vorfilterung

Interaktiv:

```bash
python ./meshtastic_mass_com.py
```

Dann fragt das Skript:

- `1` fuer alle bekannten Nodes
- `2` fuer gefiltertes Senden
- `3` fuer manuelle Listenauswahl

Direkte Beispiele per Parameter:

```bash
python ./meshtastic_mass_com.py --target-mode all
python ./meshtastic_mass_com.py --target-mode filter --filter "FR*"
python ./meshtastic_mass_com.py --target-mode filter --filter "!55d8c9dc"
python ./meshtastic_mass_com.py --target-mode filter --filter "Rico"
python ./meshtastic_mass_com.py --target-mode select --filter "FR*"
python ./meshtastic_mass_com.py --target-mode select --filter "FR*" --selection "1,3-4" --unattended
```

Filterregeln:

- Mit Wildcards wie `FR*` oder `*mobil*` wird als Muster gesucht.
- Ohne Wildcards sind Teiltreffer erlaubt.
- Geprueft werden Node-ID, Kurzname und Langname.

## Nachricht und Unattended-Modus

Du kannst eine Standardnachricht in der CFG speichern:

```bash
python ./meshtastic_mass_com.py --message "Hallo zusammen" --forcecfg
```

Start ohne Rueckfragen:

```bash
python ./meshtastic_mass_com.py --unattended
```

Typischer unattended-Aufruf:

```bash
python ./meshtastic_mass_com.py --port <PORT> --channel-index 1 --ack --target-mode filter --filter "FR*" --message "Hallo zusammen" --unattended --forcecfg
```

Im unattended-Modus gilt:

- keine Rueckfrage nach der Nachricht
- keine Rueckfrage zur Zielauswahl
- keine Rueckfrage vor dem Versand
- benoetigte Werte muessen aus Parametern oder der CFG kommen

## ACK-Auswertung

Mit `--ack` wartet das Skript pro Nachricht auf eine Rueckmeldung.

Moegliche Ergebnisse:

- `Received an ACK.`
  - Die Zustellung wurde bestaetigt.
- `Sent, but not confirmed (implicit ACK only).`
  - Das Paket wurde gesendet, aber nicht explizit bestaetigt.
- `Received a NAK, error reason: ...`
  - Die Zustellung wurde negativ beantwortet.
- `Error ... No ACK/NAK ...`
  - Timeout ohne Rueckmeldung.

Retry-Steuerung:

- `--retry-implicit-ack 1`
  - Sendet nach einem impliziten ACK einmal erneut.
- `--retry-nak 1`
  - Sendet nach einem NAK einmal erneut.

Beispiel:

```bash
python ./meshtastic_mass_com.py --port <PORT> --channel-index 1 --ack --delay 1.5 --timeout 60 --retry-implicit-ack 1 --retry-nak 1
```

## Listen-Modus

Das Skript kann auch verbunden bleiben und passende eingehende Pakete live anzeigen.

Beispiele:

```bash
python ./meshtastic_mass_com.py --mode listen
python ./meshtastic_mass_com.py --listen --listen-filter "FR*"
python ./meshtastic_mass_com.py --listen --listen-channel-index 1
python ./meshtastic_mass_com.py --listen --dm-only
python ./meshtastic_mass_com.py --listen --group-only --text-only
```

Filter im Listen-Modus:

- `--listen-filter`
  - Filtert ueber Absender-Node-ID, Kurzname oder Langname
- `--listen-channel-index`
  - Zeigt nur Pakete eines bestimmten Kanals
- `--dm-only`
  - Zeigt nur Direktnachrichten
- `--group-only`
  - Zeigt nur Gruppen-/Broadcast-Verkehr
- `--text-only`
  - Zeigt nur Textpakete

Beenden mit `Ctrl+C`.

## Logging

Mit `--log-file` schreibt das Skript JSONL-Eintraege fuer Sendeversuche und empfangene Pakete.

Beispiele:

```bash
python ./meshtastic_mass_com.py --mode send --log-file ./meshtastic_log.jsonl
python ./meshtastic_mass_com.py --listen --log-file ./meshtastic_log.jsonl
```

## Broadcast-Modus

Im Broadcast-Modus wird genau eine Nachricht auf den gewaehlten Kanal gesendet, statt eine DM-Schleife zu verwenden.

Beispiele:

```bash
python ./meshtastic_mass_com.py --mode broadcast --port <PORT> --channel-index 0 --message "Hallo private Gruppe"
python ./meshtastic_mass_com.py --broadcast --port <PORT> --channel-index 1 --message "Hallo LongFast"
```

Hinweise:

- Der Broadcast-Modus ignoriert `--ack`
- Er sendet genau einmal auf dem gewaehlten Kanal
- Das ist meist der richtige Modus, wenn die Nachricht im Gruppen-/Kanalchat erscheinen soll

## Dry-Run

Mit `--dry-run` kann geprueft werden, was gesendet wuerde, ohne wirklich Funkpakete abzusetzen.

Beispiele:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --target-mode select --filter "FR*" --selection "1,3" --message "Nur Vorschau" --dry-run
python ./meshtastic_mass_com.py --mode broadcast --port <PORT> --channel-index 1 --message "Vorschau Gruppenpost" --dry-run
```

## History

Das Skript fuehrt lokale History-Dateien fuer empfangene Pakete und gesendete Nachrichten. Diese koennen spaeter auch ohne Geraet angezeigt werden.

Standard-Trennung:

- Senden / Broadcast / History-Modus
  - `meshtastic_mass_com.send.history.jsonl`
- Listen-Modus
  - `meshtastic_mass_com.listen.history.jsonl`

Beispiele:

```bash
python ./meshtastic_mass_com.py --mode history
python ./meshtastic_mass_com.py --history --history-limit 50
python ./meshtastic_mass_com.py --history --history-filter "Naunhof"
python ./meshtastic_mass_com.py --history --history-file ./logs/history.jsonl
```

## Beispiel-Workflows

### Schnelle Alltagsnutzung

Skript interaktiv starten und sich durchfuehren lassen:

```bash
python ./meshtastic_mass_com.py
```

Direktnachricht an alle bekannten Nodes mit dem gewaehlten seriellen Port:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --target-mode all --message "Hallo an alle"
```

Auf `<PORT>` lauschen und nur Textverkehr anzeigen:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --text-only
```

Einmal in den Kanalchat posten statt Direktnachrichten zu verschicken:

```bash
python ./meshtastic_mass_com.py --mode broadcast --port <PORT> --channel-index 1 --message "Hallo Gruppe"
```

### Gefilterte Sende-Workflows

Nur an Nodes senden, deren Rufname auf ein Muster passt:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode filter --filter "FR*" --message "Netztest" --ack
```

Nur an eine exakte Node-ID senden:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode filter --filter "!55d8c9dc" --message "Privater Test" --ack
```

Liste vorfiltern und dann einzelne Empfaenger manuell auswaehlen:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode select --filter "FR*"
```

Dieselbe Auswahl unattended mit gespeicherten Indexen ausfuehren:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode select --filter "FR*" --selection "1,3-5" --message "Geplanter Ping" --unattended
```

### Zuverlaessige Zustellung

ACK anfordern und bei implizitem ACK oder NAK jeweils einmal erneut senden:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode filter --filter "FR*" --message "Bitte bestaetigen" --ack --retry-implicit-ack 1 --retry-nak 1 --delay 1.5 --timeout 60
```

Kanal `0` fuer eine kleine private Gruppe nutzen, ohne die gespeicherte CFG zu veraendern:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 0 --target-mode select --selection "1-3" --message "Privater Check-in" --ack --protectcfg
```

### Listen-Workflows

Nur LongFast-Verkehr auf Kanal `1` anzeigen:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --listen-channel-index 1
```

Nur Direktnachrichten von Nodes passend auf `FR*` anzeigen:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --listen-filter "FR*" --dm-only --text-only
```

Nur Gruppenverkehr anzeigen und Nicht-Text-Pakete sichtbar lassen:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --group-only
```

### Logging-Workflows

Versand mit ACK-Auswertung und JSONL-Logdatei:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode filter --filter "FR*" --message "Mit Log" --ack --retry-implicit-ack 1 --retry-nak 1 --log-file ./logs/send_log.jsonl
```

Dauerhaft lauschen und passende Pakete in ein gemeinsames Log schreiben:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --text-only --log-file ./logs/listen_log.jsonl
```

Beim Lauschen die Standard-History-Datei gezielt ueberschreiben:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --text-only --history-file ./logs/history.jsonl
```

### CFG-zentrierte Workflows

Ein wiederverwendbares unattended-Profil erzeugen oder aktualisieren:

```bash
python ./meshtastic_mass_com.py --mode send --port <PORT> --channel-index 1 --target-mode select --filter "FR*" --selection "1,2" --message "Routine-Nachricht" --ack --retry-implicit-ack 1 --retry-nak 1 --log-file ./logs/routine.jsonl --unattended --forcecfg
```

Spaeter nur noch mit der gespeicherten CFG starten:

```bash
python ./meshtastic_mass_com.py
```

Temporar im Listen-Modus mit anderen Werten arbeiten, ohne die CFG zu veraendern:

```bash
python ./meshtastic_mass_com.py --listen --port <PORT> --listen-filter "FR*" --dm-only --text-only --protectcfg
```

Einen Broadcast nur testen, ohne zu senden und ohne die CFG zu veraendern:

```bash
python ./meshtastic_mass_com.py --mode broadcast --port <PORT> --channel-index 0 --message "Test Gruppe" --dry-run --protectcfg
```

## Hilfe

Die eingebaute CLI-Hilfe zeigt immer die aktuelle, vollstaendige Parameterliste:

```bash
python ./meshtastic_mass_com.py --help
```

## Hinweise

- Dieses Werkzeug ist fuer kontrollierte Direktnachrichten gedacht.
- Bitte beachte lokale Funkregeln, Duty-Cycle-Grenzen und andere Teilnehmer im Mesh.





