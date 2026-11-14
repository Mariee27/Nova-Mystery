# "Was passiert, wenn …" – Antwortblatt für die Befragung

Jede Antwort beschreibt, was die App wirklich tut. In Klammern steht der Test, der es belegt
(`tests/test_rules.py`, `test_views.py`, `test_db.py`, `test_case.py`; Nummer = Done-when-Zeile der Spec).

## Ausfälle

**… ein Spieler offline geht (Handy aus, kein Internet)?**
Jedes offene Handy meldet sich alle 2 Sekunden. Kommt 20 Sekunden lang nichts, steht der Spieler bei allen als "offline" in der Liste. Das Spiel läuft weiter. Seine Aktion zählt als "keine Aktion", seine Stimme als Enthaltung. Niemand muss auf ihn warten: Die Runde endet, sobald alle Online-Spieler fertig sind, spätestens mit dem Timer. (DW 12, 13)

**… er zurückkommt?**
Er öffnet denselben Link im selben Browser und sitzt wieder auf seinem Platz, mit derselben Karte, in jeder Phase. Der Link enthält sein geheimes Token (22 zufällige Zeichen). (Smoke-Test, DW 17)

**… er es von einem anderen Gerät versucht?**
Ohne den Link geht es nicht. Das ist Absicht: Könnte man mit Name und Raumcode zurück, könnte jeder einen fremden Platz übernehmen und dessen Karte lesen.

**… der Host offline geht?**
Nach 20 Sekunden wird automatisch der nächste Online-Spieler in Beitrittsreihenfolge Host. Kommt der alte Host zurück, bleibt der neue Host. (DW 14)

**… zu viele Spieler ausfallen?**
Sind während des Spiels weniger als 3 Spieler online, endet das Spiel mit einer Meldung auf allen Bildschirmen. Mit 3 läuft es weiter. (DW 15)

**… der Mörder offline geht?**
Das Spiel läuft normal weiter. Er kann gewählt werden und wird am Ende aufgedeckt.

**… die App neu startet?**
Lokal bleibt alles erhalten, weil der Spielstand in einer SQLite-Datei liegt (DW 21). Auf dem kostenlosen Hosting kann die Datei bei einem Neustart verloren gehen. Dann braucht man einen neuen Raum. Das haben wir bewusst so entschieden: Ein Spiel dauert 5 Minuten.

**… jemand die Seite neu lädt?**
Nichts geht verloren. Der Spielstand liegt auf dem Server, nicht im Browser.

## Regeln

**… jemand zweimal handelt oder doppelt klickt?**
Die zweite Aktion wird abgelehnt, der Spielstand bleibt unverändert. (DW 7, 16)

**… zwei Spieler gleichzeitig denselben Ort durchsuchen?**
Genau einer gewinnt. Der andere bekommt die Meldung "already searched" und darf einen anderen Ort wählen. Seine Aktion ist nicht verbraucht. Technisch: Jede Aktion läuft in einer Schreib-Transaktion, die zweite muss warten und sieht dann den geänderten Stand. (DW 7, 19)

**… jemand außerhalb der Phase handelt (z. B. in der Diskussion abstimmt)?**
Abgelehnt. (DW 7, 10)

**… jemand für sich selbst oder zweimal abstimmt?**
Abgelehnt. (DW 10)

**… die Abstimmung unentschieden ausgeht?**
Der Mörder gewinnt. Die Detektive gewinnen nur, wenn der Mörder mehr Stimmen hat als jeder andere. Auch bei 0 Stimmen gewinnt der Mörder. (DW 11)

**… jemand nach Spielstart beitreten will, oder ein 7. Spieler kommt?**
Abgelehnt. Zuschauen über das Board geht immer. (DW 4)

**… zwei Spieler denselben Namen wollen?**
Der zweite wird abgelehnt, Groß- und Kleinschreibung egal. (DW 4)

**… weniger als 4 Spieler da sind?**
Der Start-Knopf ist gesperrt, und auch ein erzwungener Start wird von den Regeln abgelehnt. (DW 4)

**… ein Nicht-Host das Spiel starten oder eine Phase beenden will?**
Er hat den Knopf nicht, und die Regeln lehnen es zusätzlich ab. (DW 5)

**… eine Frage nie beantwortet wird?**
Am Ende der Diskussion steht im Protokoll, dass keine Antwort kam. (DW 8)

**… niemand etwas tut?**
Die Timer schalten die Phasen weiter: 30 s Karten, 90 s Untersuchung, 60 s Diskussion, 30 s Abstimmung. (DW 6)

## Sicherheit

**… jemand die Karte eines anderen sehen will?**
Der Server schickt jedem Handy nur die eigene Karte. Das Board und das öffentliche Protokoll enthalten vor der Auflösung weder den Mörder noch Geheimnisse noch private Spuren. (DW 17)

**… jemand HTML oder Formatierung in eine Frage tippt?**
Es erscheint als normaler Text, nichts wird ausgeführt. Höchstens 140 Zeichen. (DW 18)

**… jemand einen Link errät?**
Das Token hat 22 zufällige Zeichen. Der Raumcode allein reicht nur zum Zuschauen und, in der Lobby, zum Beitreten.

**… die falsche Spur des Mörders auffallen könnte?**
Sie sieht aus wie ein echtes Suchergebnis. Erst in der Auflösung ist sie als gefälscht markiert. (DW 9, 17)

## Fall und Fairness

**Ist jeder Fall lösbar?**
Ja. Ein Prüfer kontrolliert jeden Fall vor dem Start: genau ein Mörder, mindestens 2 starke Spuren gegen ihn (davon mindestens 1 an einem Ort), keine starke Spur gegen Unschuldige, höchstens 1 Fehlspur pro Unschuldigem. Getestet über 600 zufällige Fälle. (DW 1, 3)

**Ist es immer derselbe Fall?**
Nein. Mörder, Tatort, Rollen und Spuren werden pro Spiel neu gezogen. Mit dem Demo-Schalter kommt immer derselbe Fall, zum Proben. (DW 2)

**Wo werden die Daten gespeichert?**
In einer SQLite-Datei auf dem Server: eine Zeile pro Raum mit dem Spielstand, plus eine Tabelle mit den Lebenszeichen der Spieler. Es gibt keine Konten, keine Passwörter und keine E-Mail-Adressen.

**Was decken die Tests ab?**
Alle Regeln und Ablehnungen, die Timer, die Ausfallregeln, den Fallprüfer, die Sichtbarkeit (wer sieht was) und die Speicherung. Die Oberfläche wird mit einer Attrappe durchgespielt. Das Aussehen im Browser prüfen wir von Hand.
