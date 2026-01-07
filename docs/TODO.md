* Furuset: new inventory git repo
* I'd like the inventory gir repo to include the filenames of all the photos (backup of the photos are done separately, but we need the file listings to roll out the photos to the correct places)
* Currently used for "Solveig" and "Furuset".
* IDs should be better thought through
* Furuset: reintegrate the new script and ensure the existing structure does not break too much
* Solveig: take photos
* When the Solveig and Furuset inventory systems look OK, we should make a demo site and make a 1.0-release
* Consider scrapping the markdown file
* Add size tagging for clothes (e.g., str:140, str:L, str:42)
* Consider age ranges for children's items (e.g., age:6-8)
* QR label printing: Generate printable QR code labels with unique IDs for containers and items
  - Pre-print sheets of labels (like Avery 5260) with sequential IDs
  - QR codes should link to the web UI (e.g., https://inventory.example.com/item/ID)
  - Consider support for dedicated label printers (Brother QL-700, Dymo)
  - See how Homebox does it: https://hay-kot.github.io/homebox/tips-tricks/

