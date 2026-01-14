* The "quick start" in the installation guide should be made easier, and should rely on a Makefile
* System is currently used for "Solveig" (boat) and "Furuset" (home).  I don't want to go public with the database here, but it would be nice with a third demo site with demo data.
* There are some things now that should be included in the inventory-md:
  * at Solveig we have a shopping list generator script
  * There are some files under ~/.claude/skills/ that should be included.
  * The integration with the Lidl+ shopping history downloader should also be scripted better and included in the inventory system.
  * Make a public puppet-module for rolling out things, too
* QR label printing: Generate printable QR code labels with unique IDs for containers and items
  - Pre-print sheets of labels (like Avery 5260) with sequential IDs
  - QR codes should link to the web UI (e.g., https://inventory.example.com/item/ID)
  - Consider support for dedicated label printers (Brother QL-700, Dymo)
  - See how Homebox does it: https://hay-kot.github.io/homebox/tips-tricks/
  - Some thoughts: IDs consisting of two letters and one digit.  First letter differs for different variants of the labels - I will need some very small labels with only QR-code for smaller items, bigger labels with QR-code and visible ID-text and possibly print date for bigger items (and possibly two stickers for each big item), similar labels but like 6 copies of each for labelling containers from all sides.  The second letter and digit should increase incrementally.
* I'd like the inventory gir repo to include the filenames of all the photos (backup of the photos are done separately, but we need the file listings to roll out the photos to the correct places)
* Immich integration?
* IDs should be better thought through
* Furuset: reintegrate the new script and ensure the existing structure does not break too much
* Solveig: take photos
* When the Solveig and Furuset inventory systems look OK, we should make a demo site and make a 1.0-release
* Consider scrapping the markdown file
* Add size tagging for clothes (e.g., str:140, str:L, str:42)
* Consider age ranges for children's items (e.g., age:6-8)

