# Intro

Demo Inventory

## Om inventarlisten

Dette er en demo inventarliste som viser funksjonene i Inventory System:

* Hierarkisk organisering med foreldre/barn-relasjoner
* Tagging av items for enkel søking
* Support for bilder (når du legger til egne bilder)
* Multi-tag filtering
* Alias search

## Hvordan bruke

1. Søk etter innhold i søkefeltet
2. Filtrer på boksserie (A, B, C, etc)
3. Klikk på emneord for å filtrere på tags
4. Klikk på boks-ID for å navigere til forelder/barn-containere

# Nummereringsregime

Denne demoen bruker følgende system:

* **A-serien**: Verktøykasser (A1-A10)
* **B-serien**: Elektronikk og dataområde (B1-B10)
* **C-serien**: Sport og friluft (C1-C10)
* **Locations**: Overordnede plasseringer (Garasje, Loft, Kjeller)

# ID:Garasje Oversikt over garasjen

Hovedområde for verktøy og utstyr.

# Oversikt

## ID:Workbench parent:Garasje Arbeidsbenk i garasjen

Permanent arbeidsplass med verktøy.

* tag:verktøy,manuell Hammere (3 stk)
* tag:verktøy,manuell Skrutrekkere (forskjellige størrelser)
* tag:verktøy,elektrisk ID:Drill1 Borhammer Bosch GBH 2-26
* tag:verktøy,måling Vater 60cm
* tag:verktøy,måling Tommestokk 2m

## ID:A1 parent:Workbench Verktøykasse - Skruer og biter

Organisert kasse med forskjellige skruer og bits.

* tag:skruer,metall Maskinskruer M3-M8
* tag:skruer,tre Treskrewsvarierte lengder
* tag:verktøy,bits Bitssett 32 deler
* tag:verktøy,bits Hylsesett 1/4" og 1/2"
* ID:BitBox1 Liten plastboks med spesialbiter

## ID:A2 parent:Workbench Verktøykasse - Elektrisk

Småelektronikk og kabler.

* tag:elektronikk,kabel USB-kabler (5-10 stk)
* tag:elektronikk,kabel HDMI-kabler
* tag:elektronikk,kabel Ethernet-kabler
* tag:elektronikk,verktøy Loddbolt 60W
* tag:elektronikk,verktøy Multimeter Fluke
* tag:elektronikk,komponenter Motstander og kondensatorer
* tag:elektronikk,komponenter Arduino-brettkort (2 stk)

## ID:A3 parent:Workbench Verktøykasse - Maling og lim

Diverse maling, lim og forseglingsmidler.

* tag:maling,tre Trebeis hvit 0.5L
* tag:maling,metall Rustbeskyttelse sort
* tag:lim,kontakt Kontaktlim
* tag:lim,epoxy Epoxy 2-komponent
* tag:lim,silikon Silikon transparent og hvit
* tag:maling,verktøy Pensel sett (5 deler)
* tag:maling,verktøy Malerrulle med stang

## ID:Drill1 parent:Workbench Borhammer Bosch GBH 2-26

Elektrisk borhammer med tilbehør.

* Borkassett SDS-plus
* Meiselsett for betong
* Dybdeanlegg
* Sidehåndtak
* Oppbevaringskoffert

## ID:BitBox1 parent:A1 Spesialbiter

Samling av sjeldnere bits.

* Torx bits T10-T40
* Sekskantnøkler 1.5-10mm
* Pozidriv bits PZ1-PZ3

# ID:Loft Oversikt over loftet

Lagerområde for sesongbaserte ting og lagring.

# Oversikt

## ID:C1 parent:Loft Sport og friluft - Vinter

Utstyr for vintersport.

* tag:sport,ski,barn Barneski 120cm
* tag:sport,ski,barn Skistaver barn 100cm
* tag:sport,ski,voksen Langrennsski 200cm
* tag:sport,ski,voksen Skisko størrelse 42
* tag:sport,ski,tilbehør Skivoks (rød og blå)
* tag:sport,ski,tilbehør Smørejern
* tag:klær,vinter,barn Vinterdress størrelse 110
* tag:klær,vinter,barn Votter og lue

## ID:C2 parent:Loft Sport og friluft - Sommer

Campingutstyr og sommersport.

* tag:camping,sove Sovepose -5°C (2 stk)
* tag:camping,sove Liggeunderlag selvoppblåsbart
* tag:camping,koking Trangiakjøkken komplett
* tag:camping,koking Gassbluss og patroner
* tag:sport,sykkel Sykkelhjelm voksen
* tag:sport,sykkel Sykkellås med nøkkel
* tag:sport,sykkel Sykkellykt LED front og bak

## ID:C3 parent:Loft Leker og barneting

Leketøy og barneutstyr i oppbevaring.

* tag:leker,barn,bygg LEGO kasser (3 store)
* tag:leker,barn,dukker Dukkehus med møbler
* tag:leker,barn,biler Biler og tog
* tag:bok,barn Bildebøker 20+ stk
* tag:bok,barn Høytlesningsbøker
* tag:klær,barn,vår Vårjakker str 80-110
* tag:klær,barn,sommer Sommershorts og t-skjorter

# ID:Kjeller Oversikt over kjelleren

Våtrom og generell oppbevaring.

# Oversikt

## ID:B1 parent:Kjeller Elektronikk - Datautstyr

Gamle datamaskiner og tilbehør.

* tag:elektronikk,pc,gammel Laptop HP 2015 (defekt)
* tag:elektronikk,pc,gammel Desktop PC deler (hovedkort, RAM)
* tag:elektronikk,skjerm LCD-skjerm 24" (fungerer)
* tag:elektronikk,tilbehør Tastatur og mus (5 sett)
* tag:elektronikk,kabel Strømkabler og adaptere
* tag:elektronikk,lagring Eksterne harddisker 500GB-2TB

## ID:B2 parent:Kjeller Elektronikk - Audio/Video

Lydanlegg og videoutstyr.

* tag:elektronikk,lyd Høyttalere stereo
* tag:elektronikk,lyd Hodetelefoner (3 par)
* tag:elektronikk,lyd Mikrofon med stativ
* tag:elektronikk,video Webkamera HD
* tag:elektronikk,kabel 3.5mm jack-kabler
* tag:elektronikk,kabel RCA-kabler

## ID:B3 parent:Kjeller Strøm og belysning

Reserve pærer og lysutstyr.

* tag:belysning,led LED-pærer E27 (10 stk)
* tag:belysning,led LED-strips 5m med strømforsyning
* tag:belysning,arbeid Arbeidslampe LED 20W
* tag:elektronikk,strøm Skjøteledning 10m
* tag:elektronikk,strøm Kabeltrommel 25m
* tag:elektronikk,strøm Multistikkontakt (5 stk)

# Ekstra Notater

Dette er en demo-inventarliste. For å lage din egen:

1. Kopier denne strukturen eller bruk `inventory-md init`
2. Rediger markdown-filen med ditt eget innhold
3. Kjør `inventory-md parse inventory.md`
4. Åpne `search.html` i nettleseren

Lykke til med din inventarliste!
