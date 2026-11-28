# Probe fürs Aktivierungswort „Elektra“

Stand 22.11.2026. Festlegungen stehen in [#111](https://github.com/dragondiver/kuechen-display/issues/111).

> **Stand 28.11.2026:** Die Probe mit openWakeWord ist abgeschlossen. Das eigene Modell erkennt
> Florians „Elektra“ nicht (#111, 25. und 27.11.). Welcher Erkenner es wird, ist offen; verglichen
> wurden danach Vosk und Hark. Gültig bleiben `rufe` und `abend` zum Aufnehmen am XVF3800. `zaehlen`
> und das Training im Colab gelten nur für openWakeWord und stehen hier als Beleg.

Das Küchen-Display soll auf „Elektra“ hören. Bevor ein Erkenner in den Küchen-Dienst kommt, zeigt
diese Probe, ob [openWakeWord](https://github.com/dscripka/openWakeWord) das Wort gut genug trifft.
Am Dienst ändert die Probe nichts.

Festlegung vom 22.11.2026: Zuerst gibt es nur eine kleine Probe im Studio, wo der Testaufbau steht,
mit ein paar Rufen (Schritt 3). Sie zeigt, ob das Modell Florians „Elektra“ überhaupt erkennt und ob
openWakeWord auf dem Pi läuft. Die Durchgänge in der Küche und der Abend ohne Ruf stehen unter
„Später“ und sind vorerst nicht geplant.

Ein Werkzeug macht alles: `pi/werkzeuge/weckwort_probe.py`.

| Befehl | macht | läuft auf |
|---|---|---|
| `rufe ORDNER` | nimmt einzelne Rufe auf, jeden nach einem Ton | Pi |
| `abend ORDNER` | nimmt den Raum ohne Ruf auf, in Stücken von 10 Minuten (vorerst nicht gebraucht) | Pi |
| `zaehlen MODELL` | lässt das Modell über die Aufnahmen laufen und zählt | Pi oder Mac |

Aufgenommen wird wie im Dienst: Kanal 0 des XVF3800, 16 kHz, mono.

## Was man wissen muss

- Während einer Aufnahme ist der Küchen-Dienst aus. Er hält das Mikrofon fest, zwei Programme
  können es nicht gleichzeitig lesen. Das Werkzeug hält ihn an und startet ihn danach wieder, auch
  nach Strg-C. Solange bleibt die Anzeige stehen und Elektra hört nicht. Für einen Durchgang Rufe
  sind das ein bis zwei Minuten.
- Das gilt nur für diese Aufnahmen. Mit dem Training hat es nichts zu tun, das läuft im Colab mit
  künstlichen Stimmen. Ist das Aktivierungswort später eingebaut, hört der Dienst selbst mit.
- Die Aufnahmen bleiben auf dem Pi und dem Mac. Sie kommen nicht ins Git.
- openWakeWord ist für Englisch gebaut. Die Trainingsstimmen sprechen „Elektra“ englisch aus. Ob das
  für die deutsche Aussprache reicht, ist die Frage dieser Probe.

## 1. Modell trainieren

Im Browser, mit Florians Google-Konto. Das README von openWakeWord verlinkt unter „Training New
Models“ ein Colab-Notebook und nennt dafür weniger als eine Stunde.

1. Notebook öffnen:
   <https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb?usp=sharing>
2. Als Wort `elektra` eintragen und die Hörprobe abspielen. Klingt sie falsch, die Schreibweise
   ändern, bis sie dem deutschen „Elektra“ nahekommt (zum Beispiel `electra`).
3. Training laufen lassen und am Ende die Datei mit der Endung `.onnx` herunterladen. Die
   `.tflite`-Datei wird nicht gebraucht.
4. Die Datei als `~/weckwort-probe/elektra.onnx` auf dem Mac ablegen.

Die Bedienung des Notebooks habe ich nicht selbst durchgespielt, die Schritte stammen aus dem README.

## 2. Einrichten

### Mac

```bash
mkdir -p ~/weckwort-probe && cd ~/weckwort-probe
```

```bash
uv venv --python 3.13 venv
```

```bash
uv pip install --python venv/bin/python --no-deps openwakeword==0.6.0
```

```bash
uv pip install --python venv/bin/python onnxruntime numpy scipy scikit-learn tqdm requests
```

```bash
venv/bin/python -c "import openwakeword.utils as u; u.download_models(['hey_jarvis'])"
```

Der letzte Befehl holt die zwei Grundmodelle von openWakeWord (Melspektrogramm und Embedding), ohne
die kein Wortmodell läuft, und dazu das Beispielmodell „hey jarvis“.

### Pi

Das Werkzeug kopieren. Das geht ohne `pi/push.sh`, der Dienst startet dabei nicht neu:

```bash
scp ~/Development/kuechen-display/pi/werkzeuge/weckwort_probe.py kuechen-display.local:kuechen-display/werkzeuge/
```

Aufnehmen braucht auf dem Pi nichts weiter. Nur wenn auch dort gezählt werden soll (Schritt 4,
für die Last), kommt openWakeWord in eine eigene Umgebung neben `~/kuechen-venv`:

```bash
ssh kuechen-display.local 'python3 -m venv ~/weckwort-venv && ~/weckwort-venv/bin/pip install -q --no-deps openwakeword==0.6.0 && ~/weckwort-venv/bin/pip install -q onnxruntime numpy scipy scikit-learn tqdm requests'
```

```bash
ssh kuechen-display.local '~/weckwort-venv/bin/python -c "import openwakeword.utils as u; u.download_models([\"hey_jarvis\"])"'
```

`--no-deps` ist Absicht: openWakeWord verlangt unter Linux `tflite-runtime`, und davon gibt es kein
Rad für Python 3.13. Mit `onnxruntime` und der `.onnx`-Datei wird es nicht gebraucht.

## 3. Ein paar Rufe im Studio aufnehmen

Auf dem Pi, in einer ssh-Sitzung. Vor jedem Ruf kommt ein kurzer Ton aus dem Lautsprecher, danach
einmal „Elektra“ sagen, in normaler Lautstärke. Zehn Rufe von je 4 Sekunden dauern etwa eine Minute.

Einmal aus der Nähe, etwa einen Meter vor dem Aufbau:

```bash
ssh -t kuechen-display.local 'python3 kuechen-display/werkzeuge/weckwort_probe.py rufe weckwort-probe/studio-nah --anzahl 10'
```

Einmal von weiter weg, etwa drei Meter:

```bash
ssh -t kuechen-display.local 'python3 kuechen-display/werkzeuge/weckwort_probe.py rufe weckwort-probe/studio-fern --anzahl 10'
```

Nach jedem Ruf steht die Spitze in dB in der Zeile. Werte unter −50 dB heißen, dass kaum Ton
ankam; das Werkzeug warnt am Ende. Kommt kein Ton aus dem Lautsprecher, meldet es das und macht
ohne Ton weiter, dann zählt die Zeile „Ruf 3/10 …“ als Zeichen.

Ohne `--anzahl` sind es 20 Rufe. Andere Länge: `--sekunden 3`.

Bricht die ssh-Sitzung mitten in einem Durchgang ab oder wird das Werkzeug mit `kill` beendet,
bleibt der Dienst aus, bis er von Hand gestartet wird. Nach Strg-C oder einem Fehler startet das Werkzeug ihn selbst wieder:

```bash
ssh kuechen-display.local 'sudo systemctl start kuechen-dienst'
```

## 4. Zählen

Aufnahmen auf den Mac holen:

```bash
rsync -a kuechen-display.local:weckwort-probe/ ~/weckwort-probe/
```

Zählen:

```bash
cd ~/weckwort-probe && venv/bin/python ~/Development/kuechen-display/pi/werkzeuge/weckwort_probe.py zaehlen elektra.onnx --rufe studio-nah studio-fern
```

Die Ausgabe sieht so aus (Zahlen erfunden):

```text
Rufe           0,3    0,4    0,5    0,6    0,7
studio-nah   10/10  10/10   9/10   8/10   6/10
studio-fern  10/10   9/10   8/10   6/10   4/10

Höchster Wert je Ruf (unter 0,5 wäre überhört):
  studio-nah: 0,98 0,91 0,43 …
```

Die Tabelle zeigt je Ordner, wie viele Rufe bei welcher Schwelle erkannt wären. Ein Ruf zählt, wenn
der höchste Wert seiner Aufnahme die Schwelle erreicht. Die Zeilen darunter nennen den Wert jedes
einzelnen Rufs; `--schwelle 0.6` ändert nur die Zahl in der Überschrift dieser Liste.

Was die kleine Probe sagt: Liegen die meisten Werte nahe 1, erkennt das Modell die Aussprache, und
es lohnt sich weiterzumachen. Liegen viele unter 0,5, hilft vielleicht eine andere Schreibweise im
Training (Schritt 1), sonst ist openWakeWord für dieses Wort nicht geeignet. Über Fehlauslöser sagt
sie nichts.

Für die Last dasselbe einmal auf dem Pi:

```bash
scp ~/weckwort-probe/elektra.onnx kuechen-display.local:weckwort-probe/
```

```bash
ssh kuechen-display.local 'cd weckwort-probe && ~/weckwort-venv/bin/python ~/kuechen-display/werkzeuge/weckwort_probe.py zaehlen elektra.onnx --rufe studio-nah'
```

Die letzte Zeile nennt die Rechenzeit als Anteil eines Kerns im Dauerbetrieb.

## Später: Küche und Fehlauslöser

Vorerst nicht geplant (Festlegung 22.11.2026). Das Werkzeug kann es schon, falls es so weit kommt.

Rufe in der Küche, je 20, jeder Durchgang in einen eigenen Ordner:

| Ordner | Platz | dazu |
|---|---|---|
| `herd-ruhe` | Herd | nichts |
| `herd-abzug` | Herd | Abzug an |
| `herd-musik` | Herd | Musik vom Evoke |
| `tisch-ruhe` | Tisch | nichts |
| `tisch-abzug` | Tisch | Abzug an |
| `tisch-musik` | Tisch | Musik vom Evoke |

```bash
ssh -t kuechen-display.local 'python3 kuechen-display/werkzeuge/weckwort_probe.py rufe weckwort-probe/herd-ruhe'
```

Fehlauslöser: eine Aufnahme ohne Ruf, mit Gespräch, Kochen, Musik oder Fernseher. Je länger, desto
genauer die Zahl; drei Stunden sind rund 350 MB. Der Dienst ist die ganze Zeit aus, und die
ssh-Sitzung muss offen bleiben. Strg-C hört früher auf, die fertigen Stücke bleiben. Aufnahmen aus
der Küche enthalten Gespräche der Familie und bleiben auf Pi und Mac.

```bash
ssh -t kuechen-display.local 'python3 kuechen-display/werkzeuge/weckwort_probe.py abend weckwort-probe/abend --stunden 3'
```

Gezählt wird mit `--abend`:

```bash
cd ~/weckwort-probe && venv/bin/python ~/Development/kuechen-display/pi/werkzeuge/weckwort_probe.py zaehlen elektra.onnx --rufe herd-ruhe tisch-ruhe --abend abend
```

```text
Abend: 2,95 h in 18 Dateien
Schwelle  Fehlauslöser  je Stunde
     0,3             9        3,1
     0,5             2        0,7
     0,7             0        0,0

Fehlauslöser bei Schwelle 0,5, zum Nachhören:
  abend-003.wav bei 04:12 (Wert 0,81)
```

Nach einem Auslöser zählt 2 Sekunden lang kein zweiter. Die Liste nennt Datei und Stelle, damit man
nachhören kann, was ausgelöst hat. Grenzwerte dafür, wann das Ergebnis „passt“, sind nicht
festgelegt (#111).

## Vorher ausprobieren, ohne eigenes Modell

Mit dem Beispielmodell „hey jarvis“ und einer Mac-Stimme lässt sich prüfen, ob die Einrichtung auf
dem Mac stimmt:

```bash
cd ~/weckwort-probe && mkdir -p test && say -v Samantha -o test/tmp.aiff "Hey Jarvis" && afconvert -f WAVE -d LEI16@16000 -c 1 test/tmp.aiff test/ruf-01.wav
```

```bash
cd ~/weckwort-probe && venv/bin/python ~/Development/kuechen-display/pi/werkzeuge/weckwort_probe.py zaehlen venv/lib/python3.13/site-packages/openwakeword/resources/models/hey_jarvis_v0.1.onnx --rufe test
```

Erwartet: `test  1/1` in allen Spalten. In `test/` liegt dann noch `tmp.aiff`, die das Werkzeug
übergeht.

## Aufräumen

Nach der Probe, wenn die Zahlen in #111 stehen:

```bash
ssh kuechen-display.local 'rm -r ~/weckwort-probe ~/weckwort-venv'
```

Auf dem Mac `~/weckwort-probe` löschen, sobald die Aufnahmen nicht mehr gebraucht werden.

## Gemessen und nicht gemessen

Gemessen am 22.11.2026 auf dem Mac (Python 3.13, openWakeWord 0.6.0 mit `--no-deps`, onnxruntime):

- `zaehlen` mit dem Beispielmodell „hey jarvis“: fünf mit `say` erzeugte Rufe (vier englische
  Stimmen) ergeben 5/5 bei allen Schwellen, „Hey Jasmin“, „Spotify“ und „Guten Morgen“ ergeben 0/3.
- Ein deutscher Absatz ohne das Wort löst nicht aus. Ein englischer Absatz mit „Hey Jarvis“ in der
  Mitte löst einmal aus, mit Datei und Stelle in der Liste.
- Die Zähllogik hat Tests (`pi/werkzeuge/test_weckwort_probe.py`).

Nicht gemessen:

- Alles auf dem Pi: ob sich openWakeWord mit `--no-deps` unter Python 3.13 installieren lässt,
  `rufe` und `abend` (arecord, Anhalten und Starten des Dienstes, der Ton über `pw-play`) und die
  Rechenzeit.
- Das Training im Colab-Notebook und jedes Modell für „Elektra“.
- Echte Stimmen im Raum. Die Mac-Stimmen sind sauberer Ton ohne Hall und ohne Abstand.
